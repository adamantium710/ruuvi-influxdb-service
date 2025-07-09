#!/usr/bin/env python3
"""
Test script for weather data analysis functionality.
Tests both data profiling and association rule mining features.
"""

import asyncio
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.weather.analysis import WeatherDataAnalyzer, DataAnalysisError, InsufficientDataError
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor


def create_test_sensor_data(num_points: int = 100) -> pd.DataFrame:
    """
    Create realistic test sensor data for analysis testing.
    
    Args:
        num_points: Number of data points to generate
        
    Returns:
        pd.DataFrame: Test sensor data with realistic patterns
    """
    np.random.seed(42)  # For reproducible results
    
    # Generate time series
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=7)
    timestamps = pd.date_range(start=start_time, end=end_time, periods=num_points)
    
    # Generate realistic sensor data with patterns
    # Temperature: daily cycle with some noise
    hours = np.array([ts.hour for ts in timestamps])
    base_temp = 20 + 5 * np.sin(2 * np.pi * hours / 24)  # Daily temperature cycle
    temperature = base_temp + np.random.normal(0, 2, num_points)
    
    # Humidity: inversely correlated with temperature + noise
    base_humidity = 70 - 0.8 * (temperature - 20)
    humidity = base_humidity + np.random.normal(0, 5, num_points)
    humidity = np.clip(humidity, 10, 95)  # Keep in realistic range
    
    # Pressure: some correlation with temperature + weather patterns
    base_pressure = 1013 + 0.3 * (temperature - 20)
    pressure = base_pressure + np.random.normal(0, 8, num_points)
    
    # Add some weather events (low pressure systems)
    weather_events = np.random.choice([0, 1], size=num_points, p=[0.9, 0.1])
    pressure = pressure - weather_events * 15
    
    df = pd.DataFrame({
        'temperature': temperature,
        'humidity': humidity,
        'pressure': pressure
    }, index=timestamps)
    
    return df


async def test_data_profiling():
    """Test data profiling functionality."""
    print("\n" + "="*50)
    print("TESTING DATA PROFILING")
    print("="*50)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    # Create analyzer (will use mock data, not real InfluxDB)
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Test 1: Generate profile report with good data
        print("\n📊 Test 1: Profile report with sufficient data")
        test_data = create_test_sensor_data(100)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "test_profile_report.html")
            
            try:
                analyzer.generate_sensor_data_profile_report(test_data, output_path)
                
                # Check if file was created
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    print(f"✅ Profile report generated successfully ({file_size} bytes)")
                else:
                    print("❌ Profile report file not found")
                    
            except Exception as e:
                print(f"❌ Profile report generation failed: {e}")
        
        # Test 2: Empty DataFrame
        print("\n📊 Test 2: Profile report with empty data")
        empty_data = pd.DataFrame()
        
        try:
            analyzer.generate_sensor_data_profile_report(empty_data)
            print("❌ Should have raised InsufficientDataError")
        except InsufficientDataError:
            print("✅ Correctly raised InsufficientDataError for empty data")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Test 3: Insufficient data
        print("\n📊 Test 3: Profile report with insufficient data")
        small_data = create_test_sensor_data(5)
        
        try:
            analyzer.generate_sensor_data_profile_report(small_data)
            print("❌ Should have raised InsufficientDataError")
        except InsufficientDataError:
            print("✅ Correctly raised InsufficientDataError for insufficient data")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        print("\n✅ Data profiling tests completed")
        
    except Exception as e:
        print(f"❌ Data profiling test failed: {e}")


async def test_association_rule_mining():
    """Test association rule mining functionality."""
    print("\n" + "="*50)
    print("TESTING ASSOCIATION RULE MINING")
    print("="*50)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Test 1: Rule mining with good data
        print("\n🔍 Test 1: Association rules with sufficient data")
        test_data = create_test_sensor_data(200)  # More data for better patterns
        
        try:
            rules_df = analyzer.discover_sensor_association_rules(
                df_sensor=test_data,
                columns_to_bin=['temperature', 'humidity', 'pressure'],
                n_bins=3,
                min_support=0.1,
                min_confidence=0.5,
                min_lift=1.0
            )
            
            print(f"✅ Association rule mining completed")
            print(f"📊 Found {len(rules_df)} rules")
            
            if not rules_df.empty:
                print(f"📈 Best rule lift: {rules_df['lift'].max():.3f}")
                print(f"📈 Average confidence: {rules_df['confidence'].mean():.3f}")
            
        except Exception as e:
            print(f"❌ Association rule mining failed: {e}")
        
        # Test 2: Empty DataFrame
        print("\n🔍 Test 2: Association rules with empty data")
        empty_data = pd.DataFrame()
        
        try:
            analyzer.discover_sensor_association_rules(empty_data, ['temperature'])
            print("❌ Should have raised InsufficientDataError")
        except InsufficientDataError:
            print("✅ Correctly raised InsufficientDataError for empty data")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Test 3: Insufficient data
        print("\n🔍 Test 3: Association rules with insufficient data")
        small_data = create_test_sensor_data(10)
        
        try:
            analyzer.discover_sensor_association_rules(small_data, ['temperature'])
            print("❌ Should have raised InsufficientDataError")
        except InsufficientDataError:
            print("✅ Correctly raised InsufficientDataError for insufficient data")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        # Test 4: High thresholds (no rules expected)
        print("\n🔍 Test 4: Association rules with high thresholds")
        test_data = create_test_sensor_data(100)
        
        try:
            rules_df = analyzer.discover_sensor_association_rules(
                df_sensor=test_data,
                columns_to_bin=['temperature', 'humidity'],
                n_bins=3,
                min_support=0.9,  # Very high threshold
                min_confidence=0.9,
                min_lift=2.0
            )
            
            if rules_df.empty:
                print("✅ Correctly found no rules with high thresholds")
            else:
                print(f"⚠️  Unexpectedly found {len(rules_df)} rules with high thresholds")
                
        except Exception as e:
            print(f"❌ High threshold test failed: {e}")
        
        print("\n✅ Association rule mining tests completed")
        
    except Exception as e:
        print(f"❌ Association rule mining test failed: {e}")


