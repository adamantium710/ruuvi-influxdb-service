"""
Logging configuration for the Ruuvi Sensor Service.
Provides comprehensive logging setup with multiple handlers and structured logging.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
import colorlog
from datetime import datetime


class ProductionLogger:
    """
    Comprehensive logging setup for production deployment with multiple handlers,
    structured logging, and performance monitoring.
    """
    
    def __init__(self, 
                 app_name: str = "ruuvi_sensor_service",
                 log_dir: str = "./logs",
                 log_level: str = "INFO",
                 max_file_size: int = 10 * 1024 * 1024,  # 10MB
                 backup_count: int = 5,
                 enable_console: bool = True,
                 enable_syslog: bool = False):
        
        self.app_name = app_name
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        self.enable_syslog = enable_syslog
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup loggers
        self._setup_root_logger()
        self._setup_component_loggers()
    
    def _setup_root_logger(self):
        """Configure root logger with multiple handlers."""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler with colors (for development/debugging)
        if self.enable_console:
            console_handler = colorlog.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_formatter = colorlog.ColoredFormatter(
                '%(log_color)s%(asctime)s [%(levelname)8s] %(name)s: %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red,bg_white',
                }
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / f"{self.app_name}.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s [%(process)d:%(thread)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Syslog handler for systemd integration
        if self.enable_syslog:
            try:
                syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
                syslog_handler.setLevel(logging.WARNING)  # Only warnings and errors to syslog
                syslog_formatter = logging.Formatter(
                    f'{self.app_name}[%(process)d]: %(levelname)s - %(message)s'
                )
                syslog_handler.setFormatter(syslog_formatter)
                root_logger.addHandler(syslog_handler)
            except Exception as e:
                print(f"Warning: Could not setup syslog handler: {e}")
    
    def _setup_component_loggers(self):
        """Configure specific loggers for different components."""
        # BLE Scanner logger
        ble_logger = logging.getLogger('ruuvi.ble')
        ble_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "ble_scanner.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        ble_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] BLE: %(message)s'
        ))
        ble_logger.addHandler(ble_handler)
        
        # InfluxDB logger
        influx_logger = logging.getLogger('ruuvi.influxdb')
        influx_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "influxdb.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        influx_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] InfluxDB: %(message)s'
        ))
        influx_logger.addHandler(influx_handler)
        
        # Performance logger
        perf_logger = logging.getLogger('ruuvi.performance')
        perf_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / "performance.log",
            maxBytes=self.max_file_size,
            backupCount=self.backup_count
        )
        perf_handler.setFormatter(logging.Formatter(
            '%(asctime)s PERF: %(message)s'
        ))
        perf_logger.addHandler(perf_handler)
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """Get a logger instance."""
        if name:
            return logging.getLogger(name)
        return logging.getLogger()
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        logging.getLogger().debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        logging.getLogger().info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        logging.getLogger().warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        logging.getLogger().error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        logging.getLogger().critical(message, *args, **kwargs)


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection for production debugging.
    """
    
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger('ruuvi.performance')
        self.metrics = {
            'ble_scan_times': [],
            'influxdb_write_times': [],
            'metadata_operations': [],
            'memory_usage': [],
            'cpu_usage': []
        }
        self.start_time = datetime.now()
    
    def log_ble_scan(self, duration: float, devices_found: int, success: bool):
        """Log BLE scan performance metrics."""
        self.metrics['ble_scan_times'].append({
            'duration': duration,
            'devices_found': devices_found,
            'success': success,
            'timestamp': datetime.now()
        })
        
        self.logger.info(
            f"BLE_SCAN duration={duration:.2f}s devices={devices_found} success={success}"
        )
    
    def log_influxdb_write(self, duration: float, points_written: int, success: bool):
        """Log InfluxDB write performance metrics."""
        self.metrics['influxdb_write_times'].append({
            'duration': duration,
            'points_written': points_written,
            'success': success,
            'timestamp': datetime.now()
        })
        
        self.logger.info(
            f"INFLUXDB_WRITE duration={duration:.2f}s points={points_written} success={success}"
        )
    
    def log_system_resources(self):
        """Log current system resource usage."""
        try:
            import psutil
            process = psutil.Process()
            
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            self.metrics['memory_usage'].append({
                'rss': memory_info.rss,
                'vms': memory_info.vms,
                'timestamp': datetime.now()
            })
            
            self.metrics['cpu_usage'].append({
                'cpu_percent': cpu_percent,
                'timestamp': datetime.now()
            })
            
            self.logger.info(
                f"RESOURCES memory_rss={memory_info.rss/1024/1024:.1f}MB "
                f"memory_vms={memory_info.vms/1024/1024:.1f}MB cpu={cpu_percent:.1f}%"
            )
            
        except ImportError:
            self.logger.warning("psutil not available for resource monitoring")
        except Exception as e:
            self.logger.error(f"Failed to log system resources: {e}")
    
    def get_performance_summary(self) -> dict:
        """Generate performance summary for monitoring dashboards."""
        summary = {
            'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
            'ble_scans': {
                'total': len(self.metrics['ble_scan_times']),
                'successful': sum(1 for scan in self.metrics['ble_scan_times'] if scan['success']),
                'avg_duration': 0,
                'avg_devices_found': 0
            },
            'influxdb_writes': {
                'total': len(self.metrics['influxdb_write_times']),
                'successful': sum(1 for write in self.metrics['influxdb_write_times'] if write['success']),
                'avg_duration': 0,
                'total_points_written': sum(write['points_written'] for write in self.metrics['influxdb_write_times'])
            }
        }
        
        # Calculate averages
        if self.metrics['ble_scan_times']:
            successful_scans = [scan for scan in self.metrics['ble_scan_times'] if scan['success']]
            if successful_scans:
                summary['ble_scans']['avg_duration'] = sum(scan['duration'] for scan in successful_scans) / len(successful_scans)
                summary['ble_scans']['avg_devices_found'] = sum(scan['devices_found'] for scan in successful_scans) / len(successful_scans)
        
        if self.metrics['influxdb_write_times']:
            successful_writes = [write for write in self.metrics['influxdb_write_times'] if write['success']]
            if successful_writes:
                summary['influxdb_writes']['avg_duration'] = sum(write['duration'] for write in successful_writes) / len(successful_writes)
        
        return summary
    
    def record_metric(self, metric_name: str, value: float):
        """Record a metric value."""
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        self.metrics[metric_name].append({
            'value': value,
            'timestamp': datetime.now()
        })
        
        self.logger.debug(f"METRIC {metric_name}={value}")
    
    def measure_time(self, operation_name: str):
        """Context manager for measuring operation time."""
        from contextlib import contextmanager
        import time
        
        @contextmanager
        def timer():
            start_time = time.time()
            try:
                yield
            finally:
                duration = time.time() - start_time
                self.record_metric(f"{operation_name}_duration", duration)
                self.logger.info(f"TIMING {operation_name}={duration:.3f}s")
        
        return timer()
    
    def get_metrics(self) -> dict:
        """Get all recorded metrics."""
        return self.metrics.copy()


def setup_logging(config=None) -> ProductionLogger:
    """
    Setup logging for the Ruuvi Sensor Service using configuration.
    
    Args:
        config: Configuration instance (if None, will import from utils.config)
        
    Returns:
        ProductionLogger instance
    """
    if config is None:
        from .config import config
    
    return ProductionLogger(
        log_level=config.log_level,
        log_dir=str(config.log_dir),
        max_file_size=config.log_max_file_size,
        backup_count=config.log_backup_count,
        enable_console=config.log_enable_console,
        enable_syslog=config.log_enable_syslog
    )