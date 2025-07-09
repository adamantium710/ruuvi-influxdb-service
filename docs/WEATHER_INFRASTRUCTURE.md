# Weather Forecast Infrastructure

This document describes the weather forecast infrastructure implemented for the Ruuvi sensor system, providing integration with Open-Meteo weather API for enhanced environmental data analysis.

## Overview

The weather infrastructure extends the existing Ruuvi sensor system with comprehensive weather forecasting capabilities, enabling correlation between sensor readings and meteorological conditions.

## Architecture

### Core Components

1. **Configuration Extension** (`src/utils/config.py`)
   - Weather-specific configuration parameters
   - Environment variable management
   - Validation and defaults

2. **Weather API Module** (`src/weather/api.py`)
   - Open-Meteo API integration
   - Rate limiting and circuit breaker patterns
   - Async HTTP requests with retry logic
   - Support for current, forecast, and historical data

3. **Weather Storage Module** (`src/weather/storage.py`)
   - InfluxDB integration for weather data
   - Extends existing client patterns
   - Specialized data point conversion
   - Performance monitoring

## Configuration

### Environment Variables

Add these variables to your `.env` file to enable weather functionality:

```bash
# Enable weather forecast functionality
WEATHER_ENABLED=true

# Location coordinates (Berlin, Germany by default)
WEATHER_LOCATION_LATITUDE=52.5200
WEATHER_LOCATION_LONGITUDE=13.4050
WEATHER_TIMEZONE=Europe/Berlin

# Open-Meteo API Configuration
WEATHER_API_BASE_URL=https://api.open-meteo.com/v1
WEATHER_API_TIMEOUT=30
WEATHER_API_RETRY_ATTEMPTS=3
WEATHER_API_RETRY_DELAY=2.0
WEATHER_API_RATE_LIMIT_REQUESTS=10

# InfluxDB Weather Storage
WEATHER_INFLUXDB_BUCKET=weather_forecasts

# Forecast Scheduling
WEATHER_FORECAST_INTERVAL=60
WEATHER_FORECAST_DAYS=7
WEATHER_HISTORICAL_DAYS=7

# Circuit Breaker Configuration
WEATHER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
WEATHER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300
```

### Default Values

- **Location**: Berlin, Germany (52.5200°N, 13.4050°E)
- **Timezone**: Europe/Berlin
- **API Timeout**: 30 seconds
- **Rate Limit**: 10 requests per minute
- **Forecast Interval**: 60 minutes
- **Forecast Days**: 7 days
- **Historical Days**: 7 days

## Usage

### Basic Weather API Usage

```python
from src.utils.config import Config
from src.weather.api import WeatherAPI
import asyncio

async def fetch_weather():
    config = Config()
    api = WeatherAPI(config)
    
    try:
        # Fetch current weather
        current = await api.fetch_current_weather()
        if current:
            print(f"Current temperature: {current.temperature}°C")
        
        # Fetch forecast data
        forecast = await api.fetch_forecast_data(days=3)
        if forecast:
            print(f"Forecast points: {len(forecast.hourly_forecasts)}")
        
        # Fetch historical data
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=2)
        historical = await api.fetch_historical_data(start_date, end_date)
        if historical:
            print(f"Historical points: {len(historical.hourly_forecasts)}")
    
    finally:
        api.close()

asyncio.run(fetch_weather())
```

### Weather Storage Usage

```python
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.storage import WeatherStorage
from src.weather.api import WeatherAPI
import asyncio

async def store_weather_data():
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    api = WeatherAPI(config, logger)
    storage = WeatherStorage(config, logger, performance_monitor)
    
    try:
        await storage.connect()
        
        # Fetch and store forecast data
        forecast = await api.fetch_forecast_data()
        if forecast:
            success = await storage.write_forecast_to_influxdb(forecast)
            print(f"Storage successful: {success}")
        
        # Query stored data
        from datetime import datetime, timedelta
        start_time = datetime.utcnow() - timedelta(hours=1)
        results = await storage.query_weather_data(start_time)
        print(f"Retrieved {len(results)} records")
    
    finally:
        api.close()
        await storage.disconnect()

asyncio.run(store_weather_data())
```

