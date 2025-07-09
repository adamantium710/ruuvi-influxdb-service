"""
Weather data storage module for InfluxDB operations.
Extends existing InfluxDB client patterns for weather forecast data.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from influxdb_client import Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.rest import ApiException

from .api import WeatherData, ForecastData
from ..influxdb.client import RuuviInfluxDBClient, DataPoint
from ..utils.config import Config
from ..utils.logging import ProductionLogger, PerformanceMonitor


@dataclass
class WeatherStorageStats:
    """Statistics for weather storage operations."""
    forecasts_written: int = 0
    forecasts_failed: int = 0
    historical_written: int = 0
    historical_failed: int = 0
    last_write_time: Optional[datetime] = None
    total_write_time: float = 0.0


class WeatherStorageError(Exception):
    """Base exception for weather storage operations."""
    pass


class WeatherStorage:
    """
    Weather data storage manager for InfluxDB operations.
    
    Features:
    - Extends existing InfluxDB client patterns
    - Specialized weather data point conversion
    - Batch writing with retry logic
    - Performance monitoring and statistics
    - Support for forecast and historical data
    """
    
    def __init__(self, config: Config, logger: ProductionLogger, 
                 performance_monitor: PerformanceMonitor, 
                 influxdb_client: Optional[RuuviInfluxDBClient] = None):
        """
        Initialize weather storage manager.
        
        Args:
            config: Application configuration
            logger: Logger instance
            performance_monitor: Performance monitoring instance
            influxdb_client: Optional existing InfluxDB client
        """
        self.config = config
        self.logger = logger
        self.performance_monitor = performance_monitor
        
        # Use existing client or create new one
        if influxdb_client:
            self.influxdb_client = influxdb_client
            self._owns_client = False
        else:
            self.influxdb_client = RuuviInfluxDBClient(config, logger, performance_monitor)
            self._owns_client = True
        
        # Weather-specific configuration
        self.weather_bucket = config.weather_influxdb_bucket
        self.measurement_name = "weather_forecasts"
        self.error_measurement_name = "weather_forecast_errors"
        
        # Statistics
        self._stats = WeatherStorageStats()
        
        self.logger.info(f"WeatherStorage initialized with bucket: {self.weather_bucket}")
    
    async def connect(self) -> bool:
        """
        Connect to InfluxDB if we own the client.
        
        Returns:
            bool: True if connection successful
        """
        if self._owns_client:
            return await self.influxdb_client.connect()
        return self.influxdb_client.is_connected()
    
    async def disconnect(self):
        """Disconnect from InfluxDB if we own the client."""
        if self._owns_client:
            await self.influxdb_client.disconnect()
    
    def prepare_forecast_for_influxdb(self, forecast_data: ForecastData) -> List[DataPoint]:
        """
        Convert forecast data to InfluxDB data points.
        
        Args:
            forecast_data: Forecast data to convert
            
        Returns:
            List[DataPoint]: List of InfluxDB data points
        """
        data_points = []
        
        # Common tags for all points
        base_tags = {
            "location_lat": str(forecast_data.location_latitude),
            "location_lon": str(forecast_data.location_longitude),
            "timezone": forecast_data.timezone,
            "retrieved_at": forecast_data.retrieved_at.isoformat()
        }
        
        # Process current weather if available
        if forecast_data.current_weather:
            current_point = self._convert_weather_data_to_point(
                forecast_data.current_weather, 
                base_tags.copy(),
                data_type="current"
            )
            if current_point:
                data_points.append(current_point)
        
        # Process hourly forecasts
        for weather_data in forecast_data.hourly_forecasts:
            forecast_point = self._convert_weather_data_to_point(
                weather_data,
                base_tags.copy(),
                data_type="forecast" if weather_data.is_forecast else "historical"
            )
            if forecast_point:
                data_points.append(forecast_point)
        
        # Process daily forecasts if available
        for weather_data in forecast_data.daily_forecasts:
            daily_point = self._convert_weather_data_to_point(
                weather_data,
                base_tags.copy(),
                data_type="daily_forecast"
            )
            if daily_point:
                data_points.append(daily_point)
        
        self.logger.debug(f"Prepared {len(data_points)} weather data points for InfluxDB")
        return data_points
    
    def _convert_weather_data_to_point(self, weather_data: WeatherData, 
                                     base_tags: Dict[str, str], 
                                     data_type: str) -> Optional[DataPoint]:
        """
        Convert single weather data point to InfluxDB data point.
        
        Args:
            weather_data: Weather data to convert
            base_tags: Base tags to include
            data_type: Type of data (current, forecast, historical, daily_forecast)
            
        Returns:
            Optional[DataPoint]: InfluxDB data point or None if invalid
        """
        try:
            # Add data type tag
            tags = base_tags.copy()
            tags["data_type"] = data_type
            tags["is_forecast"] = str(weather_data.is_forecast).lower()
            
            # Build fields dictionary with all available weather parameters
            fields = {}
            
            # Core weather parameters
            if weather_data.temperature is not None:
                fields["temperature"] = float(weather_data.temperature)
            if weather_data.humidity is not None:
                fields["humidity"] = float(weather_data.humidity)
            if weather_data.pressure is not None:
                fields["pressure"] = float(weather_data.pressure)
            
            # Wind parameters
            if weather_data.wind_speed is not None:
                fields["wind_speed"] = float(weather_data.wind_speed)
            if weather_data.wind_direction is not None:
                fields["wind_direction"] = float(weather_data.wind_direction)
            
            # Precipitation and cloud cover
            if weather_data.precipitation is not None:
                fields["precipitation"] = float(weather_data.precipitation)
            if weather_data.cloud_cover is not None:
                fields["cloud_cover"] = float(weather_data.cloud_cover)
            
            # Optional parameters
            if weather_data.visibility is not None:
                fields["visibility"] = float(weather_data.visibility)
            if weather_data.uv_index is not None:
                fields["uv_index"] = float(weather_data.uv_index)
            if weather_data.weather_code is not None:
                fields["weather_code"] = int(weather_data.weather_code)
            
            # Ensure we have at least some fields
            if not fields:
                self.logger.warning("No valid fields found in weather data point")
                return None
            
            return DataPoint(
                measurement=self.measurement_name,
                tags=tags,
                fields=fields,
                timestamp=weather_data.timestamp
            )
            
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error converting weather data to point: {e}")
            return None
    
    async def write_forecast_to_influxdb(self, forecast_data: ForecastData, 
                                       buffer: bool = True) -> bool:
        """
        Write forecast data to InfluxDB.
        
        Args:
            forecast_data: Forecast data to write
            buffer: Whether to buffer the data or write immediately
            
        Returns:
            bool: True if write successful
        """
        if not self.influxdb_client.is_connected():
            self.logger.warning("InfluxDB client not connected, cannot write weather data")
            return False
        
        try:
            start_time = time.time()
            
            # Convert forecast data to InfluxDB points
            data_points = self.prepare_forecast_for_influxdb(forecast_data)
            
            if not data_points:
                self.logger.warning("No valid data points to write")
                return False
            
            # Write points using the existing InfluxDB client pattern
            success = await self._write_weather_points(data_points, buffer)
            
            write_time = time.time() - start_time
            
            # Update statistics
            if success:
                self._stats.forecasts_written += len(data_points)
                self._stats.last_write_time = datetime.utcnow()
                self._stats.total_write_time += write_time
                
                # Update performance metrics
                self.performance_monitor.record_metric("weather_points_written", len(data_points))
                self.performance_monitor.record_metric("weather_write_time", write_time)
                
                self.logger.info(f"Successfully wrote {len(data_points)} weather points in {write_time:.3f}s")
            else:
                self._stats.forecasts_failed += len(data_points)
                self.performance_monitor.record_metric("weather_write_errors", 1)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error writing forecast data: {e}")
            self._stats.forecasts_failed += 1
            self.performance_monitor.record_metric("weather_write_errors", 1)
            return False
    
    async def _write_weather_points(self, data_points: List[DataPoint], buffer: bool = True) -> bool:
        """
        Write weather data points using the existing InfluxDB client.
        
        Args:
            data_points: List of data points to write
            buffer: Whether to buffer the data
            
        Returns:
            bool: True if write successful
        """
        if not data_points:
            return True
        
        try:
            # Convert to InfluxDB points
            influx_points = self.influxdb_client._convert_to_influx_points(data_points)
            
            if buffer:
                # Add to existing buffer system
                async with self.influxdb_client._buffer_lock:
                    self.influxdb_client._buffer.extend(data_points)
                    
                    # Check buffer size limit
                    if len(self.influxdb_client._buffer) > self.influxdb_client.max_buffer_size:
                        excess = len(self.influxdb_client._buffer) - self.influxdb_client.max_buffer_size
                        for _ in range(excess):
                            self.influxdb_client._buffer.popleft()
                        self.logger.warning(f"Buffer overflow, removed {excess} oldest points")
                    
                    # Trigger flush if buffer is full
                    if len(self.influxdb_client._buffer) >= self.influxdb_client.batch_size:
                        asyncio.create_task(self.influxdb_client._flush_buffer())
                
                return True
            else:
                # Write immediately using weather bucket
                return await self._write_points_to_weather_bucket(influx_points)
                
        except Exception as e:
            self.logger.error(f"Error writing weather points: {e}")
            return False
    
    async def _write_points_to_weather_bucket(self, influx_points: List[Point]) -> bool:
        """
        Write points directly to weather bucket.
        
        Args:
            influx_points: List of InfluxDB points
            
        Returns:
            bool: True if write successful
        """
        for attempt in range(self.influxdb_client.retry_attempts):
            try:
                # Write points to weather bucket
                self.influxdb_client._write_api.write(
                    bucket=self.weather_bucket,
                    org=self.influxdb_client.org,
                    record=influx_points
                )
                
                return True
                
            except (InfluxDBError, ApiException) as e:
                self.logger.warning(f"Weather write attempt {attempt + 1} failed: {e}")
                
                if attempt < self.influxdb_client.retry_attempts - 1:
                    delay = (self.influxdb_client.retry_delay * 
                           (self.influxdb_client.retry_exponential_base ** attempt))
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"Failed to write weather points after {self.influxdb_client.retry_attempts} attempts: {e}")
                    return False
            
            except Exception as e:
                self.logger.error(f"Unexpected error writing weather points: {e}")
                return False
        
        return False
    
    async def write_multiple_forecasts(self, forecast_list: List[ForecastData], 
                                     buffer: bool = True) -> int:
        """
        Write multiple forecast data sets to InfluxDB.
        
        Args:
            forecast_list: List of forecast data to write
            buffer: Whether to buffer the data
            
        Returns:
            int: Number of successful writes
        """
        successful_writes = 0
        
        for forecast_data in forecast_list:
            if await self.write_forecast_to_influxdb(forecast_data, buffer):
                successful_writes += 1
        
        return successful_writes
    
    async def query_weather_data(self, start_time: datetime, 
                               end_time: Optional[datetime] = None,
                               data_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query weather data from InfluxDB.
        
        Args:
            start_time: Start time for data retrieval
            end_time: End time for data retrieval (defaults to now)
            data_type: Filter by data type (current, forecast, historical)
            
        Returns:
            List[Dict[str, Any]]: Weather data records
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        # Build Flux query
        flux_query = f'''
        from(bucket: "{self.weather_bucket}")
          |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
          |> filter(fn: (r) => r["_measurement"] == "{self.measurement_name}")
        '''
        
        if data_type:
            flux_query += f'  |> filter(fn: (r) => r["data_type"] == "{data_type}")\n'
        
        flux_query += '  |> sort(columns: ["_time"])'
        
        try:
            return await self.influxdb_client.query(flux_query)
        except Exception as e:
            self.logger.error(f"Error querying weather data: {e}")
            raise WeatherStorageError(f"Query failed: {e}")
    
    async def get_latest_forecast(self, data_type: str = "forecast") -> Optional[Dict[str, Any]]:
        """
        Get the latest forecast data.
        
        Args:
            data_type: Type of data to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Latest forecast data or None
        """
        try:
            # Query last 24 hours to get latest data
            start_time = datetime.utcnow() - timedelta(hours=24)
            results = await self.query_weather_data(start_time, data_type=data_type)
            
            if results:
                # Return the most recent record
                return max(results, key=lambda x: x.get('_time', ''))
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting latest forecast: {e}")
            return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get weather storage statistics.
        
        Returns:
            Dict[str, Any]: Storage statistics
        """
        return {
            "forecasts_written": self._stats.forecasts_written,
            "forecasts_failed": self._stats.forecasts_failed,
            "historical_written": self._stats.historical_written,
            "historical_failed": self._stats.historical_failed,
            "last_write_time": self._stats.last_write_time,
            "total_write_time": self._stats.total_write_time,
            "average_write_time": (
                self._stats.total_write_time / max(1, self._stats.forecasts_written + self._stats.historical_written)
            ),
            "weather_bucket": self.weather_bucket,
            "measurement_name": self.measurement_name,
            "influxdb_connected": self.influxdb_client.is_connected()
        }
    
    def reset_statistics(self):
        """Reset weather storage statistics."""
        self._stats = WeatherStorageStats()
        self.logger.debug("Weather storage statistics reset")
    
    async def health_check(self) -> bool:
        """
        Perform health check on weather storage.
        
        Returns:
            bool: True if storage is healthy
        """
        try:
            # Check InfluxDB connection
            if not self.influxdb_client.is_connected():
                return False
            
            # Try a simple query to verify bucket access
            start_time = datetime.utcnow() - timedelta(minutes=1)
            await self.query_weather_data(start_time)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Weather storage health check failed: {e}")
            return False
    
    async def cleanup_old_data(self, retention_days: int = 30) -> bool:
        """
        Clean up old weather data beyond retention period.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            bool: True if cleanup successful
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=retention_days)
            
            # Build delete query
            delete_query = f'''
            from(bucket: "{self.weather_bucket}")
              |> range(start: 1970-01-01T00:00:00Z, stop: {cutoff_time.isoformat()}Z)
              |> filter(fn: (r) => r["_measurement"] == "{self.measurement_name}")
              |> drop()
            '''
            
            # Execute delete (this would need proper delete API implementation)
            # For now, just log the intent
            self.logger.info(f"Would delete weather data older than {cutoff_time}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old weather data: {e}")
            return False


async def test_weather_storage(config: Config, logger: ProductionLogger, 
                             performance_monitor: PerformanceMonitor):
    """
    Test function for weather storage.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    from .api import WeatherData, ForecastData
    
    storage = WeatherStorage(config, logger, performance_monitor)
    
    try:
        # Connect
        await storage.connect()
        
        # Create test forecast data
        test_weather = WeatherData(
            timestamp=datetime.utcnow(),
            temperature=22.5,
            humidity=65.0,
            pressure=1013.25,
            wind_speed=5.2,
            wind_direction=180.0,
            precipitation=0.0,
            cloud_cover=25.0,
            visibility=10000.0,
            uv_index=3.0,
            weather_code=1,
            is_forecast=True
        )
        
        test_forecast = ForecastData(
            location_latitude=48.1031,
            location_longitude=11.4247,
            timezone="Europe/Berlin",
            hourly_forecasts=[test_weather]
        )
        
        # Write test data
        success = await storage.write_forecast_to_influxdb(test_forecast, buffer=False)
        print(f"Write successful: {success}")
        
        # Get statistics
        stats = storage.get_statistics()
        print(f"Statistics: {stats}")
        
        # Health check
        healthy = await storage.health_check()
        print(f"Health check: {healthy}")
        
    finally:
        await storage.disconnect()


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
    
    asyncio.run(test_weather_storage(config, logger, performance_monitor))


