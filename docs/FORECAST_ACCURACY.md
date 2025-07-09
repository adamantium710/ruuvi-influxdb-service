# Forecast Accuracy System Documentation

## Overview

The Forecast Accuracy System implements comprehensive forecast error calculation and storage capabilities as specified in Phase 2 of the weather infrastructure enhancement. This system enables tracking and analysis of weather forecast accuracy over time by comparing actual sensor readings with historical forecast predictions.

## Architecture

### Core Components

1. **Sensor Data Retrieval** (`get_sensor_data_from_influxdb()`)
   - Retrieves historical sensor data from InfluxDB
   - Returns pandas DataFrame with time-indexed sensor readings
   - Supports flexible time ranges and grouping intervals

2. **Forecast Accuracy Calculator** (`ForecastAccuracyCalculator`)
   - Aligns sensor data with forecast data based on timestamps
   - Calculates absolute and signed errors for multiple forecast horizons
   - Stores calculated errors in InfluxDB for analysis

3. **Weather Error Storage** (`WeatherErrorStorage`)
   - Specialized storage manager for forecast error data
   - Extends existing InfluxDB client patterns
   - Supports querying and analysis of stored errors

## Data Schema

### Sensor Data (Input)
- **Measurement**: `ruuvi_environmental`
- **Fields**: `temperature`, `pressure`, `humidity`
- **Time Index**: Hourly aggregated sensor readings

### Forecast Data (Input)
- **Measurement**: `weather_forecasts`
- **Fields**: `temperature`, `pressure`, `humidity`
- **Tags**: `data_type=forecast`, `source`, `retrieved_at`

### Forecast Errors (Output)
- **Measurement**: `weather_forecast_errors`
- **Fields**:
  - `temp_abs_error`: Absolute temperature error (|actual - forecast|)
  - `temp_signed_error`: Signed temperature error (forecast - actual)
  - `pressure_abs_error`: Absolute pressure error
  - `pressure_signed_error`: Signed pressure error
  - `humidity_abs_error`: Absolute humidity error
  - `humidity_signed_error`: Signed humidity error
- **Tags**:
  - `source`: Forecast data source (e.g., "openmeteo")
  - `forecast_horizon_hours`: Forecast horizon (1, 6, 24, 48 hours)

## Key Functions

### `get_sensor_data_from_influxdb()`

Retrieves sensor data from InfluxDB and returns as pandas DataFrame.

```python
def get_sensor_data_from_influxdb(
    measurement: str,
    fields: list[str],
    time_range: str = '30 days',
    group_by_interval: str = '1h',
    influxdb_client: Optional[RuuviInfluxDBClient] = None,
    config: Optional[Config] = None,
    logger: Optional[ProductionLogger] = None
) -> pd.DataFrame
```

**Parameters:**
- `measurement`: InfluxDB measurement name (e.g., 'ruuvi_environmental')
- `fields`: List of field names to retrieve (e.g., ['temperature', 'pressure', 'humidity'])
- `time_range`: Time range for data retrieval (e.g., '30 days', '7d', '24h')
- `group_by_interval`: Grouping interval for aggregation (e.g., '1h', '15m', '5m')
- `influxdb_client`: Optional existing InfluxDB client
- `config`: Optional configuration instance
- `logger`: Optional logger instance

**Returns:**
- `pd.DataFrame`: DataFrame with time index and sensor columns

**Example Usage:**
```python
from src.weather.accuracy import get_sensor_data_from_influxdb

# Retrieve last 7 days of hourly sensor data
sensor_df = get_sensor_data_from_influxdb(
    measurement="ruuvi_environmental",
    fields=["temperature", "pressure", "humidity"],
    time_range="7d",
    group_by_interval="1h"
)

print(f"Retrieved {len(sensor_df)} data points")
print(sensor_df.head())
```

### `calculate_and_store_forecast_errors()`

Main function for calculating and storing forecast accuracy errors.

```python
async def calculate_and_store_forecast_errors(
    bucket_sensor: str,
    bucket_forecast: str,
    bucket_errors: str,
    org: str,
    lookback_time: str = '48h'
) -> None
```

**Parameters:**
- `bucket_sensor`: InfluxDB bucket containing sensor data
- `bucket_forecast`: InfluxDB bucket containing forecast data
- `bucket_errors`: InfluxDB bucket for storing calculated errors
- `org`: InfluxDB organization
- `lookback_time`: Time range to look back for calculations (e.g., '48h', '7d')