## Data Schema

### Weather Data Points

Weather data is stored in InfluxDB with the following structure:

**Measurement**: `weather_forecasts`

**Tags**:
- `location_lat`: Latitude coordinate
- `location_lon`: Longitude coordinate
- `timezone`: Timezone identifier
- `data_type`: Type of data (current, forecast, historical, daily_forecast)
- `is_forecast`: Boolean indicating if data is forecast
- `retrieved_at`: Timestamp when data was retrieved

**Fields**:
- `temperature`: Temperature in Celsius
- `humidity`: Relative humidity percentage
- `pressure`: Atmospheric pressure in hPa
- `wind_speed`: Wind speed in m/s
- `wind_direction`: Wind direction in degrees
- `precipitation`: Precipitation in mm
- `cloud_cover`: Cloud cover percentage
- `visibility`: Visibility in meters (optional)
- `uv_index`: UV index (optional)
- `weather_code`: Weather condition code (optional)

## Features

### Fault Tolerance

1. **Circuit Breaker Pattern**
   - Prevents cascading failures
   - Configurable failure threshold
   - Automatic recovery attempts

2. **Rate Limiting**
   - Respects API rate limits
   - Configurable requests per minute
   - Automatic request queuing

3. **Retry Logic**
   - Exponential backoff
   - Configurable retry attempts
   - Comprehensive error handling

### Performance Monitoring

- Request timing metrics
- Success/failure statistics
- Buffer utilization tracking
- Health check monitoring

### Data Quality

- Comprehensive data validation
- Type conversion and sanitization
- Missing data handling
- Timestamp normalization

## Testing

Run the weather infrastructure test suite:

```bash
python scripts/test_weather_infrastructure.py
```

The test suite verifies:
- API connectivity and health
- Data fetching and parsing
- Storage operations
- Integration functionality
- Configuration validation

## Dependencies

New dependencies added for weather functionality:

```
requests>=2.31.0,<3.0.0            # HTTP requests for weather API
pytz>=2023.3,<2024.0               # Timezone handling for weather data
ydata-profiling>=4.5.0,<5.0.0      # Data profiling and analysis
mlxtend>=0.22.0,<1.0.0             # Machine learning extensions
```

## Integration with Existing System

The weather infrastructure seamlessly integrates with the existing Ruuvi sensor system:

1. **Configuration System**: Extends existing `Config` class with weather parameters
2. **InfluxDB Client**: Reuses existing `RuuviInfluxDBClient` patterns
3. **Logging**: Uses existing `ProductionLogger` and `PerformanceMonitor`
4. **Error Handling**: Follows established error handling patterns
5. **Async Patterns**: Maintains consistency with existing async operations

## Future Enhancements

The infrastructure is designed to support future enhancements:

1. **Weather Analysis**: Correlation analysis between sensor and weather data
2. **Predictive Models**: Machine learning models using weather and sensor data
3. **Alerting**: Weather-based alerting and notifications
4. **Data Profiling**: Automated data quality analysis
5. **Multiple Locations**: Support for multiple weather monitoring locations

## Troubleshooting

### Common Issues

1. **API Connection Failures**
   - Check internet connectivity
   - Verify API endpoint accessibility
   - Review rate limiting settings

2. **Storage Issues**
   - Ensure InfluxDB is running and accessible
   - Verify weather bucket exists
   - Check write permissions

3. **Configuration Errors**
   - Validate environment variables
   - Check coordinate ranges
   - Verify timezone settings

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
export LOG_LEVEL=DEBUG
python scripts/test_weather_infrastructure.py
```

## Security Considerations

- No API keys required for Open-Meteo (free tier)
- Rate limiting prevents abuse
- Circuit breaker prevents resource exhaustion
- Input validation prevents injection attacks
- Secure HTTPS connections for API requests

## Performance Considerations

- Async operations prevent blocking
- Batch writing for efficient storage
- Connection pooling for HTTP requests
- Buffer management for memory efficiency
- Configurable timeouts and retries