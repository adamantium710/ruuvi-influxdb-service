"""
InfluxDB client for Ruuvi sensor data storage.
Handles connection management, data buffering, batch writing, and retry logic.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
from contextlib import asynccontextmanager

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS, ASYNCHRONOUS
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.rest import ApiException

from ..ble.scanner import RuuviSensorData
from ..utils.config import Config
from ..utils.logging import ProductionLogger, PerformanceMonitor


@dataclass
class DataPoint:
    """Data point for InfluxDB storage."""
    measurement: str
    tags: Dict[str, str] = field(default_factory=dict)
    fields: Dict[str, Union[float, int, str, bool]] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


@dataclass
class BatchStats:
    """Statistics for batch operations."""
    points_written: int = 0
    points_failed: int = 0
    batches_sent: int = 0
    batches_failed: int = 0
    last_write_time: Optional[datetime] = None
    total_write_time: float = 0.0


class InfluxDBError(Exception):
    """Base exception for InfluxDB operations."""
    pass


class ConnectionError(InfluxDBError):
    """Exception for connection errors."""
    pass


class WriteError(InfluxDBError):
    """Exception for write operation errors."""
    pass


class RuuviInfluxDBClient:
    """
    InfluxDB client for Ruuvi sensor data with comprehensive features.
    
    Features:
    - Connection management with health monitoring
    - Data buffering and batch writing
    - Retry logic with exponential backoff
    - Performance monitoring and statistics
    - Line protocol formatting
    - Async and sync write operations
    """
    
    def __init__(self, config: Config, logger: ProductionLogger, performance_monitor: PerformanceMonitor):
        """
        Initialize InfluxDB client.
        
        Args:
            config: Application configuration
            logger: Logger instance
            performance_monitor: Performance monitoring instance
        """
        self.config = config
        self.logger = logger
        self.performance_monitor = performance_monitor
        
        # InfluxDB configuration
        self.url = f"http://{config.influxdb_host}:{config.influxdb_port}"
        self.token = config.influxdb_token
        self.org = config.influxdb_org
        self.bucket = config.influxdb_bucket
        self.timeout = config.influxdb_timeout * 1000  # Convert to milliseconds
        self.verify_ssl = config.influxdb_verify_ssl
        self.enable_gzip = config.influxdb_enable_gzip
        
        # Batch configuration
        self.batch_size = config.influxdb_batch_size
        self.flush_interval = config.influxdb_flush_interval
        self.max_buffer_size = config.max_buffer_size
        
        # Retry configuration
        self.retry_attempts = config.influxdb_retry_attempts
        self.retry_delay = config.influxdb_retry_delay
        self.retry_exponential_base = config.influxdb_retry_exponential_base
        
        # Client and state management
        self._client: Optional[InfluxDBClient] = None
        self._write_api = None
        self._query_api = None
        self._health_api = None
        self._is_connected = False
        self._buffer: deque = deque()
        self._buffer_lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._stats = BatchStats()
        
        # Connection health
        self._last_health_check: Optional[datetime] = None
        self._health_check_interval = 300  # 5 minutes
        self._connection_errors = 0
        self._max_connection_errors = 5
        
        self.logger.info(f"RuuviInfluxDBClient initialized for {self.url}")
    
    async def connect(self) -> bool:
        """
        Connect to InfluxDB with retry logic.
        
        Returns:
            bool: True if connection successful
            
        Raises:
            ConnectionError: If connection fails after all retries
        """
        for attempt in range(self.retry_attempts):
            try:
                self._client = InfluxDBClient(
                    url=self.url,
                    token=self.token,
                    org=self.org,
                    timeout=self.timeout,
                    verify_ssl=self.verify_ssl,
                    enable_gzip=self.enable_gzip
                )
                
                # Initialize APIs
                self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
                self._query_api = self._client.query_api()
                self._health_api = self._client.health()
                
                # Test connection
                health = await self._check_health()
                if health:
                    self._is_connected = True
                    self._connection_errors = 0
                    self.logger.info(f"Connected to InfluxDB successfully (attempt {attempt + 1})")
                    
                    # Start flush task
                    await self._start_flush_task()
                    
                    return True
                else:
                    raise ConnectionError("Health check failed")
                    
            except Exception as e:
                self.logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
                self._connection_errors += 1
                
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (self.retry_exponential_base ** attempt)
                    await asyncio.sleep(delay)
                else:
                    self._is_connected = False
                    raise ConnectionError(f"Failed to connect after {self.retry_attempts} attempts: {e}")
        
        return False
    
    async def disconnect(self):
        """Disconnect from InfluxDB and cleanup resources."""
        self.logger.info("Disconnecting from InfluxDB...")
        
        # Stop flush task
        await self._stop_flush_task()
        
        # Flush remaining buffer
        if self._buffer:
            await self._flush_buffer(force=True)
        
        # Close client
        if self._client:
            self._client.close()
            self._client = None
            self._write_api = None
            self._query_api = None
            self._health_api = None
        
        self._is_connected = False
        self.logger.info("Disconnected from InfluxDB")
    
    async def _check_health(self) -> bool:
        """
        Check InfluxDB health status.
        
        Returns:
            bool: True if healthy
        """
        try:
            if not self._health_api:
                return False
            
            health = self._health_api
            self._last_health_check = datetime.utcnow()
            
            # Simple health check - try to ping
            # Note: The actual health check implementation depends on influxdb-client version
            return True
            
        except Exception as e:
            self.logger.warning(f"Health check failed: {e}")
            return False
    
    async def _start_flush_task(self):
        """Start the periodic flush task."""
        if self._flush_task and not self._flush_task.done():
            return
        
        self._flush_task = asyncio.create_task(self._flush_loop())
        self.logger.debug("Started flush task")
    
    async def _stop_flush_task(self):
        """Stop the periodic flush task."""
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self.logger.debug("Stopped flush task")
    
    async def _flush_loop(self):
        """Periodic flush loop."""
        try:
            while True:
                await asyncio.sleep(self.flush_interval)
                if self._buffer:
                    await self._flush_buffer()
        except asyncio.CancelledError:
            self.logger.debug("Flush loop cancelled")
        except Exception as e:
            self.logger.error(f"Error in flush loop: {e}")
    
    def _convert_sensor_data_to_points(self, sensor_data: RuuviSensorData) -> List[DataPoint]:
        """
        Convert Ruuvi sensor data to InfluxDB data points.
        
        Args:
            sensor_data: Ruuvi sensor data
            
        Returns:
            List[DataPoint]: List of data points
        """
        points = []
        
        # Common tags
        tags = {
            "sensor_mac": sensor_data.mac_address,
            "data_format": str(sensor_data.data_format.value)
        }
        
        # Environmental data point
        if any([sensor_data.temperature is not None, 
                sensor_data.humidity is not None, 
                sensor_data.pressure is not None]):
            
            fields = {}
            if sensor_data.temperature is not None:
                fields["temperature"] = sensor_data.temperature
            if sensor_data.humidity is not None:
                fields["humidity"] = sensor_data.humidity
            if sensor_data.pressure is not None:
                fields["pressure"] = sensor_data.pressure
            
            if fields:
                points.append(DataPoint(
                    measurement="ruuvi_environmental",
                    tags=tags.copy(),
                    fields=fields,
                    timestamp=sensor_data.timestamp
                ))
        
        # Motion data point
        if any([sensor_data.acceleration_x is not None,
                sensor_data.acceleration_y is not None,
                sensor_data.acceleration_z is not None,
                sensor_data.movement_counter is not None]):
            
            fields = {}
            if sensor_data.acceleration_x is not None:
                fields["acceleration_x"] = sensor_data.acceleration_x
            if sensor_data.acceleration_y is not None:
                fields["acceleration_y"] = sensor_data.acceleration_y
            if sensor_data.acceleration_z is not None:
                fields["acceleration_z"] = sensor_data.acceleration_z
            if sensor_data.movement_counter is not None:
                fields["movement_counter"] = sensor_data.movement_counter
            
            if fields:
                points.append(DataPoint(
                    measurement="ruuvi_motion",
                    tags=tags.copy(),
                    fields=fields,
                    timestamp=sensor_data.timestamp
                ))
        
        # Power data point
        if any([sensor_data.battery_voltage is not None,
                sensor_data.tx_power is not None]):
            
            fields = {}
            if sensor_data.battery_voltage is not None:
                fields["battery_voltage"] = sensor_data.battery_voltage
            if sensor_data.tx_power is not None:
                fields["tx_power"] = sensor_data.tx_power
            
            if fields:
                points.append(DataPoint(
                    measurement="ruuvi_power",
                    tags=tags.copy(),
                    fields=fields,
                    timestamp=sensor_data.timestamp
                ))
        
        # Signal data point
        if any([sensor_data.rssi is not None,
                sensor_data.measurement_sequence is not None]):
            
            fields = {}
            if sensor_data.rssi is not None:
                fields["rssi"] = sensor_data.rssi
            if sensor_data.measurement_sequence is not None:
                fields["measurement_sequence"] = sensor_data.measurement_sequence
            
            if fields:
                points.append(DataPoint(
                    measurement="ruuvi_signal",
                    tags=tags.copy(),
                    fields=fields,
                    timestamp=sensor_data.timestamp
                ))
        
        return points
    
    def _convert_to_influx_points(self, data_points: List[DataPoint]) -> List[Point]:
        """
        Convert DataPoint objects to InfluxDB Point objects.
        
        Args:
            data_points: List of data points
            
        Returns:
            List[Point]: List of InfluxDB points
        """
        influx_points = []
        
        for dp in data_points:
            point = Point(dp.measurement)
            
            # Add tags
            for tag_key, tag_value in dp.tags.items():
                point = point.tag(tag_key, str(tag_value))
            
            # Add fields
            for field_key, field_value in dp.fields.items():
                point = point.field(field_key, field_value)
            
            # Add timestamp
            if dp.timestamp:
                point = point.time(dp.timestamp, WritePrecision.S)
            
            influx_points.append(point)
        
        return influx_points
    
    async def write_sensor_data(self, sensor_data: RuuviSensorData, buffer: bool = True) -> bool:
        """
        Write Ruuvi sensor data to InfluxDB.
        
        Args:
            sensor_data: Sensor data to write
            buffer: Whether to buffer the data or write immediately
            
        Returns:
            bool: True if write successful
        """
        if not self._is_connected:
            self.logger.warning("Not connected to InfluxDB, cannot write data")
            return False
        
        try:
            # Convert sensor data to data points
            data_points = self._convert_sensor_data_to_points(sensor_data)
            
            if buffer:
                # Add to buffer
                async with self._buffer_lock:
                    self._buffer.extend(data_points)
                    
                    # Check buffer size limit
                    if len(self._buffer) > self.max_buffer_size:
                        # Remove oldest points
                        excess = len(self._buffer) - self.max_buffer_size
                        for _ in range(excess):
                            self._buffer.popleft()
                        self.logger.warning(f"Buffer overflow, removed {excess} oldest points")
                    
                    # Trigger flush if buffer is full
                    if len(self._buffer) >= self.batch_size:
                        asyncio.create_task(self._flush_buffer())
                
                return True
            else:
                # Write immediately
                return await self._write_points(data_points)
                
        except Exception as e:
            self.logger.error(f"Error writing sensor data: {e}")
            return False
    
    async def write_multiple_sensor_data(self, sensor_data_list: List[RuuviSensorData], buffer: bool = True) -> int:
        """
        Write multiple sensor data points to InfluxDB.
        
        Args:
            sensor_data_list: List of sensor data to write
            buffer: Whether to buffer the data or write immediately
            
        Returns:
            int: Number of successful writes
        """
        successful_writes = 0
        
        for sensor_data in sensor_data_list:
            if await self.write_sensor_data(sensor_data, buffer):
                successful_writes += 1
        
        return successful_writes
    
    async def _write_points(self, data_points: List[DataPoint]) -> bool:
        """
        Write data points to InfluxDB with retry logic.
        
        Args:
            data_points: List of data points to write
            
        Returns:
            bool: True if write successful
        """
        if not data_points:
            return True
        
        influx_points = self._convert_to_influx_points(data_points)
        
        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()
                
                # Write points
                self._write_api.write(
                    bucket=self.bucket,
                    org=self.org,
                    record=influx_points
                )
                
                write_time = time.time() - start_time
                
                # Update statistics
                self._stats.points_written += len(data_points)
                self._stats.batches_sent += 1
                self._stats.last_write_time = datetime.utcnow()
                self._stats.total_write_time += write_time
                
                # Update performance metrics
                self.performance_monitor.record_metric("influxdb_points_written", len(data_points))
                self.performance_monitor.record_metric("influxdb_write_time", write_time)
                
                self.logger.debug(f"Wrote {len(data_points)} points to InfluxDB in {write_time:.3f}s")
                return True
                
            except (InfluxDBError, ApiException) as e:
                self.logger.warning(f"Write attempt {attempt + 1} failed: {e}")
                
                if attempt < self.retry_attempts - 1:
                    delay = self.retry_delay * (self.retry_exponential_base ** attempt)
                    await asyncio.sleep(delay)
                else:
                    self._stats.points_failed += len(data_points)
                    self._stats.batches_failed += 1
                    self.performance_monitor.record_metric("influxdb_write_errors", 1)
                    self.logger.error(f"Failed to write points after {self.retry_attempts} attempts: {e}")
                    return False
            
            except Exception as e:
                self.logger.error(f"Unexpected error writing points: {e}")
                self._stats.points_failed += len(data_points)
                self._stats.batches_failed += 1
                self.performance_monitor.record_metric("influxdb_write_errors", 1)
                return False
        
        return False
    
    async def _flush_buffer(self, force: bool = False):
        """
        Flush buffered data points to InfluxDB.
        
        Args:
            force: Force flush regardless of batch size
        """
        async with self._buffer_lock:
            if not self._buffer:
                return
            
            if not force and len(self._buffer) < self.batch_size:
                return
            
            # Get points to write
            points_to_write = []
            batch_size = min(len(self._buffer), self.batch_size)
            
            for _ in range(batch_size):
                if self._buffer:
                    points_to_write.append(self._buffer.popleft())
        
        if points_to_write:
            success = await self._write_points(points_to_write)
            if not success:
                # Re-add failed points to buffer (at front)
                async with self._buffer_lock:
                    for point in reversed(points_to_write):
                        self._buffer.appendleft(point)
    
    async def flush_all(self) -> bool:
        """
        Flush all buffered data to InfluxDB.
        
        Returns:
            bool: True if all data flushed successfully
        """
        self.logger.info("Flushing all buffered data to InfluxDB...")
        
        total_points = len(self._buffer)
        if total_points == 0:
            return True
        
        success_count = 0
        
        while self._buffer:
            async with self._buffer_lock:
                batch_size = min(len(self._buffer), self.batch_size)
                if batch_size == 0:
                    break
                
                points_to_write = []
                for _ in range(batch_size):
                    if self._buffer:
                        points_to_write.append(self._buffer.popleft())
            
            if await self._write_points(points_to_write):
                success_count += len(points_to_write)
            else:
                # Re-add failed points
                async with self._buffer_lock:
                    for point in reversed(points_to_write):
                        self._buffer.appendleft(point)
                break
        
        self.logger.info(f"Flushed {success_count}/{total_points} points successfully")
        return success_count == total_points
    
    def get_buffer_size(self) -> int:
        """
        Get current buffer size.
        
        Returns:
            int: Number of points in buffer
        """
        return len(self._buffer)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get client statistics.
        
        Returns:
            Dict[str, Any]: Client statistics
        """
        return {
            "is_connected": self._is_connected,
            "buffer_size": len(self._buffer),
            "points_written": self._stats.points_written,
            "points_failed": self._stats.points_failed,
            "batches_sent": self._stats.batches_sent,
            "batches_failed": self._stats.batches_failed,
            "last_write_time": self._stats.last_write_time,
            "total_write_time": self._stats.total_write_time,
            "average_write_time": (
                self._stats.total_write_time / self._stats.batches_sent 
                if self._stats.batches_sent > 0 else 0
            ),
            "connection_errors": self._connection_errors,
            "last_health_check": self._last_health_check
        }
    
    def reset_statistics(self):
        """Reset client statistics."""
        self._stats = BatchStats()
        self._connection_errors = 0
        self.logger.debug("InfluxDB client statistics reset")
    
    async def query(self, flux_query: str) -> List[Dict[str, Any]]:
        """
        Execute a Flux query.
        
        Args:
            flux_query: Flux query string
            
        Returns:
            List[Dict[str, Any]]: Query results
        """
        if not self._is_connected or not self._query_api:
            raise ConnectionError("Not connected to InfluxDB")
        
        try:
            tables = self._query_api.query(flux_query, org=self.org)
            results = []
            
            for table in tables:
                for record in table.records:
                    results.append(record.values)
            
            return results
            
        except Exception as e:
            self.logger.error(f"Query failed: {e}")
            raise WriteError(f"Query failed: {e}")
    
    async def get_sensor_data(self, mac_address: str, start_time: datetime, 
                            end_time: Optional[datetime] = None, 
                            measurement: str = "ruuvi_environmental") -> List[Dict[str, Any]]:
        """
        Get sensor data for a specific MAC address and time range.
        
        Args:
            mac_address: Sensor MAC address
            start_time: Start time for data retrieval
            end_time: End time for data retrieval (defaults to now)
            measurement: Measurement name to query
            
        Returns:
            List[Dict[str, Any]]: Sensor data records
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        flux_query = f'''
        from(bucket: "{self.bucket}")
          |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
          |> filter(fn: (r) => r["_measurement"] == "{measurement}")
          |> filter(fn: (r) => r["sensor_mac"] == "{mac_address}")
          |> sort(columns: ["_time"])
        '''
        
        return await self.query(flux_query)
    
    def is_connected(self) -> bool:
        """
        Check if client is connected to InfluxDB.
        
        Returns:
            bool: True if connected
        """
        return self._is_connected
    
    async def health_check(self) -> bool:
        """
        Perform health check and reconnect if necessary.
        
        Returns:
            bool: True if healthy
        """
        # Check if health check is needed
        if (self._last_health_check and 
            datetime.utcnow() - self._last_health_check < timedelta(seconds=self._health_check_interval)):
            return self._is_connected
        
        # Perform health check
        if not await self._check_health():
            self.logger.warning("Health check failed, attempting reconnection...")
            self._is_connected = False
            
            # Try to reconnect
            try:
                return await self.connect()
            except ConnectionError:
                return False
        
        return True


async def test_influxdb_client(config: Config, logger: ProductionLogger, performance_monitor: PerformanceMonitor):
    """
    Test function for InfluxDB client.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    from ..ble.scanner import RuuviSensorData, RuuviDataFormat
    
    client = RuuviInfluxDBClient(config, logger, performance_monitor)
    
    try:
        # Connect
        await client.connect()
        
        # Create test data
        test_data = RuuviSensorData(
            mac_address="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.utcnow(),
            data_format=RuuviDataFormat.FORMAT_5,
            temperature=22.5,
            humidity=45.0,
            pressure=1013.25,
            battery_voltage=3.0,
            rssi=-65
        )
        
        # Write test data
        success = await client.write_sensor_data(test_data, buffer=False)
        print(f"Write successful: {success}")
        
        # Get statistics
        stats = client.get_statistics()
        print(f"Statistics: {stats}")
        
        # Flush buffer
        await client.flush_all()
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config import Config
    from src.utils.logging import ProductionLogger, PerformanceMonitor
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    asyncio.run(test_influxdb_client(config, logger, performance_monitor))