**Example Usage:**
```python
from src.weather.accuracy import ForecastAccuracyCalculator

calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
await calculator.connect()

await calculator.calculate_and_store_forecast_errors(
    bucket_sensor="ruuvi_sensors",
    bucket_forecast="weather_forecasts",
    bucket_errors="weather_forecasts",
    org="my_org",
    lookback_time="48h"
)
```

## Data Alignment Process

The system implements sophisticated data alignment to match sensor readings with corresponding forecasts:

1. **Time-based Alignment**: Forecasts are aligned with actual sensor readings based on the forecast horizon
2. **Horizon Offset**: Forecast timestamps are shifted back by the forecast horizon to align with actual measurement times
3. **Inner Join**: Only timestamps with both sensor and forecast data are included in error calculations

### Forecast Horizons

The system calculates errors for multiple forecast horizons:
- **1 hour**: Short-term accuracy
- **6 hours**: Medium-term accuracy
- **24 hours**: Daily forecast accuracy
- **48 hours**: Extended forecast accuracy

## Error Calculations

### Absolute Error
Measures the magnitude of forecast error regardless of direction:
```
absolute_error = |actual_value - forecast_value|
```

### Signed Error (Bias)
Measures forecast bias (tendency to over or under-predict):
```
signed_error = forecast_value - actual_value
```
- Positive values indicate over-prediction
- Negative values indicate under-prediction

## Usage Examples

### Basic Sensor Data Retrieval

```python
import asyncio
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.accuracy import get_sensor_data_from_influxdb

async def main():
    config = Config()
    logger = ProductionLogger(config)
    
    # Get last 24 hours of sensor data
    sensor_df = get_sensor_data_from_influxdb(
        measurement="ruuvi_environmental",
        fields=["temperature", "pressure", "humidity"],
        time_range="24h",
        group_by_interval="1h",
        config=config,
        logger=logger
    )
    
    print(f"Retrieved {len(sensor_df)} sensor readings")
    print(f"Temperature range: {sensor_df['temperature'].min():.1f}°C to {sensor_df['temperature'].max():.1f}°C")

asyncio.run(main())
```

### Complete Accuracy Calculation

```python
import asyncio
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.accuracy import ForecastAccuracyCalculator

async def calculate_accuracy():
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
    
    try:
        await calculator.connect()
        
        # Calculate errors for last 48 hours
        await calculator.calculate_and_store_forecast_errors(
            bucket_sensor=config.influxdb_bucket,
            bucket_forecast=config.weather_influxdb_bucket,
            bucket_errors=config.weather_influxdb_bucket,
            org=config.influxdb_org,
            lookback_time="48h"
        )
        
        # Get statistics
        stats = calculator.get_statistics()
        print(f"Calculated {stats['errors_calculated']} forecast errors")
        print(f"Stored {stats['errors_stored']} error records")
        
    finally:
        await calculator.disconnect()

asyncio.run(calculate_accuracy())
```

### Error Data Storage and Querying

```python
import asyncio
from datetime import datetime, timedelta
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.storage import WeatherErrorStorage

async def query_errors():
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    error_storage = WeatherErrorStorage(config, logger, performance_monitor)
    
    try:
        await error_storage.connect()
        
        # Query errors for last 24 hours, 24-hour forecast horizon
        start_time = datetime.utcnow() - timedelta(hours=24)
        errors = await error_storage.query_forecast_errors(
            start_time=start_time,
            forecast_horizon_hours=24,
            source="openmeteo"
        )
        
        print(f"Found {len(errors)} error records")
        
        if errors:
            # Calculate average errors
            temp_errors = [e.get('temp_abs_error', 0) for e in errors if e.get('temp_abs_error')]
            avg_temp_error = sum(temp_errors) / len(temp_errors) if temp_errors else 0
            print(f"Average temperature error: {avg_temp_error:.2f}°C")
        
    finally:
        await error_storage.disconnect()

asyncio.run(query_errors())
```

## Testing

### Running Tests

Execute the comprehensive test suite:

```bash
python scripts/test_forecast_accuracy.py
```

The test suite includes:
- Sensor data retrieval testing
- Data alignment verification
- Error calculation validation
- Storage functionality testing
- End-to-end accuracy calculation

