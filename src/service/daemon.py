"""
Background Daemon for Ruuvi Sensor Service.
Handles continuous background operation, data collection, and monitoring.
"""

import asyncio
import signal
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, Set, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..utils.config import Config, ConfigurationError
from ..utils.logging import ProductionLogger, PerformanceMonitor
from ..metadata.manager import MetadataManager, MetadataError
from ..ble.scanner import RuuviBLEScanner, RuuviSensorData
from ..influxdb.client import RuuviInfluxDBClient


@dataclass
class DaemonStats:
    """Daemon statistics container."""
    start_time: datetime
    uptime_seconds: int
    scan_cycles: int
    sensors_discovered: int
    data_points_collected: int
    data_points_written: int
    errors_count: int
    last_scan_time: Optional[datetime] = None
    last_write_time: Optional[datetime] = None
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None


class ConfigFileHandler(FileSystemEventHandler):
    """File system event handler for configuration hot-reloading."""
    
    def __init__(self, daemon: 'RuuviDaemon'):
        """Initialize handler."""
        self.daemon = daemon
        self.last_reload = time.time()
        self.reload_cooldown = 5.0  # Minimum seconds between reloads
    
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        # Check if it's a configuration file we care about
        config_files = {'.env', 'metadata.json'}
        file_name = Path(event.src_path).name
        
        if file_name in config_files:
            current_time = time.time()
            if current_time - self.last_reload > self.reload_cooldown:
                self.last_reload = current_time
                asyncio.create_task(self.daemon._reload_configuration())


class RuuviDaemonError(Exception):
    """Base exception for daemon operations."""
    pass


