#!/usr/bin/env python3
"""
Forecast Accuracy System Integration Example

This example demonstrates how to use the forecast accuracy calculation system
to analyze weather forecast performance against actual sensor readings.
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
from src.weather.accuracy import (
    ForecastAccuracyCalculator,
    get_sensor_data_from_influxdb
)
from src.weather.storage import WeatherErrorStorage


async def example_sensor_data_retrieval():
    """Example: Retrieve and analyze sensor data."""
    print("=" * 60)
    print("EXAMPLE 1: Sensor Data Retrieval")
    print("=" * 60)
    
    config = Config()
    logger = ProductionLogger(config)
    
    # Retrieve sensor data for the last 7 days
    print("📊 Retrieving sensor data...")
    
    sensor_df = get_sensor_data_from_influxdb(
        measurement="ruuvi_environmental",
        fields=["temperature", "pressure", "humidity"],
        time_range="7d",
        group_by_interval="1h",
        config=config,
        logger=logger
    )
    
    if not sensor_df.empty:
        print(f"✓ Retrieved {len(sensor_df)} hourly sensor readings")
        print(f"  Time range: {sensor_df.index.min()} to {sensor_df.index.max()}")
        
        # Basic statistics
        print(f"\n📈 Sensor Data Statistics:")
        print(f"  Temperature: {sensor_df['temperature'].min():.1f}°C to {sensor_df['temperature'].max():.1f}°C (avg: {sensor_df['temperature'].mean():.1f}°C)")
        print(f"  Pressure: {sensor_df['pressure'].min():.1f} hPa to {sensor_df['pressure'].max():.1f} hPa (avg: {sensor_df['pressure'].mean():.1f} hPa)")
        print(f"  Humidity: {sensor_df['humidity'].min():.1f}% to {sensor_df['humidity'].max():.1f}% (avg: {sensor_df['humidity'].mean():.1f}%)")
        
        # Data quality check
        missing_data = sensor_df.isnull().sum()
        print(f"\n🔍 Data Quality:")
        for field, missing_count in missing_data.items():
            completeness = (1 - missing_count / len(sensor_df)) * 100
            print(f"  {field}: {completeness:.1f}% complete ({missing_count} missing values)")
    else:
        print("⚠️  No sensor data found. Make sure Ruuvi sensors are collecting data.")
    
    return sensor_df


async def example_forecast_accuracy_calculation():
    """Example: Calculate forecast accuracy."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Forecast Accuracy Calculation")
    print("=" * 60)
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    # Initialize accuracy calculator
    calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
    
    try:
        # Connect to InfluxDB
        print("🔌 Connecting to InfluxDB...")
        connected = await calculator.connect()
        
        if not connected:
            print("❌ Failed to connect to InfluxDB")
            return
        
        print("✓ Connected to InfluxDB")
        
        # Perform health check
        healthy = await calculator.health_check()
        print(f"🏥 Health check: {'✓ Passed' if healthy else '❌ Failed'}")
        
        if not healthy:
            print("⚠️  System not healthy, skipping accuracy calculation")
            return
        
        # Calculate forecast accuracy for the last 48 hours
        print(f"\n🧮 Calculating forecast accuracy for last 48 hours...")
        
        start_time = datetime.now()
        
        await calculator.calculate_and_store_forecast_errors(
            bucket_sensor=config.influxdb_bucket,
            bucket_forecast=config.weather_influxdb_bucket,
            bucket_errors=config.weather_influxdb_bucket,
            org=config.influxdb_org,
            lookback_time="48h"
        )
        
        calculation_time = datetime.now() - start_time
        
        # Get and display statistics
        stats = calculator.get_statistics()
        
        print(f"✓ Forecast accuracy calculation completed in {calculation_time.total_seconds():.2f} seconds")
        print(f"\n📊 Calculation Results:")
        print(f"  Errors calculated: {stats['errors_calculated']}")
        print(f"  Errors stored: {stats['errors_stored']}")
        print(f"  Errors failed: {stats['errors_failed']}")
        
        if stats['errors_calculated'] > 0:
            success_rate = (stats['errors_stored'] / stats['errors_calculated']) * 100
            print(f"  Success rate: {success_rate:.1f}%")
            print(f"  Average calculation time: {stats['average_calculation_time']:.3f}s per error")
        
        print(f"  Last calculation: {stats['last_calculation_time']}")
        
    finally:
        await calculator.disconnect()
        print("🔌 Disconnected from InfluxDB")


