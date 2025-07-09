#!/usr/bin/env python3
"""
Weather Data Analysis Example Script

Demonstrates the data analysis features implemented in Phase 2:
1. Automated data profiling using ydata-profiling
2. Association rule mining using mlxtend

This script shows how to use the WeatherDataAnalyzer to generate
comprehensive reports and discover patterns in sensor data.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.weather.analysis import WeatherDataAnalyzer, DataAnalysisError, InsufficientDataError
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor


async def demonstrate_data_profiling():
    """Demonstrate automated data profiling functionality."""
    print("\n" + "="*60)
    print("WEATHER DATA PROFILING DEMONSTRATION")
    print("="*60)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Connect to InfluxDB
        print("Connecting to InfluxDB...")
        connected = await analyzer.connect()
        
        if not connected:
            print("❌ Failed to connect to InfluxDB")
            return
        
        print("✅ Connected to InfluxDB successfully")
        
        # Retrieve sensor data for analysis (last 7 days)
        print("\nRetrieving sensor data for analysis...")
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=7)
        
        try:
            df_sensor = await analyzer.get_sensor_data_for_analysis(
                start_time=start_time,
                end_time=end_time
            )
            
            print(f"✅ Retrieved {len(df_sensor)} sensor data points")
            print(f"📊 Data columns: {list(df_sensor.columns)}")
            print(f"📅 Time range: {df_sensor.index.min()} to {df_sensor.index.max()}")
            
            # Display basic statistics
            print("\n📈 Basic Statistics:")
            print(df_sensor.describe())
            
        except InsufficientDataError as e:
            print(f"⚠️  Insufficient data for analysis: {e}")
            return
        
        # Generate data profiling report
        print("\n🔍 Generating comprehensive data profile report...")
        
        try:
            analyzer.generate_sensor_data_profile_report(
                df_sensor=df_sensor,
                output_path="reports/sensor_data_profile_report.html"
            )
            
            print("✅ Data profile report generated successfully!")
            print("📄 Report saved to: reports/sensor_data_profile_report.html")
            print("\n📋 The report includes:")
            print("   • Dataset overview and statistics")
            print("   • Variable distributions and histograms")
            print("   • Correlation analysis")
            print("   • Missing value analysis")
            print("   • Data quality warnings")
            print("   • Sample data preview")
            
        except Exception as e:
            print(f"❌ Failed to generate profile report: {e}")
    
    except Exception as e:
        print(f"❌ Error in data profiling demonstration: {e}")
    
    finally:
        await analyzer.disconnect()


async def demonstrate_association_rule_mining():
    """Demonstrate association rule mining functionality."""
    print("\n" + "="*60)
    print("ASSOCIATION RULE MINING DEMONSTRATION")
    print("="*60)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Connect to InfluxDB
        print("Connecting to InfluxDB...")
        connected = await analyzer.connect()
        
        if not connected:
            print("❌ Failed to connect to InfluxDB")
            return
        
        print("✅ Connected to InfluxDB successfully")
        
        # Retrieve sensor data for analysis (last 14 days for more patterns)
        print("\nRetrieving sensor data for pattern analysis...")
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=14)
        
        try:
            df_sensor = await analyzer.get_sensor_data_for_analysis(
                start_time=start_time,
                end_time=end_time
            )
            
            print(f"✅ Retrieved {len(df_sensor)} sensor data points")
            
        except InsufficientDataError as e:
            print(f"⚠️  Insufficient data for analysis: {e}")
            return
        
        # Perform association rule mining with different parameter sets
        rule_configs = [
            {
                "name": "Conservative Rules",
                "params": {
                    "columns_to_bin": ['temperature', 'humidity', 'pressure'],
                    "n_bins": 3,
                    "min_support": 0.1,
                    "min_confidence": 0.7,
                    "min_lift": 1.2
                }
            },
            {
                "name": "Exploratory Rules",
                "params": {
                    "columns_to_bin": ['temperature', 'humidity', 'pressure'],
                    "n_bins": 3,
                    "min_support": 0.05,
                    "min_confidence": 0.5,
                    "min_lift": 1.0
                }
            }
        ]
        
        for config_info in rule_configs:
            print(f"\n🔍 Mining {config_info['name']}...")
            print(f"Parameters: {config_info['params']}")
            
            try:
                rules_df = analyzer.discover_sensor_association_rules(
                    df_sensor=df_sensor,
                    **config_info['params']
                )
                
                if not rules_df.empty:
                    print(f"✅ Found {len(rules_df)} significant association rules")
                    
                    # Display top 5 rules
                    print(f"\n🏆 Top 5 {config_info['name']}:")
                    top_rules = rules_df.head(5)
                    
                    for idx, (_, rule) in enumerate(top_rules.iterrows(), 1):
                        print(f"  {idx}. {rule['antecedents_str']} → {rule['consequents_str']}")
                        print(f"     Support: {rule['support']:.3f}, "
                              f"Confidence: {rule['confidence']:.3f}, "
                              f"Lift: {rule['lift']:.3f}")
                    
                    # Rule interpretation examples
                    if len(rules_df) > 0:
                        best_rule = rules_df.iloc[0]
                        print(f"\n💡 Rule Interpretation Example:")
                        print(f"   Rule: {best_rule['antecedents_str']} → {best_rule['consequents_str']}")
                        print(f"   Meaning: When {best_rule['antecedents_str']}, "
                              f"then {best_rule['consequents_str']} occurs "
                              f"{best_rule['confidence']:.1%} of the time")
                        print(f"   Lift: {best_rule['lift']:.2f}x more likely than random chance")
                
                else:
                    print(f"⚠️  No rules found with current parameters")
                    
            except Exception as e:
                print(f"❌ Error in rule mining: {e}")
    
    except Exception as e:
        print(f"❌ Error in association rule mining demonstration: {e}")
    
    finally:
        await analyzer.disconnect()


async def demonstrate_comprehensive_analysis():
    """Demonstrate comprehensive analysis combining both features."""
    print("\n" + "="*60)
    print("COMPREHENSIVE ANALYSIS DEMONSTRATION")
    print("="*60)
    
    # Initialize components
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
    
    try:
        # Connect to InfluxDB
        print("Connecting to InfluxDB...")
        connected = await analyzer.connect()
        
        if not connected:
            print("❌ Failed to connect to InfluxDB")
            return
        
        print("✅ Connected to InfluxDB successfully")
        
        # Run comprehensive analysis
        print("\n🚀 Running comprehensive analysis...")
        print("This will generate both profile report and association rules")
        
        try:
            results = await analyzer.run_comprehensive_analysis(
                days_back=10,
                profile_report=True,
                association_rules=True,
                columns_to_bin=['temperature', 'humidity', 'pressure'],
                n_bins=3,
                min_support=0.08,
                min_confidence=0.6,
                min_lift=1.1
            )
            
            print("✅ Comprehensive analysis completed!")
            
            # Display results summary
            print(f"\n📊 Analysis Summary:")
            print(f"   • Data points analyzed: {results['data_points']}")
            print(f"   • Time range: {results['time_range']['days']} days")
            print(f"   • Columns analyzed: {', '.join(results['columns'])}")
            
            # Profile report results
            if results['profile_report']['generated']:
                print(f"   • Profile report: ✅ Generated")
                print(f"     Path: {results['profile_report']['path']}")
            else:
                print(f"   • Profile report: ❌ Failed")
                print(f"     Error: {results['profile_report'].get('error', 'Unknown')}")
            
            # Association rules results
            if results['association_rules']['generated']:
                rules_count = results['association_rules']['rules_found']
                print(f"   • Association rules: ✅ {rules_count} rules found")
                
                if 'top_rules' in results['association_rules']:
                    print(f"\n🏆 Top Association Rules:")
                    for i, rule in enumerate(results['association_rules']['top_rules'][:3], 1):
                        print(f"     {i}. {rule['antecedents']} → {rule['consequents']}")
                        print(f"        Confidence: {rule['confidence']:.3f}, Lift: {rule['lift']:.3f}")
            else:
                print(f"   • Association rules: ❌ Failed")
                print(f"     Error: {results['association_rules'].get('error', 'Unknown')}")
            
            print(f"\n⏰ Analysis completed at: {results['analysis_timestamp']}")
            
        except Exception as e:
            print(f"❌ Comprehensive analysis failed: {e}")
    
    except Exception as e:
        print(f"❌ Error in comprehensive analysis demonstration: {e}")
    
    finally:
        await analyzer.disconnect()


async def main():
    """Main demonstration function."""
    print("🌡️  Weather Data Analysis Demonstration")
    print("Phase 2 Implementation - Data Profiling & Association Rule Mining")
    print("=" * 70)
    
    try:
        # Run all demonstrations
        await demonstrate_data_profiling()
        await demonstrate_association_rule_mining()
        await demonstrate_comprehensive_analysis()
        
        print("\n" + "="*60)
        print("DEMONSTRATION COMPLETED")
        print("="*60)
        print("\n📁 Generated Files:")
        print("   • reports/sensor_data_profile_report.html - Comprehensive data profile")
        print("\n💡 Next Steps:")
        print("   • Open the HTML report in your browser to explore data insights")
        print("   • Review the association rules printed above for sensor patterns")
        print("   • Integrate these analysis functions into your main application")
        print("   • Set up periodic analysis runs for continuous monitoring")
        
    except KeyboardInterrupt:
        print("\n⚠️  Demonstration interrupted by user")
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())