class RuuviDaemon:
    """
    Background daemon for continuous Ruuvi sensor monitoring.
    
    Features:
    - Continuous BLE scanning and data collection
    - Automatic InfluxDB data forwarding
    - Configuration hot-reloading
    - Error recovery and resilience
    - Performance monitoring
    - Graceful shutdown handling
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize daemon."""
        self.config_path = config_path or Path.cwd()
        self.config: Optional[Config] = None
        self.logger: Optional[ProductionLogger] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.metadata_manager: Optional[MetadataManager] = None
        self.ble_scanner: Optional[RuuviBLEScanner] = None
        self.influxdb_client: Optional[RuuviInfluxDBClient] = None
        
        # Daemon state
        self._running = False
        self._shutdown_requested = False
        self._scan_task: Optional[asyncio.Task] = None
        self._write_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
        
        # Configuration monitoring
        self._config_observer: Optional[Observer] = None
        self._config_handler: Optional[ConfigFileHandler] = None
        
        # Statistics
        self._stats = DaemonStats(
            start_time=datetime.now(),
            uptime_seconds=0,
            scan_cycles=0,
            sensors_discovered=0,
            data_points_collected=0,
            data_points_written=0,
            errors_count=0
        )
        
        # Data buffer for batch processing
        self._data_buffer: Dict[str, RuuviSensorData] = {}
        self._buffer_lock = asyncio.Lock()
        
        # Error recovery
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10
        self._error_backoff_base = 1.0
        self._error_backoff_max = 60.0
        
        # Callbacks
        self._data_callbacks: Set[Callable[[RuuviSensorData], None]] = set()
        self._status_callbacks: Set[Callable[[Dict[str, Any]], None]] = set()
    
    def add_data_callback(self, callback: Callable[[RuuviSensorData], None]):
        """Add callback for sensor data events."""
        self._data_callbacks.add(callback)
    
    def remove_data_callback(self, callback: Callable[[RuuviSensorData], None]):
        """Remove data callback."""
        self._data_callbacks.discard(callback)
    
    def add_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for status updates."""
        self._status_callbacks.add(callback)
    
    def remove_status_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Remove status callback."""
        self._status_callbacks.discard(callback)
    
    async def _initialize_components(self):
        """Initialize all daemon components."""
        try:
            # Load configuration
            self.config = Config()
            self.config.validate_environment()
            
            # Initialize logging
            self.logger = ProductionLogger(self.config)
            self.performance_monitor = PerformanceMonitor(self.logger)
            
            # Initialize metadata manager
            self.metadata_manager = MetadataManager(self.config, self.logger)
            
            # Initialize BLE scanner
            self.ble_scanner = RuuviBLEScanner(
                self.config, 
                self.logger, 
                self.performance_monitor
            )
            
            # Initialize InfluxDB client
            self.influxdb_client = RuuviInfluxDBClient(
                self.config, 
                self.logger, 
                self.performance_monitor
            )
            
            # Connect to InfluxDB
            await self.influxdb_client.connect()
            
            # Set up data callback
            self.ble_scanner.add_callback(self._handle_sensor_data)
            
            self.logger.info("Daemon components initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Component initialization failed: {e}")
            raise RuuviDaemonError(f"Initialization failed: {e}")
    
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            if self.logger:
                self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            self._shutdown_requested = True
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Handle SIGHUP for configuration reload
        def reload_handler(signum, frame):
            """Handle configuration reload signal."""
            if self.logger:
                self.logger.info("Received SIGHUP, reloading configuration...")
            asyncio.create_task(self._reload_configuration())
        
        signal.signal(signal.SIGHUP, reload_handler)
    
    def _setup_config_monitoring(self):
        """Set up configuration file monitoring for hot-reloading."""
        try:
            self._config_handler = ConfigFileHandler(self)
            self._config_observer = Observer()
            
            # Monitor project directory for .env and metadata.json changes
            self._config_observer.schedule(
                self._config_handler,
                str(self.config_path),
                recursive=False
            )
            
            # Monitor data directory for metadata.json changes
            data_dir = self.config_path / "data"
            if data_dir.exists():
                self._config_observer.schedule(
                    self._config_handler,
                    str(data_dir),
                    recursive=False
                )
            
            self._config_observer.start()
            self.logger.info("Configuration monitoring started")
            
        except Exception as e:
            self.logger.warning(f"Failed to setup configuration monitoring: {e}")
    
    async def _reload_configuration(self):
        """Reload configuration and restart components if needed."""
        try:
            self.logger.info("Reloading configuration...")
            
            # Reload configuration
            old_config = self.config
            new_config = Config()
            new_config.validate_environment()
            
            # Check if critical settings changed
            critical_changes = False
            if old_config:
                critical_settings = [
                    'influxdb_host', 'influxdb_port', 'influxdb_token',
                    'influxdb_org', 'influxdb_bucket', 'ble_adapter'
                ]
                
                for setting in critical_settings:
                    if getattr(old_config, setting) != getattr(new_config, setting):
                        critical_changes = True
                        break
            
            # Update configuration
            self.config = new_config
            
            # Reload metadata
            if self.metadata_manager:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.metadata_manager.load
                )
            
            # If critical changes, restart components
            if critical_changes:
                self.logger.info("Critical configuration changes detected, restarting components...")
                await self._restart_components()
            
            self.logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            self.logger.error(f"Configuration reload failed: {e}")
            self._consecutive_errors += 1
    
    async def _restart_components(self):
        """Restart critical components after configuration changes."""
        try:
            # Stop current scanning
            if self.ble_scanner:
                await self.ble_scanner.stop_continuous_scan()
            
            # Disconnect from InfluxDB
            if self.influxdb_client:
                await self.influxdb_client.disconnect()
            
            # Reinitialize components
            await self._initialize_components()
            
            # Restart scanning if we were running
            if self._running:
                await self.ble_scanner.start_continuous_scan()
            
            self.logger.info("Components restarted successfully")
            
        except Exception as e:
            self.logger.error(f"Component restart failed: {e}")
            raise
    
    def _handle_sensor_data(self, sensor_data: RuuviSensorData):
        """Handle incoming sensor data."""
        try:
            # Update statistics
            self._stats.data_points_collected += 1
            self._stats.last_scan_time = datetime.now()
            
            # Update metadata
            if self.metadata_manager:
                self.metadata_manager.update_sensor_last_seen(sensor_data.mac_address)
            
            # Add to buffer for batch processing
            asyncio.create_task(self._buffer_sensor_data(sensor_data))
            
            # Notify callbacks
            for callback in self._data_callbacks:
                try:
                    callback(sensor_data)
                except Exception as e:
                    if self.logger:
                        self.logger.warning(f"Data callback failed: {e}")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error handling sensor data: {e}")
            self._consecutive_errors += 1
    
    async def _buffer_sensor_data(self, sensor_data: RuuviSensorData):
        """Add sensor data to buffer for batch processing."""
        async with self._buffer_lock:
            # Use MAC address as key to avoid duplicates in buffer
            self._data_buffer[sensor_data.mac_address] = sensor_data
    
    async def _continuous_scan_loop(self):
        """Main continuous scanning loop."""
        self.logger.info("Starting continuous scan loop...")
        
        try:
            # Start continuous scanning once - it runs its own loop
            await self.ble_scanner.start_continuous_scan()
            
            # Wait for shutdown - the scanner handles its own continuous operation
            while self._running and not self._shutdown_requested:
                await asyncio.sleep(1)
                
            # Update statistics on successful completion
            self._stats.scan_cycles += 1
            self._consecutive_errors = 0
                
        except Exception as e:
            self.logger.error(f"Continuous scan loop error: {e}")
            self._consecutive_errors += 1
            self._stats.errors_count += 1
            
            # Check for too many consecutive errors
            if self._consecutive_errors >= self._max_consecutive_errors:
                self.logger.critical("Too many consecutive errors, shutting down...")
                self._shutdown_requested = True
                
        finally:
            # Stop scanning on exit
            if self.ble_scanner:
                try:
                    await self.ble_scanner.stop_continuous_scan()
                except Exception as e:
                    self.logger.warning(f"Error stopping scanner: {e}")
        
        self.logger.info("Continuous scan loop stopped")
    
    async def _data_write_loop(self):
        """Background loop for writing buffered data to InfluxDB."""
        self.logger.info("Starting data write loop...")
        
        write_interval = self.config.influxdb_flush_interval
        
        while self._running and not self._shutdown_requested:
            try:
                await asyncio.sleep(write_interval)
                
                # Get buffered data
                async with self._buffer_lock:
                    if not self._data_buffer:
                        continue
                    
                    data_to_write = list(self._data_buffer.values())
                    self._data_buffer.clear()
                
                # Write to InfluxDB
                if data_to_write:
                    for sensor_data in data_to_write:
                        await self.influxdb_client.write_sensor_data(sensor_data)
                    
                    self._stats.data_points_written += len(data_to_write)
                    self._stats.last_write_time = datetime.now()
                    
                    self.logger.debug(f"Wrote {len(data_to_write)} data points to InfluxDB")
                
            except Exception as e:
                self.logger.error(f"Data write loop error: {e}")
                self._consecutive_errors += 1
                self._stats.errors_count += 1
                
                # Error backoff
                backoff_time = min(
                    self._error_backoff_base * (2 ** min(self._consecutive_errors, 5)),
                    self._error_backoff_max
                )
                await asyncio.sleep(backoff_time)
        
        # Flush remaining data on shutdown
        async with self._buffer_lock:
            if self._data_buffer:
                try:
                    for sensor_data in self._data_buffer.values():
                        await self.influxdb_client.write_sensor_data(sensor_data)
                    self.logger.info(f"Flushed {len(self._data_buffer)} remaining data points")
                except Exception as e:
                    self.logger.error(f"Error flushing data on shutdown: {e}")
        
        self.logger.info("Data write loop stopped")
    
    async def _statistics_loop(self):
        """Background loop for updating statistics and status."""
        self.logger.info("Starting statistics loop...")
        
        while self._running and not self._shutdown_requested:
            try:
                await asyncio.sleep(60)  # Update every minute
                
                # Update uptime
                self._stats.uptime_seconds = int(
                    (datetime.now() - self._stats.start_time).total_seconds()
                )
                
                # Update resource usage
                try:
                    import psutil
                    process = psutil.Process()
                    self._stats.memory_usage_mb = process.memory_info().rss / 1024 / 1024
                    self._stats.cpu_usage_percent = process.cpu_percent()
                except ImportError:
                    pass
                
                # Periodic metadata save (batched to avoid race conditions)
                if self.metadata_manager:
                    try:
                        if self.metadata_manager.save_if_dirty():
                            self.logger.debug("Saved metadata (batched)")
                    except Exception as e:
                        self.logger.error(f"Failed to save metadata: {e}")
                
                # Notify status callbacks
                status = self.get_status()
                for callback in self._status_callbacks:
                    try:
                        callback(status)
                    except Exception as e:
                        self.logger.warning(f"Status callback failed: {e}")
                
            except Exception as e:
                self.logger.error(f"Statistics loop error: {e}")
                await asyncio.sleep(60)
        
        self.logger.info("Statistics loop stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current daemon status."""
        return {
            "running": self._running,
            "shutdown_requested": self._shutdown_requested,
            "stats": asdict(self._stats),
            "buffer_size": len(self._data_buffer),
            "consecutive_errors": self._consecutive_errors,
            "components": {
                "config": self.config is not None,
                "logger": self.logger is not None,
                "metadata_manager": self.metadata_manager is not None,
                "ble_scanner": self.ble_scanner is not None,
                "influxdb_client": self.influxdb_client is not None and self.influxdb_client.is_connected(),
            }
        }
    
    def get_statistics(self) -> DaemonStats:
        """Get daemon statistics."""
        return self._stats
    
    async def start(self):
        """Start the daemon."""
        if self._running:
            raise RuuviDaemonError("Daemon is already running")
        
        try:
            # Initialize components first (this sets up logger)
            await self._initialize_components()
            
            self.logger.info("Starting Ruuvi Sensor Daemon...")
            
            # Set up signal handlers
            self._setup_signal_handlers()
            
            # Set up configuration monitoring
            self._setup_config_monitoring()
            
            # Start daemon
            self._running = True
            
            # Start background tasks
            self._scan_task = asyncio.create_task(self._continuous_scan_loop())
            self._write_task = asyncio.create_task(self._data_write_loop())
            self._stats_task = asyncio.create_task(self._statistics_loop())
            
            self.logger.info("Ruuvi Sensor Daemon started successfully")
            
            # Wait for shutdown
            while self._running and not self._shutdown_requested:
                await asyncio.sleep(1)
            
            # Shutdown
            await self.stop()
            
        except Exception as e:
            self.logger.error(f"Daemon startup failed: {e}")
            await self.stop()
            raise RuuviDaemonError(f"Startup failed: {e}")
    
    async def stop(self):
        """Stop the daemon gracefully."""
        if not self._running:
            return
        
        self.logger.info("Stopping Ruuvi Sensor Daemon...")
        self._running = False
        
        # Cancel background tasks
        tasks = [self._scan_task, self._write_task, self._stats_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Stop configuration monitoring
        if self._config_observer:
            self._config_observer.stop()
            self._config_observer.join()
        
        # Save any pending metadata changes before shutdown
        if self.metadata_manager:
            try:
                if self.metadata_manager.save_if_dirty():
                    self.logger.info("Saved pending metadata changes during shutdown")
            except Exception as e:
                self.logger.error(f"Failed to save metadata during shutdown: {e}")
        
        # Cleanup components
        if self.ble_scanner:
            await self.ble_scanner.cleanup()
        
        if self.influxdb_client:
            await self.influxdb_client.flush_all()
            await self.influxdb_client.disconnect()
        
        self.logger.info("Ruuvi Sensor Daemon stopped")
    
    async def reload(self):
        """Reload daemon configuration."""
        await self._reload_configuration()


# CLI entry point for daemon mode
async def run_daemon():
    """Run the daemon from command line."""
    daemon = RuuviDaemon()
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        print("\nDaemon interrupted by user")
    except RuuviDaemonError as e:
        print(f"Daemon initialization failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected daemon error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_daemon())