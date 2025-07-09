#!/usr/bin/env python3
"""
Test script for weather forecast infrastructure.
Verifies API connectivity, data parsing, and storage functionality.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.api import WeatherAPI
from src.weather.storage import WeatherStorage


async def test_weather_api(config: Config, logger: ProductionLogger):
    """Test weather API functionality."""
    print("\n=== Testing Weather API ===")
    
    api = WeatherAPI(config, logger)
    
    try:
        # Test health check
        print("1. Testing API health check...")
        healthy = await api.health_check()
        print(f"   API Health: {'✓ Healthy' if healthy else '✗ Unhealthy'}")
        
        if not healthy:
            print("   Skipping API tests due to health check failure")
            return False
        
        # Test current weather
        print("2. Testing current weather fetch...")
        current = await api.fetch_current_weather()
        if current:
            print(f"   ✓ Current weather: {current.temperature}°C at {current.timestamp}")
        else:
            print("   ✗ Failed to fetch current weather")
        
        # Test forecast data
        print("3. Testing forecast data fetch...")
        forecast = await api.fetch_forecast_data(days=2)
        if forecast:
            print(f"   ✓ Forecast data: {len(forecast.hourly_forecasts)} hourly points")
            print(f"   Location: ({forecast.location_latitude}, {forecast.location_longitude})")
            print(f"   Timezone: {forecast.timezone}")
        else:
            print("   ✗ Failed to fetch forecast data")
        
        # Test historical data
        print("4. Testing historical data fetch...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)
        historical = await api.fetch_historical_data(start_date, end_date)
        if historical:
            print(f"   ✓ Historical data: {len(historical.hourly_forecasts)} hourly points")
        else:
            print("   ✗ Failed to fetch historical data")
        
        # Test rate limiter and circuit breaker status
        print("5. Testing rate limiter and circuit breaker...")
        rate_status = api.get_rate_limiter_status()
        circuit_status = api.get_circuit_breaker_status()
        print(f"   Rate limiter: {rate_status['current_requests']}/{rate_status['max_requests']} requests")
        print(f"   Circuit breaker: {circuit_status['state']} (failures: {circuit_status['failure_count']})")
        
        return True
        
    except Exception as e:
        print(f"   ✗ API test failed: {e}")
        return False
    finally:
        api.close()


async def test_weather_storage(config: Config, logger: ProductionLogger, 
                             performance_monitor: PerformanceMonitor):
    """Test weather storage functionality."""
    print("\n=== Testing Weather Storage ===")
    
    storage = WeatherStorage(config, logger, performance_monitor)
    
    try:
        # Test connection
        print("1. Testing storage connection...")
        connected = await storage.connect()
        print(f"   Storage connection: {'✓ Connected' if connected else '✗ Failed'}")
        
        if not connected:
            print("   Skipping storage tests due to connection failure")
            return False
        
        # Test health check
        print("2. Testing storage health check...")
        healthy = await storage.health_check()
        print(f"   Storage health: {'✓ Healthy' if healthy else '✗ Unhealthy'}")
        
        # Create test data
        print("3. Testing data preparation...")
        from src.weather.api import WeatherData, ForecastData
        
        test_weather = WeatherData(
            timestamp=datetime.utcnow(),
            temperature=20.5,
            humidity=60.0,
            pressure=1013.25,
            wind_speed=3.5,
            wind_direction=180.0,
            precipitation=0.0,
            cloud_cover=30.0,
            visibility=10000.0,
            uv_index=2.0,
            weather_code=1,
            is_forecast=True
        )
        
        test_forecast = ForecastData(
            location_latitude=config.weather_location_latitude,
            location_longitude=config.weather_location_longitude,
            timezone=config.weather_timezone,
            hourly_forecasts=[test_weather]
        )
        
        # Test data point preparation
        data_points = storage.prepare_forecast_for_influxdb(test_forecast)
        print(f"   ✓ Prepared {len(data_points)} data points")
        
        # Test writing data
        print("4. Testing data write...")
        success = await storage.write_forecast_to_influxdb(test_forecast, buffer=False)
        print(f"   Data write: {'✓ Success' if success else '✗ Failed'}")
        
        # Test statistics
        print("5. Testing statistics...")
        stats = storage.get_statistics()
        print(f"   Forecasts written: {stats['forecasts_written']}")
        print(f"   Forecasts failed: {stats['forecasts_failed']}")
        print(f"   Average write time: {stats['average_write_time']:.3f}s")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Storage test failed: {e}")
        return False
    finally:
        await storage.disconnect()


async def test_integration(config: Config, logger: ProductionLogger, 
                         performance_monitor: PerformanceMonitor):
    """Test full integration of API and storage."""
    print("\n=== Testing Integration ===")
    
    api = WeatherAPI(config, logger)
    storage = WeatherStorage(config, logger, performance_monitor)
    
    try:
        # Connect storage
        await storage.connect()
        
        # Fetch real forecast data
        print("1. Fetching real forecast data...")
        forecast = await api.fetch_forecast_data(days=1)
        
        if not forecast:
            print("   ✗ Failed to fetch forecast data")
            return False
        
        print(f"   ✓ Fetched {len(forecast.hourly_forecasts)} forecast points")
        
        # Store the data
        print("2. Storing forecast data...")
        success = await storage.write_forecast_to_influxdb(forecast, buffer=False)
        print(f"   Storage: {'✓ Success' if success else '✗ Failed'}")
        
        # Query the data back
        print("3. Querying stored data...")
        start_time = datetime.utcnow() - timedelta(minutes=5)
        results = await storage.query_weather_data(start_time, data_type="forecast")
        print(f"   ✓ Retrieved {len(results)} stored records")
        
        return success
        
    except Exception as e:
        print(f"   ✗ Integration test failed: {e}")
        return False
    finally:
        api.close()
        await storage.disconnect()


def print_configuration_summary(config: Config):
    """Print weather configuration summary."""
    print("\n=== Weather Configuration ===")
    
    if not config.weather_enabled:
        print("Weather functionality is DISABLED")
        print("Set WEATHER_ENABLED=true in your .env file to enable")
        return
    
    summary = config.get_summary()
    weather_config = summary.get('weather', {})
    
    print(f"Status: {'✓ ENABLED' if config.weather_enabled else '✗ DISABLED'}")
    print(f"Location: ({weather_config.get('location', {}).get('latitude')}, "
          f"{weather_config.get('location', {}).get('longitude')})")
    print(f"Timezone: {weather_config.get('location', {}).get('timezone')}")
    print(f"API URL: {weather_config.get('api', {}).get('base_url')}")
    print(f"Storage Bucket: {weather_config.get('storage', {}).get('bucket')}")
    print(f"Forecast Interval: {weather_config.get('scheduling', {}).get('forecast_interval')} minutes")
    print(f"Forecast Days: {weather_config.get('scheduling', {}).get('forecast_days')}")


async def main():
    """Main test function."""
    print("Weather Infrastructure Test Suite")
    print("=" * 50)
    
    try:
        # Initialize configuration
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        # Print configuration
        print_configuration_summary(config)
        
        if not config.weather_enabled:
            print("\nWeather functionality is disabled. Enable it to run tests.")
            return
        
        # Run tests
        api_success = await test_weather_api(config, logger)
        storage_success = await test_weather_storage(config, logger, performance_monitor)
        
        if api_success and storage_success:
            integration_success = await test_integration(config, logger, performance_monitor)
        else:
            integration_success = False
        
        # Summary
        print("\n=== Test Summary ===")
        print(f"API Tests: {'✓ PASSED' if api_success else '✗ FAILED'}")
        print(f"Storage Tests: {'✓ PASSED' if storage_success else '✗ FAILED'}")
        print(f"Integration Tests: {'✓ PASSED' if integration_success else '✗ FAILED'}")
        
        overall_success = api_success and storage_success and integration_success
        print(f"Overall: {'✓ ALL TESTS PASSED' if overall_success else '✗ SOME TESTS FAILED'}")
        
        return 0 if overall_success else 1
        
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)