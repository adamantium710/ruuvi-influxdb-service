#!/usr/bin/env python3
"""
Weather Forecast Main Orchestrator Script

This script implements the main orchestrator for Phase 2 weather forecast system
as specified in the project requirements. It coordinates all weather components
into a cohesive workflow.

Workflow (Phase 2 Section 6):
1. Fetch current forecast
2. Store forecast in `weather_forecasts` measurement in InfluxDB
3. Periodically fetch historical sensor data and corresponding forecast data
4. Calculate and store forecast errors in `weather_forecast_errors` measurement
5. Run data profiling on sensor data and generate HTML report
6. Run association rule mining on sensor data and print/log results

Author: Weather Data Orchestrator
Created: 2025-01-07
"""

import asyncio
import sys
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

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
    DataAnalysisError, InsufficientDataError
)


class WeatherForecastOrchestrator:
    """
    Main orchestrator for weather forecast system.
    
    Coordinates all Phase 2 components according to the specified workflow:
    - Weather data fetching and storage
    - Forecast accuracy calculation
    - Data analysis and reporting
    """
    
    def __init__(self, config: Config):
        """
        Initialize the weather forecast orchestrator.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = ProductionLogger(config)
        self.performance_monitor = PerformanceMonitor(self.logger)
        
        # Initialize components
        self.influxdb_client: Optional[RuuviInfluxDBClient] = None
        self.weather_api: Optional[WeatherAPI] = None
        self.weather_storage: Optional[WeatherStorage] = None
        self.error_storage: Optional[WeatherErrorStorage] = None
        self.accuracy_calculator: Optional[ForecastAccuracyCalculator] = None
        self.data_analyzer: Optional[WeatherDataAnalyzer] = None
        
        # Orchestrator state
        self._running = False
        self._shutdown_requested = False
        
        # Statistics
        self.stats = {
            'runs_completed': 0,
            'runs_failed': 0,
            'forecasts_fetched': 0,
            'forecasts_stored': 0,
            'errors_calculated': 0,
            'reports_generated': 0,
            'last_run_time': None,
            'total_run_time': 0.0
        }
        
        self.logger.info("WeatherForecastOrchestrator initialized")
    
    async def initialize(self) -> bool:
        """
        Initialize all components and connections.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing weather forecast orchestrator components...")
            
            # Validate configuration
            if not self.config.weather_enabled:
                raise ConfigurationError("Weather forecasting is not enabled in configuration")
            
            self.config.validate_configuration()
            
            # Initialize InfluxDB client
            self.influxdb_client = RuuviInfluxDBClient(
                self.config, self.logger, self.performance_monitor
            )
            
            if not await self.influxdb_client.connect():
                raise RuntimeError("Failed to connect to InfluxDB")
            
            # Initialize weather API
            self.weather_api = WeatherAPI(self.config, self.logger)
            
            # Initialize storage components
            self.weather_storage = WeatherStorage(
                self.config, self.logger, self.performance_monitor, self.influxdb_client
            )
            
            self.error_storage = WeatherErrorStorage(
                self.config, self.logger, self.performance_monitor, self.influxdb_client
            )
            
            # Initialize accuracy calculator
            self.accuracy_calculator = ForecastAccuracyCalculator(
                self.config, self.logger, self.performance_monitor, self.influxdb_client
            )
            
            # Initialize data analyzer
            self.data_analyzer = WeatherDataAnalyzer(
                self.config, self.logger, self.performance_monitor, self.influxdb_client
            )
            
            # Perform health checks
            await self._perform_health_checks()
            
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize orchestrator: {e}")
            return False
    
    async def _perform_health_checks(self):
        """Perform health checks on all components."""
        self.logger.info("Performing component health checks...")
        
        # Check weather API
        if not await self.weather_api.health_check():
            raise RuntimeError("Weather API health check failed")
        
        # Check storage components
        if not await self.weather_storage.health_check():
            raise RuntimeError("Weather storage health check failed")
        
        if not await self.error_storage.health_check():
            raise RuntimeError("Weather error storage health check failed")
        
        # Check accuracy calculator
        if not await self.accuracy_calculator.health_check():
            raise RuntimeError("Forecast accuracy calculator health check failed")
        
        self.logger.info("All component health checks passed")
    
    async def run_workflow(self) -> bool:
        """
        Execute the complete Phase 2 workflow.
        
        Returns:
            bool: True if workflow completed successfully
        """
        workflow_start_time = time.time()
        
        try:
            self.logger.info("=== Starting Weather Forecast Workflow ===")
            
            # Step 1: Fetch current forecast
            self.logger.info("Step 1: Fetching current weather forecast...")
            forecast_data = await self._fetch_current_forecast()
            
            if not forecast_data:
                self.logger.error("Failed to fetch forecast data, aborting workflow")
                return False
            
            # Step 2: Store forecast in InfluxDB
            self.logger.info("Step 2: Storing forecast data in InfluxDB...")
            if not await self._store_forecast_data(forecast_data):
                self.logger.error("Failed to store forecast data")
                return False
            
            # Step 3: Calculate and store forecast errors
            self.logger.info("Step 3: Calculating and storing forecast errors...")
            if not await self._calculate_forecast_errors():
                self.logger.warning("Forecast error calculation failed, continuing workflow")
            
            # Step 4: Generate data profiling report
            self.logger.info("Step 4: Generating sensor data profiling report...")
            if not await self._generate_data_profile_report():
                self.logger.warning("Data profiling report generation failed, continuing workflow")
            
            # Step 5: Run association rule mining
            self.logger.info("Step 5: Running association rule mining on sensor data...")
            if not await self._run_association_rule_mining():
                self.logger.warning("Association rule mining failed, continuing workflow")
            
            # Update statistics
            workflow_time = time.time() - workflow_start_time
            self.stats['runs_completed'] += 1
            self.stats['last_run_time'] = datetime.utcnow()
            self.stats['total_run_time'] += workflow_time
            
            # Record performance metrics
            self.performance_monitor.record_metric("workflow_execution_time", workflow_time)
            self.performance_monitor.record_metric("workflow_runs_completed", 1)
            
            self.logger.info(f"=== Weather Forecast Workflow Completed Successfully in {workflow_time:.2f}s ===")
            return True
            
        except Exception as e:
            self.stats['runs_failed'] += 1
            self.performance_monitor.record_metric("workflow_runs_failed", 1)
            self.logger.error(f"Weather forecast workflow failed: {e}")
            return False
    
    async def _fetch_current_forecast(self):
        """Fetch current weather forecast data."""
        try:
            forecast_data = await self.weather_api.fetch_forecast_data(
                days=self.config.weather_forecast_days
            )
            
            if forecast_data:
                self.stats['forecasts_fetched'] += 1
                self.logger.info(
                    f"Successfully fetched forecast with {len(forecast_data.hourly_forecasts)} hourly points"
                )
                return forecast_data
            else:
                self.logger.error("No forecast data received from API")
                return None
                
        except WeatherAPIError as e:
            self.logger.error(f"Weather API error: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching forecast: {e}")
            return None
    
    async def _store_forecast_data(self, forecast_data) -> bool:
        """Store forecast data in InfluxDB."""
        try:
            success = await self.weather_storage.write_forecast_to_influxdb(
                forecast_data, buffer=False
            )
            
            if success:
                self.stats['forecasts_stored'] += 1
                self.logger.info("Forecast data stored successfully")
                return True
            else:
                self.logger.error("Failed to store forecast data")
                return False
                
        except WeatherStorageError as e:
            self.logger.error(f"Weather storage error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error storing forecast: {e}")
            return False
    
    async def _calculate_forecast_errors(self) -> bool:
        """Calculate and store forecast accuracy errors."""
        try:
            await self.accuracy_calculator.calculate_and_store_forecast_errors(
                bucket_sensor=self.config.influxdb_bucket,
                bucket_forecast=self.config.weather_influxdb_bucket,
                bucket_errors=self.config.weather_influxdb_bucket,
                org=self.config.influxdb_org,
                lookback_time="48h"
            )
            
            # Get statistics
            accuracy_stats = self.accuracy_calculator.get_statistics()
            errors_calculated = accuracy_stats.get('errors_calculated', 0)
            
            self.stats['errors_calculated'] += errors_calculated
            self.logger.info(f"Calculated and stored {errors_calculated} forecast errors")
            return True
            
        except ForecastAccuracyError as e:
            self.logger.error(f"Forecast accuracy calculation error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error calculating forecast errors: {e}")
            return False
    
    async def _generate_data_profile_report(self) -> bool:
        """Generate comprehensive data profiling report."""
        try:
            # Get sensor data for the last 30 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            
            sensor_df = await self.data_analyzer.get_sensor_data_for_analysis(
                start_time=start_time,
                end_time=end_time
            )
            
            if sensor_df.empty:
                self.logger.warning("No sensor data available for profiling report")
                return False
            
            # Generate profile report
            self.data_analyzer.generate_sensor_data_profile_report(
                sensor_df,
                output_path="reports/sensor_data_profile_report.html"
            )
            
            self.stats['reports_generated'] += 1
            self.logger.info(f"Data profiling report generated for {len(sensor_df)} data points")
            return True
            
        except (DataAnalysisError, InsufficientDataError) as e:
            self.logger.error(f"Data analysis error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error generating profile report: {e}")
            return False
    
    async def _run_association_rule_mining(self) -> bool:
        """Run association rule mining on sensor data."""
        try:
            # Get sensor data for the last 30 days
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=30)
            
            sensor_df = await self.data_analyzer.get_sensor_data_for_analysis(
                start_time=start_time,
                end_time=end_time
            )
            
            if sensor_df.empty:
                self.logger.warning("No sensor data available for association rule mining")
                return False
            
            # Run association rule mining
            rules_df = self.data_analyzer.discover_sensor_association_rules(
                sensor_df,
                columns_to_bin=['temperature', 'humidity', 'pressure'],
                n_bins=3,
                min_support=0.05,
                min_confidence=0.5,
                min_lift=1.0
            )
            
            if not rules_df.empty:
                self.logger.info(f"Association rule mining completed: {len(rules_df)} rules discovered")
            else:
                self.logger.info("Association rule mining completed: no significant rules found")
            
            return True
            
        except (DataAnalysisError, InsufficientDataError) as e:
            self.logger.error(f"Association rule mining error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in association rule mining: {e}")
            return False
    
    async def run_continuous(self, interval_minutes: Optional[int] = None):
        """
        Run the orchestrator continuously with specified interval.
        
        Args:
            interval_minutes: Interval between runs in minutes (defaults to config value)
        """
        if interval_minutes is None:
            interval_minutes = self.config.weather_forecast_interval
        
        interval_seconds = interval_minutes * 60
        
        self.logger.info(f"Starting continuous operation with {interval_minutes} minute intervals")
        self._running = True
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self._shutdown_requested = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            while self._running and not self._shutdown_requested:
                # Run workflow
                success = await self.run_workflow()
                
                if not success:
                    self.logger.error("Workflow execution failed")
                
                # Log current statistics
                self._log_statistics()
                
                # Check for shutdown request
                if self._shutdown_requested:
                    break
                
                # Wait for next interval
                self.logger.info(f"Waiting {interval_minutes} minutes until next run...")
                
                # Sleep in chunks to allow for responsive shutdown
                sleep_chunks = interval_seconds // 10  # 10-second chunks
                for _ in range(int(sleep_chunks)):
                    if self._shutdown_requested:
                        break
                    await asyncio.sleep(10)
                
                # Sleep remaining time
                remaining_sleep = interval_seconds % 10
                if remaining_sleep > 0 and not self._shutdown_requested:
                    await asyncio.sleep(remaining_sleep)
        
        except Exception as e:
            self.logger.error(f"Error in continuous operation: {e}")
        finally:
            self._running = False
            self.logger.info("Continuous operation stopped")
    
    def _log_statistics(self):
        """Log current orchestrator statistics."""
        self.logger.info("=== Orchestrator Statistics ===")
        self.logger.info(f"Runs completed: {self.stats['runs_completed']}")
        self.logger.info(f"Runs failed: {self.stats['runs_failed']}")
        self.logger.info(f"Forecasts fetched: {self.stats['forecasts_fetched']}")
        self.logger.info(f"Forecasts stored: {self.stats['forecasts_stored']}")
        self.logger.info(f"Errors calculated: {self.stats['errors_calculated']}")
        self.logger.info(f"Reports generated: {self.stats['reports_generated']}")
        
        if self.stats['last_run_time']:
            self.logger.info(f"Last run: {self.stats['last_run_time']}")
        
        if self.stats['runs_completed'] > 0:
            avg_time = self.stats['total_run_time'] / self.stats['runs_completed']
            self.logger.info(f"Average run time: {avg_time:.2f}s")
    
    async def shutdown(self):
        """Gracefully shutdown the orchestrator."""
        self.logger.info("Shutting down weather forecast orchestrator...")
        
        self._running = False
        self._shutdown_requested = True
        
        # Close weather API session
        if self.weather_api:
            self.weather_api.close()
        
        # Disconnect from InfluxDB
        if self.influxdb_client:
            await self.influxdb_client.disconnect()
        
        self.logger.info("Weather forecast orchestrator shutdown complete")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current orchestrator status.
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            'running': self._running,
            'shutdown_requested': self._shutdown_requested,
            'statistics': self.stats.copy(),
            'components': {
                'influxdb_connected': self.influxdb_client.is_connected() if self.influxdb_client else False,
                'weather_api_status': self.weather_api.get_circuit_breaker_status() if self.weather_api else None,
                'weather_storage_stats': self.weather_storage.get_statistics() if self.weather_storage else None,
                'accuracy_calculator_stats': self.accuracy_calculator.get_statistics() if self.accuracy_calculator else None
            }
        }


async def main():
    """Main entry point for the weather forecast orchestrator."""
    try:
        # Load configuration
        config = Config()
        
        # Create orchestrator
        orchestrator = WeatherForecastOrchestrator(config)
        
        # Initialize components
        if not await orchestrator.initialize():
            print("Failed to initialize orchestrator", file=sys.stderr)
            return 1
        
        # Determine run mode
        if len(sys.argv) > 1 and sys.argv[1] == "--once":
            # Single run mode
            print("Running weather forecast workflow once...")
            success = await orchestrator.run_workflow()
            
            if success:
                print("Workflow completed successfully")
                return 0
            else:
                print("Workflow failed", file=sys.stderr)
                return 1
        else:
            # Continuous mode
            print("Starting continuous weather forecast orchestrator...")
            print("Press Ctrl+C to stop gracefully")
            
            try:
                await orchestrator.run_continuous()
            except KeyboardInterrupt:
                print("\nReceived interrupt signal, shutting down...")
            
            return 0
    
    except ConfigurationError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    finally:
        if 'orchestrator' in locals():
            await orchestrator.shutdown()


if __name__ == "__main__":
    # Run the orchestrator
    exit_code = asyncio.run(main())
    sys.exit(exit_code)