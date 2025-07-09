#!/usr/bin/env python3
"""
Test script for forecast accuracy calculation system.
Tests the implementation of sensor data retrieval and forecast error calculations.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.weather.accuracy import (
    ForecastAccuracyCalculator,
    get_sensor_data_from_influxdb
)
from src.weather.storage import WeatherErrorStorage
from src.influxdb.client import RuuviInfluxDBClient


async def test_sensor_data_retrieval():
    """Test the sensor data retrieval function."""
    print("\n" + "="*60)
    print("TESTING SENSOR DATA RETRIEVAL")
    print("="*60)
    
    try:
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        print(f"✓ Configuration loaded")
        print(f"  - InfluxDB Host: {config.influxdb_host}:{config.influxdb_port}")
        print(f"  - InfluxDB Bucket: {config.influxdb_bucket}")
        print(f"  - Weather Bucket: {config.weather_influxdb_bucket}")
        
        # Test sensor data retrieval
        print(f"\n📊 Testing sensor data retrieval...")
        
        sensor_df = get_sensor_data_from_influxdb(
            measurement="ruuvi_environmental",
            fields=["temperature", "pressure", "humidity"],
            time_range="7d",
            group_by_interval="1h",
            config=config,
            logger=logger
        )
        
        if not sensor_df.empty:
            print(f"✓ Retrieved {len(sensor_df)} sensor data points")
            print(f"  - Columns: {list(sensor_df.columns)}")
            print(f"  - Time range: {sensor_df.index.min()} to {sensor_df.index.max()}")
            print(f"  - Sample data:")
            print(sensor_df.head().to_string())
            
            # Check for missing data
            missing_data = sensor_df.isnull().sum()
            print(f"  - Missing data: {missing_data.to_dict()}")
        else:
            print("⚠️  No sensor data found")
            print("   This might be expected if no Ruuvi sensors have been running")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in sensor data retrieval test: {e}")
        return False


async def test_forecast_accuracy_calculator():
    """Test the forecast accuracy calculator."""
    print("\n" + "="*60)
    print("TESTING FORECAST ACCURACY CALCULATOR")
    print("="*60)
    
    try:
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        # Initialize calculator
        calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
        
        print(f"✓ ForecastAccuracyCalculator initialized")
        
        # Connect to InfluxDB
        connected = await calculator.connect()
        if connected:
            print(f"✓ Connected to InfluxDB")
        else:
            print(f"❌ Failed to connect to InfluxDB")
            return False
        
        try:
            # Test health check
            healthy = await calculator.health_check()
            print(f"✓ Health check: {'Passed' if healthy else 'Failed'}")
            
            # Test accuracy calculation
            print(f"\n🧮 Testing forecast accuracy calculation...")
            
            await calculator.calculate_and_store_forecast_errors(
                bucket_sensor=config.influxdb_bucket,
                bucket_forecast=config.weather_influxdb_bucket,
                bucket_errors=config.weather_influxdb_bucket,
                org=config.influxdb_org,
                lookback_time="24h"
            )
            
            # Get statistics
            stats = calculator.get_statistics()
            print(f"✓ Accuracy calculation completed")
            print(f"  - Errors calculated: {stats['errors_calculated']}")
            print(f"  - Errors stored: {stats['errors_stored']}")
            print(f"  - Errors failed: {stats['errors_failed']}")
            print(f"  - Last calculation: {stats['last_calculation_time']}")
            print(f"  - Total calculation time: {stats['total_calculation_time']:.3f}s")
            
            if stats['errors_calculated'] > 0:
                print(f"  - Average calculation time: {stats['average_calculation_time']:.3f}s")
            
            return True
            
        finally:
            await calculator.disconnect()
            print(f"✓ Disconnected from InfluxDB")
        
    except Exception as e:
        print(f"❌ Error in forecast accuracy calculator test: {e}")
        return False


async def test_weather_error_storage():
    """Test the weather error storage functionality."""
    print("\n" + "="*60)
    print("TESTING WEATHER ERROR STORAGE")
    print("="*60)
    
    try:
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        # Initialize error storage
        error_storage = WeatherErrorStorage(config, logger, performance_monitor)
        
        print(f"✓ WeatherErrorStorage initialized")
        
        # Connect to InfluxDB
        connected = await error_storage.connect()
        if connected:
            print(f"✓ Connected to InfluxDB")
        else:
            print(f"❌ Failed to connect to InfluxDB")
            return False
        
        try:
            # Test health check
            healthy = await error_storage.health_check()
            print(f"✓ Health check: {'Passed' if healthy else 'Failed'}")
            
            # Create test error data
            test_errors = [
                {
                    'timestamp': datetime.utcnow() - timedelta(hours=1),
                    'forecast_horizon_hours': 24,
                    'source': 'openmeteo',
                    'temp_abs_error': 2.5,
                    'temp_signed_error': -1.2,
                    'pressure_abs_error': 5.3,
                    'pressure_signed_error': 3.1,
                    'humidity_abs_error': 8.7,
                    'humidity_signed_error': -4.2
                },
                {
                    'timestamp': datetime.utcnow() - timedelta(hours=2),
                    'forecast_horizon_hours': 6,
                    'source': 'openmeteo',
                    'temp_abs_error': 1.8,
                    'temp_signed_error': 0.9,
                    'pressure_abs_error': 3.2,
                    'pressure_signed_error': -2.1,
                    'humidity_abs_error': 6.4,
                    'humidity_signed_error': 3.8
                }
            ]
            
            print(f"\n💾 Testing error data storage...")
            
            # Write test error data
            success = await error_storage.write_forecast_errors_to_influxdb(
                test_errors, buffer=False
            )
            
            if success:
                print(f"✓ Successfully wrote {len(test_errors)} test error records")
            else:
                print(f"❌ Failed to write test error records")
                return False
            
            # Get statistics
            stats = error_storage.get_error_statistics()
            print(f"✓ Error storage statistics:")
            print(f"  - Errors written: {stats['errors_written']}")
            print(f"  - Errors failed: {stats['errors_failed']}")
            print(f"  - Last write time: {stats['last_write_time']}")
            print(f"  - Total write time: {stats['total_write_time']:.3f}s")
            print(f"  - Average write time: {stats['average_write_time']:.3f}s")
            
            # Test querying error data
            print(f"\n🔍 Testing error data querying...")
            
            start_time = datetime.utcnow() - timedelta(hours=3)
            error_records = await error_storage.query_forecast_errors(
                start_time=start_time,
                forecast_horizon_hours=24
            )
            
            print(f"✓ Queried {len(error_records)} error records for 24h horizon")
            
            if error_records:
                print(f"  - Sample record keys: {list(error_records[0].keys())}")
            
            return True
            
        finally:
            await error_storage.disconnect()
            print(f"✓ Disconnected from InfluxDB")
        
    except Exception as e:
        print(f"❌ Error in weather error storage test: {e}")
        return False


async def test_data_alignment():
    """Test data alignment functionality with mock data."""
    print("\n" + "="*60)
    print("TESTING DATA ALIGNMENT")
    print("="*60)
    
    try:
        # Create mock sensor data
        sensor_times = pd.date_range(
            start=datetime.now() - timedelta(days=2),
            end=datetime.now(),
            freq='1H'
        )
        
        sensor_data = {
            'temperature': [20 + i * 0.1 for i in range(len(sensor_times))],
            'pressure': [1013 + i * 0.5 for i in range(len(sensor_times))],
            'humidity': [50 + i * 0.2 for i in range(len(sensor_times))]
        }
        
        sensor_df = pd.DataFrame(sensor_data, index=sensor_times)
        
        # Create mock forecast data (offset by forecast horizon)
        forecast_times = pd.date_range(
            start=datetime.now() - timedelta(days=2, hours=24),  # 24h ahead forecasts
            end=datetime.now() - timedelta(hours=24),
            freq='1H'
        )
        
        forecast_data = {
            'temperature': [19.5 + i * 0.1 for i in range(len(forecast_times))],
            'pressure': [1012 + i * 0.5 for i in range(len(forecast_times))],
            'humidity': [51 + i * 0.2 for i in range(len(forecast_times))]
        }
        
        forecast_df = pd.DataFrame(forecast_data, index=forecast_times)
        
        print(f"✓ Created mock data:")
        print(f"  - Sensor data: {len(sensor_df)} points from {sensor_df.index.min()} to {sensor_df.index.max()}")
        print(f"  - Forecast data: {len(forecast_df)} points from {forecast_df.index.min()} to {forecast_df.index.max()}")
        
        # Test alignment using calculator
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
        
        # Test alignment
        aligned_df = calculator._align_sensor_and_forecast_data(
            sensor_df, forecast_df, forecast_horizon_hours=24
        )
        
        print(f"✓ Data alignment completed:")
        print(f"  - Aligned data points: {len(aligned_df)}")
        
        if not aligned_df.empty:
            print(f"  - Columns: {list(aligned_df.columns)}")
            print(f"  - Time range: {aligned_df.index.min()} to {aligned_df.index.max()}")
            print(f"  - Sample aligned data:")
            print(aligned_df.head().to_string())
            
            # Test error calculation
            errors = calculator._calculate_errors(aligned_df, 24, "test")
            print(f"✓ Error calculation completed: {len(errors)} errors calculated")
            
            if errors:
                sample_error = errors[0]
                print(f"  - Sample error:")
                print(f"    - Temperature abs error: {sample_error.temp_abs_error}")
                print(f"    - Temperature signed error: {sample_error.temp_signed_error}")
                print(f"    - Pressure abs error: {sample_error.pressure_abs_error}")
                print(f"    - Humidity abs error: {sample_error.humidity_abs_error}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in data alignment test: {e}")
        return False


async def main():
    """Run all forecast accuracy tests."""
    print("🚀 FORECAST ACCURACY SYSTEM TEST SUITE")
    print("=" * 80)
    
    tests = [
        ("Sensor Data Retrieval", test_sensor_data_retrieval),
        ("Data Alignment", test_data_alignment),
        ("Weather Error Storage", test_weather_error_storage),
        ("Forecast Accuracy Calculator", test_forecast_accuracy_calculator),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {status}")
        except Exception as e:
            print(f"   ❌ FAILED with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Forecast accuracy system is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)