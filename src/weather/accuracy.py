"""
Weather forecast accuracy calculation module.
Implements forecast error calculations and data alignment between sensor data and forecasts.
"""

import asyncio
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from influxdb_client import Point, WritePrecision
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.rest import ApiException

from ..influxdb.client import RuuviInfluxDBClient, DataPoint
from ..utils.config import Config
from ..utils.logging import ProductionLogger, PerformanceMonitor


@dataclass
class ForecastError:
    """Forecast error data point."""
    timestamp: datetime
    forecast_horizon_hours: int
    source: str
    temp_abs_error: Optional[float] = None
    temp_signed_error: Optional[float] = None
    pressure_abs_error: Optional[float] = None
    pressure_signed_error: Optional[float] = None
    humidity_abs_error: Optional[float] = None
    humidity_signed_error: Optional[float] = None


@dataclass
class AccuracyStats:
    """Statistics for accuracy calculations."""
    errors_calculated: int = 0
    errors_stored: int = 0
    errors_failed: int = 0
    last_calculation_time: Optional[datetime] = None
    total_calculation_time: float = 0.0


class ForecastAccuracyError(Exception):
    """Base exception for forecast accuracy operations."""
    pass


def get_sensor_data_from_influxdb(
    measurement: str,
    fields: list[str],
    time_range: str = '30 days',
    group_by_interval: str = '1h',
    influxdb_client: Optional[RuuviInfluxDBClient] = None,
    config: Optional[Config] = None,
    logger: Optional[ProductionLogger] = None
) -> pd.DataFrame:
    """
    Retrieve sensor data from InfluxDB and return as pandas DataFrame.
    
    This function extends the existing InfluxDB client patterns to provide
    sensor data retrieval with time-based grouping and filtering.
    
    Args:
        measurement: InfluxDB measurement name (e.g., 'ruuvi_environmental')
        fields: List of field names to retrieve (e.g., ['temperature', 'pressure', 'humidity'])
        time_range: Time range for data retrieval (e.g., '30 days', '7d', '24h')
        group_by_interval: Grouping interval for aggregation (e.g., '1h', '15m', '5m')
        influxdb_client: Optional existing InfluxDB client
        config: Optional configuration instance
        logger: Optional logger instance
        
    Returns:
        pd.DataFrame: DataFrame with time index and sensor columns
        
    Raises:
        ForecastAccuracyError: If data retrieval fails
    """
    if influxdb_client is None:
        if config is None or logger is None:
            raise ForecastAccuracyError("Either influxdb_client or both config and logger must be provided")
        
        from ..utils.logging import PerformanceMonitor
        performance_monitor = PerformanceMonitor(logger)
        influxdb_client = RuuviInfluxDBClient(config, logger, performance_monitor)
    
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    
    try:
        # Build Flux query for sensor data retrieval
        field_filters = ' or '.join([f'r["_field"] == "{field}"' for field in fields])
        
        flux_query = f'''
        from(bucket: "{influxdb_client.bucket}")
          |> range(start: -{time_range})
          |> filter(fn: (r) => r["_measurement"] == "{measurement}")
          |> filter(fn: (r) => {field_filters})
          |> aggregateWindow(every: {group_by_interval}, fn: mean, createEmpty: false)
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''
        
        logger.debug(f"Executing sensor data query for measurement: {measurement}")
        
        # Execute query using existing client
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(influxdb_client.query(flux_query))
        finally:
            loop.close()
        
        if not results:
            logger.warning(f"No sensor data found for measurement: {measurement}")
            return pd.DataFrame()
        
        # Convert results to DataFrame
        data_rows = []
        for record in results:
            row = {'time': pd.to_datetime(record['_time'])}
            for field in fields:
                if field in record and record[field] is not None:
                    row[field] = float(record[field])
                else:
                    row[field] = None
            data_rows.append(row)
        
        df = pd.DataFrame(data_rows)
        
        if not df.empty:
            # Set time as index
            df.set_index('time', inplace=True)
            df.sort_index(inplace=True)
            
            logger.info(f"Retrieved {len(df)} sensor data points for {len(fields)} fields")
        else:
            logger.warning("No valid sensor data points found")
        
        return df
        
    except Exception as e:
        logger.error(f"Error retrieving sensor data from InfluxDB: {e}")
        raise ForecastAccuracyError(f"Sensor data retrieval failed: {e}")


class ForecastAccuracyCalculator:
    """
    Forecast accuracy calculator for weather data.
    
    Features:
    - Data alignment between sensor readings and forecasts
    - Error calculation for multiple forecast horizons
    - Batch processing with performance monitoring
    - Integration with existing InfluxDB patterns
    """
    
    def __init__(self, config: Config, logger: ProductionLogger, 
                 performance_monitor: PerformanceMonitor,
                 influxdb_client: Optional[RuuviInfluxDBClient] = None):
        """
        Initialize forecast accuracy calculator.
        
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
        self.error_measurement = "weather_forecast_errors"
        
        # Statistics
        self._stats = AccuracyStats()
        
        self.logger.info("ForecastAccuracyCalculator initialized")
    
    async def connect(self) -> bool:
        """Connect to InfluxDB if we own the client."""
        if self._owns_client:
            return await self.influxdb_client.connect()
        return self.influxdb_client.is_connected()
    
    async def disconnect(self):
        """Disconnect from InfluxDB if we own the client."""
        if self._owns_client:
            await self.influxdb_client.disconnect()
    
    def _align_sensor_and_forecast_data(self, sensor_df: pd.DataFrame, 
                                      forecast_df: pd.DataFrame,
                                      forecast_horizon_hours: int) -> pd.DataFrame:
        """
        Align sensor data with forecast data based on timestamps and forecast horizon.
        
        Args:
            sensor_df: DataFrame with sensor data (time index)
            forecast_df: DataFrame with forecast data (time index)
            forecast_horizon_hours: Forecast horizon in hours
            
        Returns:
            pd.DataFrame: Aligned data with sensor and forecast columns
        """
        try:
            # Create forecast horizon offset
            forecast_offset = pd.Timedelta(hours=forecast_horizon_hours)
            
            # Shift forecast timestamps back by horizon to align with actual times
            forecast_aligned = forecast_df.copy()
            forecast_aligned.index = forecast_aligned.index - forecast_offset
            
            # Merge sensor and forecast data on aligned timestamps
            aligned_df = pd.merge(
                sensor_df, 
                forecast_aligned, 
                left_index=True, 
                right_index=True, 
                how='inner',
                suffixes=('_actual', '_forecast')
            )
            
            self.logger.debug(f"Aligned {len(aligned_df)} data points for {forecast_horizon_hours}h horizon")
            return aligned_df
            
        except Exception as e:
            self.logger.error(f"Error aligning sensor and forecast data: {e}")
            return pd.DataFrame()
    
    def _calculate_errors(self, aligned_df: pd.DataFrame, 
                         forecast_horizon_hours: int,
                         source: str = "openmeteo") -> List[ForecastError]:
        """
        Calculate forecast errors from aligned data.
        
        Args:
            aligned_df: DataFrame with aligned sensor and forecast data
            forecast_horizon_hours: Forecast horizon in hours
            source: Forecast data source
            
        Returns:
            List[ForecastError]: List of calculated forecast errors
        """
        errors = []
        
        for timestamp, row in aligned_df.iterrows():
            try:
                error = ForecastError(
                    timestamp=timestamp,
                    forecast_horizon_hours=forecast_horizon_hours,
                    source=source
                )
                
                # Temperature errors
                if ('temperature_actual' in row and 'temperature_forecast' in row and
                    pd.notna(row['temperature_actual']) and pd.notna(row['temperature_forecast'])):
                    actual_temp = float(row['temperature_actual'])
                    forecast_temp = float(row['temperature_forecast'])
                    error.temp_abs_error = abs(actual_temp - forecast_temp)
                    error.temp_signed_error = forecast_temp - actual_temp
                
                # Pressure errors
                if ('pressure_actual' in row and 'pressure_forecast' in row and
                    pd.notna(row['pressure_actual']) and pd.notna(row['pressure_forecast'])):
                    actual_pressure = float(row['pressure_actual'])
                    forecast_pressure = float(row['pressure_forecast'])
                    error.pressure_abs_error = abs(actual_pressure - forecast_pressure)
                    error.pressure_signed_error = forecast_pressure - actual_pressure
                
                # Humidity errors
                if ('humidity_actual' in row and 'humidity_forecast' in row and
                    pd.notna(row['humidity_actual']) and pd.notna(row['humidity_forecast'])):
                    actual_humidity = float(row['humidity_actual'])
                    forecast_humidity = float(row['humidity_forecast'])
                    error.humidity_abs_error = abs(actual_humidity - forecast_humidity)
                    error.humidity_signed_error = forecast_humidity - actual_humidity
                
                # Only add error if at least one metric was calculated
                if any([error.temp_abs_error is not None,
                       error.pressure_abs_error is not None,
                       error.humidity_abs_error is not None]):
                    errors.append(error)
                    
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error calculating forecast error for timestamp {timestamp}: {e}")
                continue
        
        self.logger.debug(f"Calculated {len(errors)} forecast errors for {forecast_horizon_hours}h horizon")
        return errors
    
    def _convert_errors_to_datapoints(self, errors: List[ForecastError]) -> List[DataPoint]:
        """
        Convert forecast errors to InfluxDB data points.
        
        Args:
            errors: List of forecast errors
            
        Returns:
            List[DataPoint]: List of InfluxDB data points
        """
        data_points = []
        
        for error in errors:
            try:
                # Build tags
                tags = {
                    "source": error.source,
                    "forecast_horizon_hours": str(error.forecast_horizon_hours)
                }
                
                # Build fields
                fields = {}
                if error.temp_abs_error is not None:
                    fields["temp_abs_error"] = float(error.temp_abs_error)
                if error.temp_signed_error is not None:
                    fields["temp_signed_error"] = float(error.temp_signed_error)
                if error.pressure_abs_error is not None:
                    fields["pressure_abs_error"] = float(error.pressure_abs_error)
                if error.pressure_signed_error is not None:
                    fields["pressure_signed_error"] = float(error.pressure_signed_error)
                if error.humidity_abs_error is not None:
                    fields["humidity_abs_error"] = float(error.humidity_abs_error)
                if error.humidity_signed_error is not None:
                    fields["humidity_signed_error"] = float(error.humidity_signed_error)
                
                if fields:  # Only create point if we have fields
                    data_points.append(DataPoint(
                        measurement=self.error_measurement,
                        tags=tags,
                        fields=fields,
                        timestamp=error.timestamp
                    ))
                    
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Error converting forecast error to data point: {e}")
                continue
        
        return data_points
    
    async def _write_error_points(self, data_points: List[DataPoint], 
                                bucket: str) -> bool:
        """
        Write forecast error data points to InfluxDB.
        
        Args:
            data_points: List of data points to write
            bucket: InfluxDB bucket name
            
        Returns:
            bool: True if write successful
        """
        if not data_points:
            return True
        
        try:
            # Convert to InfluxDB points
            influx_points = self.influxdb_client._convert_to_influx_points(data_points)
            
            # Write points to specified bucket
            for attempt in range(self.influxdb_client.retry_attempts):
                try:
                    self.influxdb_client._write_api.write(
                        bucket=bucket,
                        org=self.influxdb_client.org,
                        record=influx_points
                    )
                    
                    self.logger.debug(f"Wrote {len(data_points)} error points to bucket: {bucket}")
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
            
        except Exception as e:
            self.logger.error(f"Error writing forecast error points: {e}")
            return False
    
    async def calculate_and_store_forecast_errors(self,
                                                bucket_sensor: str,
                                                bucket_forecast: str,
                                                bucket_errors: str,
                                                org: str,
                                                lookback_time: str = '48h') -> None:
        """
        Calculate and store forecast errors by comparing sensor data with forecasts.
        
        This function implements the core forecast accuracy calculation as specified
        in Phase 2, including data alignment and error storage.
        
        Args:
            bucket_sensor: InfluxDB bucket containing sensor data
            bucket_forecast: InfluxDB bucket containing forecast data
            bucket_errors: InfluxDB bucket for storing calculated errors
            org: InfluxDB organization
            lookback_time: Time range to look back for calculations (e.g., '48h', '7d')
            
        Raises:
            ForecastAccuracyError: If calculation or storage fails
        """
        if not self.influxdb_client.is_connected():
            raise ForecastAccuracyError("InfluxDB client not connected")
        
        start_time = time.time()
        
        try:
            self.logger.info(f"Starting forecast accuracy calculation for {lookback_time} lookback")
            
            # Define forecast horizons to calculate (1h, 6h, 24h, 48h)
            forecast_horizons = [1, 6, 24, 48]
            
            # Get sensor data
            sensor_df = get_sensor_data_from_influxdb(
                measurement="ruuvi_environmental",
                fields=["temperature", "pressure", "humidity"],
                time_range=lookback_time,
                group_by_interval="1h",
                influxdb_client=self.influxdb_client,
                logger=self.logger
            )
            
            if sensor_df.empty:
                self.logger.warning("No sensor data found for accuracy calculation")
                return
            
            # Get forecast data
            forecast_query = f'''
            from(bucket: "{bucket_forecast}")
              |> range(start: -{lookback_time})
              |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
              |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "pressure" or r["_field"] == "humidity")
              |> filter(fn: (r) => r["data_type"] == "forecast")
              |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
              |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
              |> sort(columns: ["_time"])
            '''
            
            forecast_results = await self.influxdb_client.query(forecast_query)
            
            if not forecast_results:
                self.logger.warning("No forecast data found for accuracy calculation")
                return
            
            # Convert forecast results to DataFrame
            forecast_rows = []
            for record in forecast_results:
                row = {'time': pd.to_datetime(record['_time'])}
                for field in ["temperature", "pressure", "humidity"]:
                    if field in record and record[field] is not None:
                        row[field] = float(record[field])
                    else:
                        row[field] = None
                forecast_rows.append(row)
            
            forecast_df = pd.DataFrame(forecast_rows)
            if not forecast_df.empty:
                forecast_df.set_index('time', inplace=True)
                forecast_df.sort_index(inplace=True)
            
            if forecast_df.empty:
                self.logger.warning("No valid forecast data points found")
                return
            
            total_errors_calculated = 0
            total_errors_stored = 0
            
            # Calculate errors for each forecast horizon
            for horizon_hours in forecast_horizons:
                try:
                    self.logger.debug(f"Calculating errors for {horizon_hours}h forecast horizon")
                    
                    # Align sensor and forecast data
                    aligned_df = self._align_sensor_and_forecast_data(
                        sensor_df, forecast_df, horizon_hours
                    )
                    
                    if aligned_df.empty:
                        self.logger.warning(f"No aligned data for {horizon_hours}h horizon")
                        continue
                    
                    # Calculate errors
                    errors = self._calculate_errors(aligned_df, horizon_hours, "openmeteo")
                    
                    if not errors:
                        self.logger.warning(f"No errors calculated for {horizon_hours}h horizon")
                        continue
                    
                    # Convert to data points
                    data_points = self._convert_errors_to_datapoints(errors)
                    
                    if not data_points:
                        self.logger.warning(f"No data points created for {horizon_hours}h horizon")
                        continue
                    
                    # Store errors
                    success = await self._write_error_points(data_points, bucket_errors)
                    
                    if success:
                        total_errors_calculated += len(errors)
                        total_errors_stored += len(data_points)
                        self.logger.info(f"Stored {len(data_points)} error points for {horizon_hours}h horizon")
                    else:
                        self._stats.errors_failed += len(data_points)
                        self.logger.error(f"Failed to store error points for {horizon_hours}h horizon")
                
                except Exception as e:
                    self.logger.error(f"Error processing {horizon_hours}h forecast horizon: {e}")
                    continue
            
            # Update statistics
            calculation_time = time.time() - start_time
            self._stats.errors_calculated += total_errors_calculated
            self._stats.errors_stored += total_errors_stored
            self._stats.last_calculation_time = datetime.utcnow()
            self._stats.total_calculation_time += calculation_time
            
            # Update performance metrics
            self.performance_monitor.record_metric("forecast_errors_calculated", total_errors_calculated)
            self.performance_monitor.record_metric("forecast_errors_stored", total_errors_stored)
            self.performance_monitor.record_metric("forecast_accuracy_calculation_time", calculation_time)
            
            self.logger.info(
                f"Forecast accuracy calculation completed: "
                f"{total_errors_calculated} errors calculated, "
                f"{total_errors_stored} errors stored in {calculation_time:.3f}s"
            )
            
        except Exception as e:
            self.logger.error(f"Error in forecast accuracy calculation: {e}")
            self._stats.errors_failed += 1
            self.performance_monitor.record_metric("forecast_accuracy_calculation_errors", 1)
            raise ForecastAccuracyError(f"Forecast accuracy calculation failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get forecast accuracy calculation statistics.
        
        Returns:
            Dict[str, Any]: Calculation statistics
        """
        return {
            "errors_calculated": self._stats.errors_calculated,
            "errors_stored": self._stats.errors_stored,
            "errors_failed": self._stats.errors_failed,
            "last_calculation_time": self._stats.last_calculation_time,
            "total_calculation_time": self._stats.total_calculation_time,
            "average_calculation_time": (
                self._stats.total_calculation_time / max(1, self._stats.errors_calculated)
            ),
            "error_measurement": self.error_measurement,
            "influxdb_connected": self.influxdb_client.is_connected()
        }
    
    def reset_statistics(self):
        """Reset calculation statistics."""
        self._stats = AccuracyStats()
        self.logger.debug("Forecast accuracy statistics reset")
    
    async def health_check(self) -> bool:
        """
        Perform health check on forecast accuracy calculator.
        
        Returns:
            bool: True if calculator is healthy
        """
        try:
            # Check InfluxDB connection
            if not self.influxdb_client.is_connected():
                return False
            
            # Try a simple query to verify access
            test_query = f'''
            from(bucket: "{self.influxdb_client.bucket}")
              |> range(start: -1m)
              |> limit(n: 1)
            '''
            
            await self.influxdb_client.query(test_query)
            return True
            
        except Exception as e:
            self.logger.error(f"Forecast accuracy health check failed: {e}")
            return False


async def test_forecast_accuracy(config: Config, logger: ProductionLogger, 
                               performance_monitor: PerformanceMonitor):
    """
    Test function for forecast accuracy calculator.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
    
    try:
        # Connect
        await calculator.connect()
        
        # Test sensor data retrieval
        sensor_df = get_sensor_data_from_influxdb(
            measurement="ruuvi_environmental",
            fields=["temperature", "pressure", "humidity"],
            time_range="24h",
            group_by_interval="1h",
            influxdb_client=calculator.influxdb_client,
            logger=logger
        )
        
        print(f"Retrieved sensor data: {len(sensor_df)} points")
        if not sensor_df.empty:
            print(f"Sensor data columns: {list(sensor_df.columns)}")
            print(f"Sensor data time range: {sensor_df.index.min()} to {sensor_df.index.max()}")
        
        # Test accuracy calculation
        await calculator.calculate_and_store_forecast_errors(
            bucket_sensor=config.influxdb_bucket,
            bucket_forecast=config.weather_influxdb_bucket,
            bucket_errors=config.weather_influxdb_bucket,  # Store errors in same bucket for now
            org=config.influxdb_org,
            lookback_time="24h"
        )
        
        # Get statistics
        stats = calculator.get_statistics()
        print(f"Accuracy calculation statistics: {stats}")
        
        # Health check
        healthy = await calculator.health_check()
        print(f"Health check: {healthy}")
        
    finally:
        await calculator.disconnect()


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
    
    asyncio.run(test_forecast_accuracy(config, logger, performance_monitor))
# Convenience function alias for the main calculation function
async def calculate_and_store_forecast_errors(
    bucket_sensor: str,
    bucket_forecast: str,
    bucket_errors: str,
    org: str,
    lookback_time: str = '48h',
    config: Optional[Config] = None,
    logger: Optional[ProductionLogger] = None,
    performance_monitor: Optional[PerformanceMonitor] = None
) -> None:
    """
    Convenience function to calculate and store forecast errors.
    
    This function provides a simplified interface to the forecast accuracy
    calculation system without requiring manual instantiation of the calculator.
    
    Args:
        bucket_sensor: InfluxDB bucket containing sensor data
        bucket_forecast: InfluxDB bucket containing forecast data
        bucket_errors: InfluxDB bucket for storing calculated errors
        org: InfluxDB organization
        lookback_time: Time range to look back for calculations (e.g., '48h', '7d')
        config: Optional configuration instance
        logger: Optional logger instance
        performance_monitor: Optional performance monitor instance
        
    Raises:
        ForecastAccuracyError: If calculation or storage fails
    """
    # Initialize components if not provided
    if config is None:
        config = Config()
    if logger is None:
        logger = ProductionLogger(config)
    if performance_monitor is None:
        performance_monitor = PerformanceMonitor(logger)
    
    # Create and use calculator
    calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
    
    try:
        await calculator.connect()
        await calculator.calculate_and_store_forecast_errors(
            bucket_sensor=bucket_sensor,
            bucket_forecast=bucket_forecast,
            bucket_errors=bucket_errors,
            org=org,
            lookback_time=lookback_time
        )
    finally:
        await calculator.disconnect()