async def example_error_data_analysis():
    """Example: Analyze stored forecast errors."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Forecast Error Analysis")
    print("=" * 60)
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    # Initialize error storage
    error_storage = WeatherErrorStorage(config, logger, performance_monitor)
    
    try:
        # Connect to InfluxDB
        print("🔌 Connecting to InfluxDB...")
        connected = await error_storage.connect()
        
        if not connected:
            print("❌ Failed to connect to InfluxDB")
            return
        
        print("✓ Connected to InfluxDB")
        
        # Query errors for different forecast horizons
        forecast_horizons = [1, 6, 24, 48]
        start_time = datetime.utcnow() - timedelta(days=7)
        
        print(f"\n🔍 Analyzing forecast errors for last 7 days...")
        
        for horizon in forecast_horizons:
            try:
                errors = await error_storage.query_forecast_errors(
                    start_time=start_time,
                    forecast_horizon_hours=horizon,
                    source="openmeteo"
                )
                
                if errors:
                    print(f"\n📈 {horizon}-hour forecast horizon ({len(errors)} records):")
                    
                    # Calculate temperature error statistics
                    temp_abs_errors = [e.get('temp_abs_error') for e in errors if e.get('temp_abs_error') is not None]
                    temp_signed_errors = [e.get('temp_signed_error') for e in errors if e.get('temp_signed_error') is not None]
                    
                    if temp_abs_errors:
                        avg_abs_error = sum(temp_abs_errors) / len(temp_abs_errors)
                        max_abs_error = max(temp_abs_errors)
                        print(f"  Temperature - Avg absolute error: {avg_abs_error:.2f}°C, Max: {max_abs_error:.2f}°C")
                    
                    if temp_signed_errors:
                        avg_bias = sum(temp_signed_errors) / len(temp_signed_errors)
                        bias_direction = "over-prediction" if avg_bias > 0 else "under-prediction"
                        print(f"  Temperature - Bias: {avg_bias:.2f}°C ({bias_direction})")
                    
                    # Calculate pressure error statistics
                    pressure_abs_errors = [e.get('pressure_abs_error') for e in errors if e.get('pressure_abs_error') is not None]
                    if pressure_abs_errors:
                        avg_pressure_error = sum(pressure_abs_errors) / len(pressure_abs_errors)
                        print(f"  Pressure - Avg absolute error: {avg_pressure_error:.2f} hPa")
                    
                    # Calculate humidity error statistics
                    humidity_abs_errors = [e.get('humidity_abs_error') for e in errors if e.get('humidity_abs_error') is not None]
                    if humidity_abs_errors:
                        avg_humidity_error = sum(humidity_abs_errors) / len(humidity_abs_errors)
                        print(f"  Humidity - Avg absolute error: {avg_humidity_error:.2f}%")
                
                else:
                    print(f"\n⚠️  No error data found for {horizon}-hour horizon")
                    
            except Exception as e:
                print(f"❌ Error querying {horizon}-hour horizon data: {e}")
        
        # Get storage statistics
        stats = error_storage.get_error_statistics()
        print(f"\n📊 Error Storage Statistics:")
        print(f"  Total errors written: {stats['errors_written']}")
        print(f"  Total errors failed: {stats['errors_failed']}")
        print(f"  Last write time: {stats['last_write_time']}")
        print(f"  Average write time: {stats['average_write_time']:.3f}s")
        
    finally:
        await error_storage.disconnect()
        print("🔌 Disconnected from InfluxDB")


async def example_create_test_error_data():
    """Example: Create test error data for demonstration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Creating Test Error Data")
    print("=" * 60)
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    error_storage = WeatherErrorStorage(config, logger, performance_monitor)
    
    try:
        await error_storage.connect()
        print("✓ Connected to InfluxDB")
        
        # Create sample error data for demonstration
        test_errors = []
        base_time = datetime.utcnow() - timedelta(hours=24)
        
        for i in range(24):  # 24 hours of test data
            timestamp = base_time + timedelta(hours=i)
            
            # Simulate realistic forecast errors
            test_errors.append({
                'timestamp': timestamp,
                'forecast_horizon_hours': 24,
                'source': 'openmeteo',
                'temp_abs_error': 1.5 + (i * 0.1),  # Increasing error over time
                'temp_signed_error': -0.5 + (i * 0.05),  # Slight cold bias
                'pressure_abs_error': 2.0 + (i * 0.2),
                'pressure_signed_error': 1.0 - (i * 0.1),
                'humidity_abs_error': 5.0 + (i * 0.3),
                'humidity_signed_error': -2.0 + (i * 0.2)
            })
        
        print(f"📝 Creating {len(test_errors)} test error records...")
        
        # Write test error data
        success = await error_storage.write_forecast_errors_to_influxdb(
            test_errors, buffer=False
        )
        
        if success:
            print(f"✓ Successfully created {len(test_errors)} test error records")
            print("  These records can be used for testing Grafana dashboards")
            print("  and validating the forecast accuracy system")
        else:
            print("❌ Failed to create test error records")
        
    finally:
        await error_storage.disconnect()


async def main():
    """Run all forecast accuracy examples."""
    print("🚀 FORECAST ACCURACY SYSTEM EXAMPLES")
    print("=" * 80)
    print("This example demonstrates the forecast accuracy calculation system")
    print("and shows how to integrate it into your weather analysis workflow.")
    print("=" * 80)
    
    try:
        # Example 1: Sensor data retrieval
        sensor_df = await example_sensor_data_retrieval()
        
        # Example 2: Forecast accuracy calculation
        await example_forecast_accuracy_calculation()
        
        # Example 3: Error data analysis
        await example_error_data_analysis()
        
        # Example 4: Create test data (optional)
        print(f"\n❓ Would you like to create test error data for demonstration?")
        print("   (This will add sample data to your InfluxDB for testing)")
        # For automation, we'll skip the interactive part
        # await example_create_test_error_data()
        
        print(f"\n🎉 All examples completed successfully!")
        print(f"\n📚 Next Steps:")
        print(f"  1. Set up Grafana dashboards to visualize forecast accuracy")
        print(f"  2. Schedule regular accuracy calculations via cron/systemd")
        print(f"  3. Configure alerting for forecast accuracy thresholds")
        print(f"  4. Analyze seasonal patterns and forecast performance trends")
        
        print(f"\n📖 For more information, see docs/FORECAST_ACCURACY.md")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")
        print(f"   Make sure InfluxDB is running and properly configured")
        print(f"   Check your .env file for correct database settings")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)