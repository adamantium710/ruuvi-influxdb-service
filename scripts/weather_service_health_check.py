#!/usr/bin/env python3
"""
Weather Service Health Check Script

This script performs comprehensive health checks on the weather forecast system
components and provides detailed status information.

Usage:
    python scripts/weather_service_health_check.py [OPTIONS]

Options:
    --verbose       Enable verbose output
    --json          Output results in JSON format
    --check TYPE    Run specific check type (api, storage, accuracy, analysis, all)

Author: Weather Service Monitor
Created: 2025-01-07
"""

import asyncio
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import argparse

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import Config, ConfigurationError
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.influxdb.client import RuuviInfluxDBClient
from src.weather import (
    WeatherAPI, WeatherStorage, WeatherErrorStorage,
    ForecastAccuracyCalculator, WeatherDataAnalyzer,
    WeatherAPIError, WeatherStorageError, ForecastAccuracyError,
    DataAnalysisError
)


class WeatherServiceHealthChecker:
    """
    Comprehensive health checker for weather forecast system.
    
    Performs health checks on all components and provides detailed status reports.
    """
    
    def __init__(self, config: Config, verbose: bool = False):
        """
        Initialize health checker.
        
        Args:
            config: Application configuration
            verbose: Enable verbose logging
        """
        self.config = config
        self.verbose = verbose
        
        # Initialize logging
        self.logger = ProductionLogger(config)
        if not verbose:
            self.logger.setLevel('WARNING')
        
        self.performance_monitor = PerformanceMonitor(self.logger)
        
        # Health check results
        self.results = {
            'timestamp': datetime.utcnow().isoformat(),
            'overall_status': 'unknown',
            'checks': {},
            'summary': {
                'total_checks': 0,
                'passed_checks': 0,
                'failed_checks': 0,
                'warning_checks': 0
            }
        }
    
    async def check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity."""
        check_result = {
            'name': 'Configuration',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate configuration
            self.config.validate_configuration()
            
            # Check weather-specific configuration
            if not self.config.weather_enabled:
                check_result['warnings'].append("Weather forecasting is disabled")
            
            # Check required environment variables
            required_vars = [
                'INFLUXDB_HOST', 'INFLUXDB_TOKEN', 'INFLUXDB_ORG', 'INFLUXDB_BUCKET'
            ]
            
            missing_vars = []
            for var in required_vars:
                try:
                    getattr(self.config, var.lower())
                except ConfigurationError:
                    missing_vars.append(var)
            
            if missing_vars:
                check_result['errors'].append(f"Missing required variables: {', '.join(missing_vars)}")
            
            # Configuration summary
            check_result['details'] = {
                'weather_enabled': self.config.weather_enabled,
                'location': {
                    'latitude': self.config.weather_location_latitude,
                    'longitude': self.config.weather_location_longitude,
                    'timezone': self.config.weather_timezone
                },
                'api': {
                    'base_url': self.config.weather_api_base_url,
                    'timeout': self.config.weather_api_timeout,
                    'retry_attempts': self.config.weather_api_retry_attempts
                },
                'influxdb': {
                    'host': self.config.influxdb_host,
                    'port': self.config.influxdb_port,
                    'org': self.config.influxdb_org,
                    'bucket': self.config.influxdb_bucket,
                    'weather_bucket': self.config.weather_influxdb_bucket
                }
            }
            
            if check_result['errors']:
                check_result['status'] = 'failed'
            elif check_result['warnings']:
                check_result['status'] = 'warning'
            else:
                check_result['status'] = 'passed'
                
        except ConfigurationError as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Configuration validation failed: {e}")
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Unexpected configuration error: {e}")
        
        return check_result
    
    async def check_influxdb_connection(self) -> Dict[str, Any]:
        """Check InfluxDB connection and accessibility."""
        check_result = {
            'name': 'InfluxDB Connection',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        influxdb_client = None
        
        try:
            # Create InfluxDB client
            influxdb_client = RuuviInfluxDBClient(
                self.config, self.logger, self.performance_monitor
            )
            
            # Test connection
            connection_start = time.time()
            connected = await influxdb_client.connect()
            connection_time = time.time() - connection_start
            
            if not connected:
                check_result['status'] = 'failed'
                check_result['errors'].append("Failed to connect to InfluxDB")
                return check_result
            
            # Test basic query
            query_start = time.time()
            test_query = f'''
            from(bucket: "{self.config.influxdb_bucket}")
              |> range(start: -1m)
              |> limit(n: 1)
            '''
            
            try:
                await influxdb_client.query(test_query)
                query_time = time.time() - query_start
            except Exception as e:
                check_result['warnings'].append(f"Query test failed: {e}")
                query_time = None
            
            # Connection details
            check_result['details'] = {
                'connected': True,
                'connection_time': round(connection_time, 3),
                'query_time': round(query_time, 3) if query_time else None,
                'host': self.config.influxdb_host,
                'port': self.config.influxdb_port,
                'org': self.config.influxdb_org,
                'bucket': self.config.influxdb_bucket
            }
            
            if check_result['warnings']:
                check_result['status'] = 'warning'
            else:
                check_result['status'] = 'passed'
                
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"InfluxDB connection error: {e}")
        
        finally:
            if influxdb_client:
                await influxdb_client.disconnect()
        
        return check_result
    
    async def check_weather_api(self) -> Dict[str, Any]:
        """Check weather API connectivity and functionality."""
        check_result = {
            'name': 'Weather API',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        weather_api = None
        
        try:
            # Create weather API client
            weather_api = WeatherAPI(self.config, self.logger)
            
            # Test API health
            api_start = time.time()
            api_healthy = await weather_api.health_check()
            api_time = time.time() - api_start
            
            if not api_healthy:
                check_result['status'] = 'failed'
                check_result['errors'].append("Weather API health check failed")
            
            # Get API status
            circuit_breaker_status = weather_api.get_circuit_breaker_status()
            rate_limiter_status = weather_api.get_rate_limiter_status()
            
            # Test forecast fetch
            forecast_start = time.time()
            try:
                forecast_data = await weather_api.fetch_forecast_data(days=1)
                forecast_time = time.time() - forecast_start
                forecast_success = forecast_data is not None
                forecast_points = len(forecast_data.hourly_forecasts) if forecast_data else 0
            except Exception as e:
                forecast_time = time.time() - forecast_start
                forecast_success = False
                forecast_points = 0
                check_result['warnings'].append(f"Forecast fetch failed: {e}")
            
            # API details
            check_result['details'] = {
                'healthy': api_healthy,
                'response_time': round(api_time, 3),
                'forecast_test': {
                    'success': forecast_success,
                    'response_time': round(forecast_time, 3),
                    'data_points': forecast_points
                },
                'circuit_breaker': circuit_breaker_status,
                'rate_limiter': rate_limiter_status,
                'configuration': {
                    'base_url': self.config.weather_api_base_url,
                    'timeout': self.config.weather_api_timeout,
                    'location': {
                        'latitude': self.config.weather_location_latitude,
                        'longitude': self.config.weather_location_longitude
                    }
                }
            }
            
            if check_result['errors']:
                check_result['status'] = 'failed'
            elif check_result['warnings']:
                check_result['status'] = 'warning'
            else:
                check_result['status'] = 'passed'
                
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Weather API error: {e}")
        
        finally:
            if weather_api:
                weather_api.close()
        
        return check_result
    
    async def check_weather_storage(self) -> Dict[str, Any]:
        """Check weather data storage functionality."""
        check_result = {
            'name': 'Weather Storage',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        influxdb_client = None
        weather_storage = None
        
        try:
            # Create components
            influxdb_client = RuuviInfluxDBClient(
                self.config, self.logger, self.performance_monitor
            )
            
            if not await influxdb_client.connect():
                check_result['status'] = 'failed'
                check_result['errors'].append("Failed to connect to InfluxDB for storage test")
                return check_result
            
            weather_storage = WeatherStorage(
                self.config, self.logger, self.performance_monitor, influxdb_client
            )
            
            # Test storage health
            storage_healthy = await weather_storage.health_check()
            
            # Get storage statistics
            storage_stats = weather_storage.get_statistics()
            
            # Test recent data query
            try:
                start_time = datetime.utcnow() - timedelta(hours=24)
                recent_data = await weather_storage.query_weather_data(start_time)
                recent_data_count = len(recent_data)
            except Exception as e:
                recent_data_count = None
                check_result['warnings'].append(f"Recent data query failed: {e}")
            
            # Storage details
            check_result['details'] = {
                'healthy': storage_healthy,
                'statistics': storage_stats,
                'recent_data_points': recent_data_count,
                'bucket': self.config.weather_influxdb_bucket,
                'measurement': 'weather_forecasts'
            }
            
            if not storage_healthy:
                check_result['status'] = 'failed'
                check_result['errors'].append("Weather storage health check failed")
            elif check_result['warnings']:
                check_result['status'] = 'warning'
            else:
                check_result['status'] = 'passed'
                
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Weather storage error: {e}")
        
        finally:
            if influxdb_client:
                await influxdb_client.disconnect()
        
        return check_result
    
    async def check_forecast_accuracy(self) -> Dict[str, Any]:
        """Check forecast accuracy calculation functionality."""
        check_result = {
            'name': 'Forecast Accuracy',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        influxdb_client = None
        accuracy_calculator = None
        
        try:
            # Create components
            influxdb_client = RuuviInfluxDBClient(
                self.config, self.logger, self.performance_monitor
            )
            
            if not await influxdb_client.connect():
                check_result['status'] = 'failed'
                check_result['errors'].append("Failed to connect to InfluxDB for accuracy test")
                return check_result
            
            accuracy_calculator = ForecastAccuracyCalculator(
                self.config, self.logger, self.performance_monitor, influxdb_client
            )
            
            # Test accuracy calculator health
            accuracy_healthy = await accuracy_calculator.health_check()
            
            # Get accuracy statistics
            accuracy_stats = accuracy_calculator.get_statistics()
            
            # Check for recent sensor data
            try:
                from src.weather.accuracy import get_sensor_data_from_influxdb
                sensor_df = get_sensor_data_from_influxdb(
                    measurement="ruuvi_environmental",
                    fields=["temperature", "pressure", "humidity"],
                    time_range="24h",
                    influxdb_client=influxdb_client,
                    logger=self.logger
                )
                sensor_data_points = len(sensor_df)
            except Exception as e:
                sensor_data_points = None
                check_result['warnings'].append(f"Sensor data check failed: {e}")
            
            # Accuracy details
            check_result['details'] = {
                'healthy': accuracy_healthy,
                'statistics': accuracy_stats,
                'sensor_data_points': sensor_data_points,
                'error_measurement': 'weather_forecast_errors'
            }
            
            if not accuracy_healthy:
                check_result['status'] = 'failed'
                check_result['errors'].append("Forecast accuracy calculator health check failed")
            elif check_result['warnings']:
                check_result['status'] = 'warning'
            else:
                check_result['status'] = 'passed'
                
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Forecast accuracy error: {e}")
        
        finally:
            if influxdb_client:
                await influxdb_client.disconnect()
        
        return check_result
    
    async def check_data_analysis(self) -> Dict[str, Any]:
        """Check data analysis functionality."""
        check_result = {
            'name': 'Data Analysis',
            'status': 'unknown',
            'details': {},
            'errors': [],
            'warnings': []
        }
        
        influxdb_client = None
        data_analyzer = None
        
        try:
            # Create components
            influxdb_client = RuuviInfluxDBClient(
                self.config, self.logger, self.performance_monitor
            )
            
            if not await influxdb_client.connect():
                check_result['status'] = 'failed'
                check_result['errors'].append("Failed to connect to InfluxDB for analysis test")
                return check_result
            
            data_analyzer = WeatherDataAnalyzer(
                self.config, self.logger, self.performance_monitor, influxdb_client
            )
            
            # Test data retrieval
            try:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                sensor_df = await data_analyzer.get_sensor_data_for_analysis(
                    start_time=start_time,
                    end_time=end_time
                )
                
                analysis_data_points = len(sensor_df)
                analysis_columns = list(sensor_df.columns) if not sensor_df.empty else []
                
            except Exception as e:
                analysis_data_points = None
                analysis_columns = []
                check_result['warnings'].append(f"Data analysis retrieval failed: {e}")
            
            # Check reports directory
            reports_dir = Path("reports")
            reports_exist = reports_dir.exists()
            profile_report_exists = (reports_dir / "sensor_data_profile_report.html").exists()
            
            # Analysis details
            check_result['details'] = {
                'data_points_available': analysis_data_points,
                'data_columns': analysis_columns,
                'reports_directory': {
                    'exists': reports_exist,
                    'path': str(reports_dir.absolute()),
                    'profile_report_exists': profile_report_exists
                }
            }
            
            if analysis_data_points is None:
                check_result['status'] = 'warning'
            elif analysis_data_points == 0:
                check_result['status'] = 'warning'
                check_result['warnings'].append("No sensor data available for analysis")
            else:
                check_result['status'] = 'passed'
                
        except Exception as e:
            check_result['status'] = 'failed'
            check_result['errors'].append(f"Data analysis error: {e}")
        
        finally:
            if influxdb_client:
                await influxdb_client.disconnect()
        
        return check_result
    
    async def run_all_checks(self, check_types: Optional[list] = None) -> Dict[str, Any]:
        """
        Run all health checks.
        
        Args:
            check_types: List of specific check types to run, or None for all
            
        Returns:
            Dict[str, Any]: Complete health check results
        """
        if check_types is None:
            check_types = ['config', 'influxdb', 'api', 'storage', 'accuracy', 'analysis']
        
        # Available checks
        available_checks = {
            'config': self.check_configuration,
            'influxdb': self.check_influxdb_connection,
            'api': self.check_weather_api,
            'storage': self.check_weather_storage,
            'accuracy': self.check_forecast_accuracy,
            'analysis': self.check_data_analysis
        }
        
        # Run requested checks
        for check_type in check_types:
            if check_type in available_checks:
                if self.verbose:
                    print(f"Running {check_type} check...")
                
                try:
                    check_result = await available_checks[check_type]()
                    self.results['checks'][check_type] = check_result
                    
                    # Update summary
                    self.results['summary']['total_checks'] += 1
                    
                    if check_result['status'] == 'passed':
                        self.results['summary']['passed_checks'] += 1
                    elif check_result['status'] == 'warning':
                        self.results['summary']['warning_checks'] += 1
                    elif check_result['status'] == 'failed':
                        self.results['summary']['failed_checks'] += 1
                        
                except Exception as e:
                    error_result = {
                        'name': check_type.title(),
                        'status': 'failed',
                        'details': {},
                        'errors': [f"Check execution failed: {e}"],
                        'warnings': []
                    }
                    self.results['checks'][check_type] = error_result
                    self.results['summary']['total_checks'] += 1
                    self.results['summary']['failed_checks'] += 1
            else:
                print(f"Unknown check type: {check_type}")
        
        # Determine overall status
        if self.results['summary']['failed_checks'] > 0:
            self.results['overall_status'] = 'failed'
        elif self.results['summary']['warning_checks'] > 0:
            self.results['overall_status'] = 'warning'
        else:
            self.results['overall_status'] = 'passed'
        
        return self.results


def main():
    """Main entry point for health check script."""
    parser = argparse.ArgumentParser(
        description="Weather Service Health Check",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results in JSON format'
    )
    
    parser.add_argument(
        '--check',
        choices=['config', 'influxdb', 'api', 'storage', 'accuracy', 'analysis', 'all'],
        default='all',
        help='Run specific check type (default: all)'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = Config()
        
        # Create health checker
        health_checker = WeatherServiceHealthChecker(config, verbose=args.verbose)
        
        # Determine check types
        if args.check == 'all':
            check_types = None
        else:
            check_types = [args.check]
        
        # Run health checks
        results = asyncio.run(health_checker.run_all_checks(check_types))
        
        # Output results
        if args.json:
            print(json.dumps(results, indent=2, default=str))
        else:
            # Human-readable output
            print(f"\n=== Weather Service Health Check Results ===")
            print(f"Timestamp: {results['timestamp']}")
            print(f"Overall Status: {results['overall_status'].upper()}")
            print(f"Checks: {results['summary']['passed_checks']} passed, "
                  f"{results['summary']['warning_checks']} warnings, "
                  f"{results['summary']['failed_checks']} failed")
            
            # Show individual check results
            for check_name, check_result in results['checks'].items():
                status_symbol = {
                    'passed': '✓',
                    'warning': '⚠',
                    'failed': '✗',
                    'unknown': '?'
                }.get(check_result['status'], '?')
                
                print(f"\n{status_symbol} {check_result['name']}: {check_result['status'].upper()}")
                
                if check_result['errors']:
                    for error in check_result['errors']:
                        print(f"  ERROR: {error}")
                
                if check_result['warnings']:
                    for warning in check_result['warnings']:
                        print(f"  WARNING: {warning}")
                
                if args.verbose and check_result['details']:
                    print(f"  Details: {json.dumps(check_result['details'], indent=4, default=str)}")
        
        # Exit with appropriate code
        if results['overall_status'] == 'failed':
            return 1
        elif results['overall_status'] == 'warning':
            return 2
        else:
            return 0
            
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)