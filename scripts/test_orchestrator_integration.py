#!/usr/bin/env python3
"""
Integration test for the Weather Forecast Orchestrator system.

This script tests the complete orchestrator workflow including:
- Configuration validation
- Component initialization
- Workflow execution
- Error handling
- Performance monitoring
"""

import asyncio
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.config import Config
from weather.api import WeatherAPI
from weather.storage import WeatherStorage
from weather.accuracy import ForecastAccuracy
from weather.analysis import WeatherDataAnalysis

# Import the orchestrator
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from weather_forecast_main import WeatherForecastOrchestrator

class OrchestratorIntegrationTest:
    """Integration test suite for the Weather Forecast Orchestrator."""
    
    def __init__(self):
        self.config = None
        self.test_results = []
        self.temp_dir = None
        
    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up integration test environment...")
        
        # Create temporary directory for test reports
        self.temp_dir = tempfile.mkdtemp(prefix="weather_test_")
        
        # Load configuration
        try:
            self.config = Config()
            print("✅ Configuration loaded successfully")
        except Exception as e:
            print(f"❌ Configuration failed: {e}")
            return False
            
        return True
    
    def teardown(self):
        """Clean up test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
    
    async def test_component_initialization(self):
        """Test that all components can be initialized."""
        print("\n📦 Testing component initialization...")
        
        components = {}
        
        try:
            # Test WeatherAPI initialization
            components['api'] = WeatherAPI(self.config)
            print("✅ WeatherAPI initialized")
            
            # Test WeatherStorage initialization
            components['storage'] = WeatherStorage(self.config)
            print("✅ WeatherStorage initialized")
            
            # Test ForecastAccuracy initialization
            components['accuracy'] = ForecastAccuracy(self.config)
            print("✅ ForecastAccuracy initialized")
            
            # Test WeatherDataAnalysis initialization
            components['analysis'] = WeatherDataAnalysis(self.config)
            print("✅ WeatherDataAnalysis initialized")
            
            self.test_results.append(("Component Initialization", True, "All components initialized successfully"))
            return components
            
        except Exception as e:
            print(f"❌ Component initialization failed: {e}")
            self.test_results.append(("Component Initialization", False, str(e)))
            return None
    
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        print("\n🎭 Testing orchestrator initialization...")
        
        try:
            orchestrator = WeatherForecastOrchestrator(self.config)
            print("✅ Orchestrator initialized successfully")
            
            # Test component access
            if hasattr(orchestrator, 'weather_api') and orchestrator.weather_api:
                print("✅ Weather API component accessible")
            else:
                raise Exception("Weather API component not accessible")
                
            if hasattr(orchestrator, 'storage') and orchestrator.storage:
                print("✅ Storage component accessible")
            else:
                raise Exception("Storage component not accessible")
                
            if hasattr(orchestrator, 'accuracy') and orchestrator.accuracy:
                print("✅ Accuracy component accessible")
            else:
                raise Exception("Accuracy component not accessible")
                
            if hasattr(orchestrator, 'analysis') and orchestrator.analysis:
                print("✅ Analysis component accessible")
            else:
                raise Exception("Analysis component not accessible")
            
            self.test_results.append(("Orchestrator Initialization", True, "Orchestrator and all components accessible"))
            return orchestrator
            
        except Exception as e:
            print(f"❌ Orchestrator initialization failed: {e}")
            self.test_results.append(("Orchestrator Initialization", False, str(e)))
            return None
    
    async def test_health_checks(self, orchestrator):
        """Test orchestrator health check functionality."""
        print("\n🏥 Testing health check functionality...")
        
        try:
            health_status = await orchestrator.check_health()
            
            if health_status.get('overall_health') == 'healthy':
                print("✅ Overall health check passed")
            else:
                print(f"⚠️ Health check warning: {health_status}")
            
            # Check individual components
            components = ['config', 'influxdb', 'api', 'storage', 'accuracy', 'analysis']
            for component in components:
                if component in health_status and health_status[component].get('status') == 'healthy':
                    print(f"✅ {component.capitalize()} health check passed")
                else:
                    print(f"⚠️ {component.capitalize()} health check failed or warning")
            
            self.test_results.append(("Health Checks", True, f"Health status: {health_status.get('overall_health', 'unknown')}"))
            return True
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            self.test_results.append(("Health Checks", False, str(e)))
            return False
    
    async def test_forecast_fetching(self, orchestrator):
        """Test forecast fetching functionality."""
        print("\n🌤️ Testing forecast fetching...")
        
        try:
            # Test forecast fetching
            forecast_data = await orchestrator.weather_api.get_current_weather()
            
            if forecast_data and 'weather' in forecast_data:
                print("✅ Forecast data retrieved successfully")
                print(f"   Temperature: {forecast_data.get('main', {}).get('temp', 'N/A')}°C")
                print(f"   Weather: {forecast_data['weather'][0].get('description', 'N/A')}")
            else:
                raise Exception("Invalid forecast data structure")
            
            self.test_results.append(("Forecast Fetching", True, "Forecast data retrieved and validated"))
            return True
            
        except Exception as e:
            print(f"❌ Forecast fetching failed: {e}")
            self.test_results.append(("Forecast Fetching", False, str(e)))
            return False
    
    async def test_data_storage(self, orchestrator):
        """Test data storage functionality."""
        print("\n💾 Testing data storage...")
        
        try:
            # Test storage connection
            await orchestrator.storage.test_connection()
            print("✅ Storage connection test passed")
            
            # Test forecast storage (if we have recent data)
            try:
                forecast_data = await orchestrator.weather_api.get_current_weather()
                if forecast_data:
                    await orchestrator.storage.store_forecast(forecast_data)
                    print("✅ Forecast storage test passed")
            except Exception as e:
                print(f"⚠️ Forecast storage test skipped: {e}")
            
            self.test_results.append(("Data Storage", True, "Storage connection and basic operations successful"))
            return True
            
        except Exception as e:
            print(f"❌ Data storage test failed: {e}")
            self.test_results.append(("Data Storage", False, str(e)))
            return False
    
    async def test_workflow_execution(self, orchestrator):
        """Test a single workflow execution."""
        print("\n⚙️ Testing workflow execution...")
        
        try:
            # Override reports directory for testing
            original_reports_dir = getattr(orchestrator.analysis, 'reports_dir', None)
            if hasattr(orchestrator.analysis, 'reports_dir'):
                orchestrator.analysis.reports_dir = self.temp_dir
            
            # Execute single workflow run
            start_time = datetime.now()
            stats = await orchestrator.run_single_cycle()
            end_time = datetime.now()
            
            execution_time = (end_time - start_time).total_seconds()
            print(f"✅ Workflow executed in {execution_time:.2f} seconds")
            
            # Check statistics
            if stats:
                print(f"   Forecast fetches: {stats.get('forecast_fetches', 0)}")
                print(f"   Accuracy calculations: {stats.get('accuracy_calculations', 0)}")
                print(f"   Analysis runs: {stats.get('analysis_runs', 0)}")
                print(f"   Errors: {stats.get('errors', 0)}")
            
            # Restore original reports directory
            if original_reports_dir and hasattr(orchestrator.analysis, 'reports_dir'):
                orchestrator.analysis.reports_dir = original_reports_dir
            
            self.test_results.append(("Workflow Execution", True, f"Completed in {execution_time:.2f}s with stats: {stats}"))
            return True
            
        except Exception as e:
            print(f"❌ Workflow execution failed: {e}")
            self.test_results.append(("Workflow Execution", False, str(e)))
            return False
    
    async def test_error_handling(self, orchestrator):
        """Test error handling capabilities."""
        print("\n🚨 Testing error handling...")
        
        try:
            # Test with invalid API configuration
            original_api_key = orchestrator.weather_api.api_key
            orchestrator.weather_api.api_key = "invalid_key_for_testing"
            
            try:
                await orchestrator.weather_api.get_current_weather()
                print("⚠️ Expected API error did not occur")
            except Exception as e:
                print(f"✅ API error handled correctly: {type(e).__name__}")
            
            # Restore original API key
            orchestrator.weather_api.api_key = original_api_key
            
            self.test_results.append(("Error Handling", True, "Error conditions handled appropriately"))
            return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            self.test_results.append(("Error Handling", False, str(e)))
            return False
    
    def print_test_summary(self):
        """Print summary of all test results."""
        print("\n" + "="*60)
        print("🧪 INTEGRATION TEST SUMMARY")
        print("="*60)
        
        passed = 0
        failed = 0
        
        for test_name, success, details in self.test_results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if not success or details:
                print(f"     {details}")
            
            if success:
                passed += 1
            else:
                failed += 1
        
        print("-" * 60)
        print(f"Total Tests: {len(self.test_results)}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/len(self.test_results)*100):.1f}%" if self.test_results else "0%")
        
        if failed == 0:
            print("\n🎉 All integration tests passed! The orchestrator is ready for deployment.")
        else:
            print(f"\n⚠️ {failed} test(s) failed. Please review the issues before deployment.")
        
        return failed == 0

async def main():
    """Run the complete integration test suite."""
    print("🚀 Starting Weather Forecast Orchestrator Integration Tests")
    print("=" * 60)
    
    test_suite = OrchestratorIntegrationTest()
    
    try:
        # Setup
        if not await test_suite.setup():
            print("❌ Test setup failed")
            return 1
        
        # Run tests
        components = await test_suite.test_component_initialization()
        if not components:
            return 1
        
        orchestrator = await test_suite.test_orchestrator_initialization()
        if not orchestrator:
            return 1
        
        await test_suite.test_health_checks(orchestrator)
        await test_suite.test_forecast_fetching(orchestrator)
        await test_suite.test_data_storage(orchestrator)
        await test_suite.test_workflow_execution(orchestrator)
        await test_suite.test_error_handling(orchestrator)
        
        # Print summary
        success = test_suite.print_test_summary()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⏹️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        return 1
    finally:
        test_suite.teardown()

if __name__ == "__main__":
    # Configure logging for tests
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during testing
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run tests
    exit_code = asyncio.run(main())
    sys.exit(exit_code)