class WeatherErrorStorage:
    """
    Weather forecast error storage manager for InfluxDB operations.
    
    Extends the weather storage functionality to handle forecast accuracy errors
    as specified in the Phase 2 architecture plan.
    """
    
    def __init__(self, config: Config, logger: ProductionLogger,
                 performance_monitor: PerformanceMonitor,
                 influxdb_client: Optional[RuuviInfluxDBClient] = None):
        """
        Initialize weather error storage manager.
        
        Args:
            config: Application configuration
            logger: Logger instance
            performance_monitor: Performance monitoring instance
            influxdb_client: Optional existing InfluxDB client
        """
        self.config = config
        self.logger = logger
        self.performance_monitor = performance_monitor
        
        # Use existing client or create new one
        if influxdb_client:
            self.influxdb_client = influxdb_client
            self._owns_client = False
        else:
            self.influxdb_client = RuuviInfluxDBClient(config, logger, performance_monitor)
            self._owns_client = True
        
        # Error storage configuration
        self.weather_bucket = config.weather_influxdb_bucket
        self.error_measurement_name = "weather_forecast_errors"
        
        # Statistics
        self._error_stats = WeatherStorageStats()
        
        self.logger.info(f"WeatherErrorStorage initialized with bucket: {self.weather_bucket}")
    
    async def connect(self) -> bool:
        """Connect to InfluxDB if we own the client."""
        if self._owns_client:
            return await self.influxdb_client.connect()
        return self.influxdb_client.is_connected()
    
    async def disconnect(self):
        """Disconnect from InfluxDB if we own the client."""
        if self._owns_client:
            await self.influxdb_client.disconnect()
    
    def prepare_error_data_for_influxdb(self, error_data: List[Dict[str, Any]]) -> List[DataPoint]:
        """
        Convert forecast error data to InfluxDB data points.
        
        Args:
            error_data: List of error data dictionaries
            
        Returns:
            List[DataPoint]: List of InfluxDB data points
        """
        data_points = []
        
        for error_record in error_data:
            try:
                # Extract required fields
                timestamp = error_record.get('timestamp')
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                elif not isinstance(timestamp, datetime):
                    self.logger.warning(f"Invalid timestamp format: {timestamp}")
                    continue
                
                # Build tags
                tags = {
                    "source": str(error_record.get('source', 'unknown')),
                    "forecast_horizon_hours": str(error_record.get('forecast_horizon_hours', 0))
                }
                
                # Build fields for error metrics
                fields = {}
                
                # Temperature errors
                if error_record.get('temp_abs_error') is not None:
                    fields["temp_abs_error"] = float(error_record['temp_abs_error'])
                if error_record.get('temp_signed_error') is not None:
                    fields["temp_signed_error"] = float(error_record['temp_signed_error'])
                
                # Pressure errors
                if error_record.get('pressure_abs_error') is not None:
                    fields["pressure_abs_error"] = float(error_record['pressure_abs_error'])
                if error_record.get('pressure_signed_error') is not None:
                    fields["pressure_signed_error"] = float(error_record['pressure_signed_error'])
                
                # Humidity errors
                if error_record.get('humidity_abs_error') is not None:
                    fields["humidity_abs_error"] = float(error_record['humidity_abs_error'])
                if error_record.get('humidity_signed_error') is not None:
                    fields["humidity_signed_error"] = float(error_record['humidity_signed_error'])
                
                # Only create data point if we have at least one error field
                if fields:
                    data_points.append(DataPoint(
                        measurement=self.error_measurement_name,
                        tags=tags,
                        fields=fields,
                        timestamp=timestamp
                    ))
                else:
                    self.logger.warning("No valid error fields found in error record")
                    
            except (ValueError, TypeError, KeyError) as e:
                self.logger.error(f"Error converting error data to point: {e}")
                continue
        
        self.logger.debug(f"Prepared {len(data_points)} error data points for InfluxDB")
        return data_points
    
    async def write_forecast_errors_to_influxdb(self, error_data: List[Dict[str, Any]],
                                              buffer: bool = True) -> bool:
        """
        Write forecast error data to InfluxDB.
        
        Args:
            error_data: List of error data dictionaries
            buffer: Whether to buffer the data or write immediately
            
        Returns:
            bool: True if write successful
        """
        if not self.influxdb_client.is_connected():
            self.logger.warning("InfluxDB client not connected, cannot write error data")
            return False
        
        try:
            start_time = time.time()
            
            # Convert error data to InfluxDB points
            data_points = self.prepare_error_data_for_influxdb(error_data)
            
            if not data_points:
                self.logger.warning("No valid error data points to write")
                return False
            
            # Write points using the existing InfluxDB client pattern
            success = await self._write_error_points(data_points, buffer)
            
            write_time = time.time() - start_time
            
            # Update statistics
            if success:
                self._error_stats.forecasts_written += len(data_points)
                self._error_stats.last_write_time = datetime.utcnow()
                self._error_stats.total_write_time += write_time
                
                # Update performance metrics
                self.performance_monitor.record_metric("weather_error_points_written", len(data_points))
                self.performance_monitor.record_metric("weather_error_write_time", write_time)
                
                self.logger.info(f"Successfully wrote {len(data_points)} error points in {write_time:.3f}s")
            else:
                self._error_stats.forecasts_failed += len(data_points)
                self.performance_monitor.record_metric("weather_error_write_errors", 1)
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error writing forecast error data: {e}")
            self._error_stats.forecasts_failed += 1
            self.performance_monitor.record_metric("weather_error_write_errors", 1)
            return False
    
    async def _write_error_points(self, data_points: List[DataPoint], buffer: bool = True) -> bool:
        """
        Write error data points using the existing InfluxDB client.
        
        Args:
            data_points: List of data points to write
            buffer: Whether to buffer the data
            
        Returns:
            bool: True if write successful
        """
        if not data_points:
            return True
        
        try:
            # Convert to InfluxDB points
            influx_points = self.influxdb_client._convert_to_influx_points(data_points)
            
            if buffer:
                # Add to existing buffer system
                async with self.influxdb_client._buffer_lock:
                    self.influxdb_client._buffer.extend(data_points)
                    
                    # Check buffer size limit
                    if len(self.influxdb_client._buffer) > self.influxdb_client.max_buffer_size:
                        excess = len(self.influxdb_client._buffer) - self.influxdb_client.max_buffer_size
                        for _ in range(excess):
                            self.influxdb_client._buffer.popleft()
                        self.logger.warning(f"Buffer overflow, removed {excess} oldest points")
                    
                    # Trigger flush if buffer is full
                    if len(self.influxdb_client._buffer) >= self.influxdb_client.batch_size:
                        asyncio.create_task(self.influxdb_client._flush_buffer())
                
                return True
            else:
                # Write immediately using weather bucket
                return await self._write_points_to_weather_bucket(influx_points)
                
        except Exception as e:
            self.logger.error(f"Error writing error points: {e}")
            return False
    
    async def _write_points_to_weather_bucket(self, influx_points: List[Point]) -> bool:
        """
        Write points directly to weather bucket.
        
        Args:
            influx_points: List of InfluxDB points
            
        Returns:
            bool: True if write successful
        """
        for attempt in range(self.influxdb_client.retry_attempts):
            try:
                # Write points to weather bucket
                self.influxdb_client._write_api.write(
                    bucket=self.weather_bucket,
                    org=self.influxdb_client.org,
                    record=influx_points
                )
                
                return True
                
            except (InfluxDBError, ApiException) as e:
                self.logger.warning(f"Error write attempt {attempt + 1} failed: {e}")
                
                if attempt < self.influxdb_client.retry_attempts - 1:
                    delay = (self.influxdb_client.retry_delay *
                           (self.influxdb_client.retry_exponential_base ** attempt))
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"Failed to write error points after {self.influxdb_client.retry_attempts} attempts: {e}")
                    return False
            
            except Exception as e:
                self.logger.error(f"Unexpected error writing error points: {e}")
                return False
        
        return False
    
    async def query_forecast_errors(self, start_time: datetime,
                                  end_time: Optional[datetime] = None,
                                  forecast_horizon_hours: Optional[int] = None,
                                  source: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query forecast error data from InfluxDB.
        
        Args:
            start_time: Start time for data retrieval
            end_time: End time for data retrieval (defaults to now)
            forecast_horizon_hours: Filter by forecast horizon
            source: Filter by forecast source
            
        Returns:
            List[Dict[str, Any]]: Error data records
        """
        if end_time is None:
            end_time = datetime.utcnow()
        
        # Build Flux query
        flux_query = f'''
        from(bucket: "{self.weather_bucket}")
          |> range(start: {start_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
          |> filter(fn: (r) => r["_measurement"] == "{self.error_measurement_name}")
        '''
        
        if forecast_horizon_hours is not None:
            flux_query += f'  |> filter(fn: (r) => r["forecast_horizon_hours"] == "{forecast_horizon_hours}")\n'
        
        if source:
            flux_query += f'  |> filter(fn: (r) => r["source"] == "{source}")\n'
        
        flux_query += '  |> sort(columns: ["_time"])'
        
        try:
            return await self.influxdb_client.query(flux_query)
        except Exception as e:
            self.logger.error(f"Error querying forecast error data: {e}")
            raise WeatherStorageError(f"Error query failed: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get forecast error storage statistics.
        
        Returns:
            Dict[str, Any]: Error storage statistics
        """
        return {
            "errors_written": self._error_stats.forecasts_written,
            "errors_failed": self._error_stats.forecasts_failed,
            "last_write_time": self._error_stats.last_write_time,
            "total_write_time": self._error_stats.total_write_time,
            "average_write_time": (
                self._error_stats.total_write_time / max(1, self._error_stats.forecasts_written)
            ),
            "weather_bucket": self.weather_bucket,
            "error_measurement_name": self.error_measurement_name,
            "influxdb_connected": self.influxdb_client.is_connected()
        }
    
    def reset_error_statistics(self):
        """Reset forecast error storage statistics."""
        self._error_stats = WeatherStorageStats()
        self.logger.debug("Weather error storage statistics reset")
    
    async def health_check(self) -> bool:
        """
        Perform health check on weather error storage.
        
        Returns:
            bool: True if storage is healthy
        """
        try:
            # Check InfluxDB connection
            if not self.influxdb_client.is_connected():
                return False
            
            # Try a simple query to verify bucket access
            start_time = datetime.utcnow() - timedelta(minutes=1)
            await self.query_forecast_errors(start_time)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Weather error storage health check failed: {e}")
            return False


async def test_weather_error_storage(config: Config, logger: ProductionLogger,
                                   performance_monitor: PerformanceMonitor):
    """
    Test function for weather error storage.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    error_storage = WeatherErrorStorage(config, logger, performance_monitor)
    
    try:
        # Connect
        await error_storage.connect()
        
        # Create test error data
        test_errors = [
            {
                'timestamp': datetime.utcnow(),
                'forecast_horizon_hours': 24,
                'source': 'openmeteo',
                'temp_abs_error': 2.5,
                'temp_signed_error': -1.2,
                'pressure_abs_error': 5.3,
                'pressure_signed_error': 3.1,
                'humidity_abs_error': 8.7,
                'humidity_signed_error': -4.2
            }
        ]
        
        # Write test error data
        success = await error_storage.write_forecast_errors_to_influxdb(test_errors, buffer=False)
        print(f"Error write successful: {success}")
        
        # Get statistics
        stats = error_storage.get_error_statistics()
        print(f"Error statistics: {stats}")
        
        # Health check
        healthy = await error_storage.health_check()
        print(f"Error storage health check: {healthy}")
        
    finally:
        await error_storage.disconnect()