### Test Components

1. **Sensor Data Retrieval Test**: Verifies the `get_sensor_data_from_influxdb()` function
2. **Data Alignment Test**: Tests alignment logic with mock data
3. **Weather Error Storage Test**: Validates error storage and querying
4. **Forecast Accuracy Calculator Test**: End-to-end accuracy calculation testing

## Configuration

### Required Environment Variables

```bash
# InfluxDB Configuration
INFLUXDB_HOST=localhost
INFLUXDB_PORT=8086
INFLUXDB_TOKEN=your_token_here
INFLUXDB_ORG=your_org
INFLUXDB_BUCKET=ruuvi_sensors

# Weather Configuration
WEATHER_ENABLED=true
WEATHER_INFLUXDB_BUCKET=weather_forecasts
```

### Configuration Properties

The system uses the following configuration properties:

- `influxdb_*`: Standard InfluxDB connection settings
- `weather_influxdb_bucket`: Bucket for weather forecast and error data
- `weather_enabled`: Enable/disable weather functionality

## Performance Considerations

### Optimization Features

1. **Batch Processing**: Errors are calculated and stored in batches
2. **Time-based Filtering**: Only processes data within specified time ranges
3. **Efficient Queries**: Uses optimized Flux queries for data retrieval
4. **Connection Reuse**: Reuses existing InfluxDB connections when possible

### Monitoring

The system provides comprehensive performance monitoring:

- Error calculation timing
- Data point processing rates
- Storage operation success rates
- Memory usage tracking

### Statistics

Access performance statistics:

```python
stats = calculator.get_statistics()
print(f"Errors calculated: {stats['errors_calculated']}")
print(f"Average calculation time: {stats['average_calculation_time']:.3f}s")
```

## Integration with Grafana

### Recommended Dashboards

1. **Forecast Accuracy Overview**
   - Temperature error trends over time
   - Pressure and humidity accuracy metrics
   - Error distribution by forecast horizon

2. **Forecast Bias Analysis**
   - Signed error trends (bias detection)
   - Seasonal accuracy patterns
   - Horizon-specific performance

### Example Flux Queries

**Average Temperature Error by Horizon:**
```flux
from(bucket: "weather_forecasts")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> group(columns: ["forecast_horizon_hours"])
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
```

**Forecast Bias Detection:**
```flux
from(bucket: "weather_forecasts")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_signed_error")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
```

## Troubleshooting

### Common Issues

1. **No Sensor Data Found**
   - Verify Ruuvi sensors are running and collecting data
   - Check InfluxDB bucket and measurement names
   - Ensure time range covers periods with sensor data

2. **No Forecast Data Found**
   - Verify weather forecast collection is enabled
   - Check weather API configuration
   - Ensure forecast data is being stored in correct bucket

3. **Alignment Issues**
   - Verify timezone consistency between sensor and forecast data
   - Check forecast horizon calculations
   - Ensure data timestamps are properly formatted

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Both the calculator and storage components provide health check methods:

```python
# Check calculator health
healthy = await calculator.health_check()

# Check storage health
healthy = await error_storage.health_check()
```

## Future Enhancements

### Planned Features

1. **Advanced Error Metrics**
   - Root Mean Square Error (RMSE)
   - Mean Absolute Percentage Error (MAPE)
   - Skill scores and forecast verification metrics

2. **Automated Scheduling**
   - Periodic accuracy calculation via cron/systemd
   - Configurable calculation intervals
   - Automatic error threshold alerting

3. **Enhanced Analysis**
   - Seasonal accuracy patterns
   - Weather condition-specific accuracy
   - Multi-location forecast comparison

### Extension Points

The system is designed for extensibility:

- Custom error calculation methods
- Additional forecast data sources
- Enhanced data alignment algorithms
- Custom storage backends

## API Reference

### Classes

- `ForecastAccuracyCalculator`: Main accuracy calculation engine
- `WeatherErrorStorage`: Specialized error data storage
- `ForecastError`: Data class for error records

### Functions

- `get_sensor_data_from_influxdb()`: Sensor data retrieval
- `calculate_and_store_forecast_errors()`: Main calculation function

### Exceptions

- `ForecastAccuracyError`: Base exception for accuracy operations
- `WeatherStorageError`: Storage-related exceptions

For detailed API documentation, refer to the docstrings in the source code.