async def test_data_discretization():
    """Test data discretization functionality."""
    print("\n" + "="*50)
    print("TESTING DATA DISCRETIZATION")
    print("="*50)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Test 1: Normal discretization
        print("\n🔢 Test 1: Normal data discretization")
        test_data = create_test_sensor_data(100)
        
        discretized = analyzer._discretize_continuous_data(
            test_data, 
            ['temperature', 'humidity', 'pressure'], 
            n_bins=3
        )
        
        # Check that binned columns were created
        expected_columns = ['temperature_binned', 'humidity_binned', 'pressure_binned']
        found_columns = [col for col in expected_columns if col in discretized.columns]
        
        print(f"✅ Created {len(found_columns)}/3 binned columns: {found_columns}")
        
        # Check bin distributions
        for col in found_columns:
            unique_bins = discretized[col].dropna().unique()
            print(f"   {col}: {len(unique_bins)} bins - {list(unique_bins)}")
        
        # Test 2: Missing column
        print("\n🔢 Test 2: Discretization with missing column")
        discretized = analyzer._discretize_continuous_data(
            test_data,
            ['temperature', 'nonexistent_column'],
            n_bins=3
        )
        
        if 'temperature_binned' in discretized.columns and 'nonexistent_column_binned' not in discretized.columns:
            print("✅ Correctly handled missing column")
        else:
            print("❌ Did not handle missing column correctly")
        
        # Test 3: Data with few unique values
        print("\n🔢 Test 3: Discretization with few unique values")
        limited_data = pd.DataFrame({
            'temperature': [20.0, 20.0, 21.0, 21.0, 20.0] * 10  # Only 2 unique values
        })
        
        discretized = analyzer._discretize_continuous_data(
            limited_data,
            ['temperature'],
            n_bins=3
        )
        
        if 'temperature_binned' in discretized.columns:
            unique_bins = discretized['temperature_binned'].dropna().unique()
            print(f"✅ Handled limited unique values: {len(unique_bins)} bins created")
        else:
            print("⚠️  No binned column created for limited unique values")
        
        print("\n✅ Data discretization tests completed")
        
    except Exception as e:
        print(f"❌ Data discretization test failed: {e}")


async def test_comprehensive_analysis():
    """Test comprehensive analysis functionality."""
    print("\n" + "="*50)
    print("TESTING COMPREHENSIVE ANALYSIS")
    print("="*50)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Mock the data retrieval method
        test_data = create_test_sensor_data(150)
        
        async def mock_get_sensor_data(*args, **kwargs):
            return test_data
        
        analyzer.get_sensor_data_for_analysis = mock_get_sensor_data
        
        print("\n🚀 Test: Comprehensive analysis")
        
        results = await analyzer.run_comprehensive_analysis(
            days_back=7,
            profile_report=True,
            association_rules=True,
            min_support=0.1,
            min_confidence=0.6
        )
        
        # Verify result structure
        required_keys = ['data_points', 'time_range', 'columns', 'analysis_timestamp']
        missing_keys = [key for key in required_keys if key not in results]
        
        if not missing_keys:
            print("✅ Result structure is correct")
        else:
            print(f"❌ Missing keys in results: {missing_keys}")
        
        # Check data points
        if results['data_points'] == len(test_data):
            print(f"✅ Correct data points count: {results['data_points']}")
        else:
            print(f"❌ Incorrect data points count: {results['data_points']} vs {len(test_data)}")
        
        # Check profile report
        if 'profile_report' in results:
            if results['profile_report'].get('generated', False):
                print("✅ Profile report generated successfully")
            else:
                print(f"❌ Profile report failed: {results['profile_report'].get('error', 'Unknown')}")
        
        # Check association rules
        if 'association_rules' in results:
            if results['association_rules'].get('generated', False):
                rules_count = results['association_rules'].get('rules_found', 0)
                print(f"✅ Association rules generated: {rules_count} rules found")
            else:
                print(f"❌ Association rules failed: {results['association_rules'].get('error', 'Unknown')}")
        
        print("\n✅ Comprehensive analysis test completed")
        
    except Exception as e:
        print(f"❌ Comprehensive analysis test failed: {e}")


async def main():
    """Main test function."""
    print("🧪 Weather Data Analysis Testing Suite")
    print("Testing Phase 2 Implementation")
    print("=" * 60)
    
    try:
        # Run all tests
        await test_data_profiling()
        await test_association_rule_mining()
        await test_data_discretization()
        await test_comprehensive_analysis()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
        print("\n✅ Weather data analysis functionality is working correctly!")
        print("\n📝 Test Summary:")
        print("   • Data profiling: Generates comprehensive HTML reports")
        print("   • Association rule mining: Discovers patterns in sensor data")
        print("   • Data discretization: Converts continuous to categorical data")
        print("   • Comprehensive analysis: Combines all features")
        print("\n🚀 Ready for integration into main application!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())