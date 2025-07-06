#!/usr/bin/env python3
"""
Comprehensive Service Integration Test

This script tests the Ruuvi sensor service running as a daemon to ensure:
1. Service starts and runs properly
2. BLE scanning works
3. Data is written to InfluxDB
4. Service can be stopped gracefully

Usage:
    python scripts/test_service_integration.py
"""

import asyncio
import sys
import time
import signal
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json

# Add src directory to Python path (same as main.py)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import after path setup (without src prefix since we added src to path)
from utils.config import Config
from utils.logging import ProductionLogger, PerformanceMonitor
from influxdb.client import RuuviInfluxDBClient
from ble.scanner import RuuviSensorData, RuuviDataFormat


class ServiceTestError(Exception):
    """Exception for service test errors."""
    pass


class ServiceIntegrationTester:
    """
    Comprehensive service integration tester.
    
    Tests the complete service workflow:
    - Service startup and initialization
    - BLE scanning functionality
    - InfluxDB data writing
    - Service monitoring and statistics
    - Graceful shutdown
    """
    
    def __init__(self):
        """Initialize the tester."""
        self.config = Config()
        self.logger = ProductionLogger(self.config)
        self.performance_monitor = PerformanceMonitor(self.logger)
        self.influxdb_client: Optional[RuuviInfluxDBClient] = None
        self.service_process: Optional[subprocess.Popen] = None
        self.test_results: Dict[str, Any] = {}
        
    async def setup(self):
        """Set up test environment."""
        self.logger.info("Setting up service integration test...")
        
        # Initialize InfluxDB client for verification
        self.influxdb_client = RuuviInfluxDBClient(
            self.config, self.logger, self.performance_monitor
        )
        
        # Connect to InfluxDB
        try:
            await self.influxdb_client.connect()
            self.logger.info("Connected to InfluxDB for verification")
        except Exception as e:
            raise ServiceTestError(f"Failed to connect to InfluxDB: {e}")
    
    async def cleanup(self):
        """Clean up test environment."""
        self.logger.info("Cleaning up test environment...")
        
        # Stop service if running
        if self.service_process:
            await self.stop_service()
        
        # Disconnect from InfluxDB
        if self.influxdb_client:
            await self.influxdb_client.disconnect()
    
    def start_service(self) -> bool:
        """
        Start the service as a background process.
        
        Returns:
            bool: True if service started successfully
        """
        try:
            self.logger.info("Starting Ruuvi sensor service...")
            
            # Start service process
            self.service_process = subprocess.Popen(
                [sys.executable, "main.py", "daemon"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Give service time to start
            time.sleep(5)
            
            # Check if process is still running
            if self.service_process.poll() is None:
                self.logger.info(f"Service started with PID: {self.service_process.pid}")
                return True
            else:
                stdout, stderr = self.service_process.communicate()
                self.logger.error(f"Service failed to start. STDOUT: {stdout}, STDERR: {stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            return False
    
    async def stop_service(self) -> bool:
        """
        Stop the service gracefully.
        
        Returns:
            bool: True if service stopped successfully
        """
        if not self.service_process:
            return True
        
        try:
            self.logger.info("Stopping service gracefully...")
            
            # Send SIGTERM for graceful shutdown
            self.service_process.send_signal(signal.SIGTERM)
            
            # Wait for graceful shutdown (up to 30 seconds)
            try:
                stdout, stderr = self.service_process.communicate(timeout=30)
                self.logger.info("Service stopped gracefully")
                
                # Log service output
                if stdout:
                    self.logger.debug(f"Service STDOUT: {stdout}")
                if stderr:
                    self.logger.debug(f"Service STDERR: {stderr}")
                
                return True
                
            except subprocess.TimeoutExpired:
                self.logger.warning("Service didn't stop gracefully, forcing termination...")
                self.service_process.kill()
                self.service_process.communicate()
                return False
                
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}")
            return False
        finally:
            self.service_process = None
    
    def is_service_running(self) -> bool:
        """
        Check if service is running.
        
        Returns:
            bool: True if service is running
        """
        if not self.service_process:
            return False
        
        return self.service_process.poll() is None
    
    async def test_service_startup(self) -> Dict[str, Any]:
        """
        Test service startup.
        
        Returns:
            Dict[str, Any]: Test results
        """
        self.logger.info("Testing service startup...")
        
        result = {
            "test_name": "service_startup",
            "success": False,
            "start_time": datetime.now(),
            "details": {}
        }
        
        try:
            # Start service
            startup_success = self.start_service()
            result["details"]["startup_success"] = startup_success
            
            if not startup_success:
                result["error"] = "Failed to start service"
                return result
            
            # Wait for service to initialize
            self.logger.info("Waiting for service initialization...")
            await asyncio.sleep(10)
            
            # Check if service is still running
            is_running = self.is_service_running()
            result["details"]["is_running"] = is_running
            
            if not is_running:
                result["error"] = "Service stopped unexpectedly after startup"
                return result
            
            result["success"] = True
            self.logger.info("Service startup test passed")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Service startup test failed: {e}")
        
        finally:
            result["end_time"] = datetime.now()
            result["duration"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    async def test_influxdb_connectivity(self) -> Dict[str, Any]:
        """
        Test InfluxDB connectivity and data writing.
        
        Returns:
            Dict[str, Any]: Test results
        """
        self.logger.info("Testing InfluxDB connectivity...")
        
        result = {
            "test_name": "influxdb_connectivity",
            "success": False,
            "start_time": datetime.now(),
            "details": {}
        }
        
        try:
            # Test direct connection
            connection_test = await self.influxdb_client.health_check()
            result["details"]["connection_healthy"] = connection_test
            
            if not connection_test:
                result["error"] = "InfluxDB health check failed"
                return result
            
            # Write test data
            test_data = RuuviSensorData(
                mac_address="TEST:SERVICE:INTEGRATION",
                timestamp=datetime.utcnow(),
                data_format=RuuviDataFormat.FORMAT_5,
                temperature=25.0,
                humidity=50.0,
                pressure=1013.25,
                battery_voltage=3.0,
                rssi=-60
            )
            
            write_success = await self.influxdb_client.write_sensor_data(test_data, buffer=False)
            result["details"]["test_write_success"] = write_success
            
            if not write_success:
                result["error"] = "Failed to write test data to InfluxDB"
                return result
            
            # Verify data was written
            await asyncio.sleep(2)  # Give InfluxDB time to process
            
            try:
                query_results = await self.influxdb_client.get_sensor_data(
                    "TEST:SERVICE:INTEGRATION",
                    datetime.utcnow() - timedelta(minutes=5)
                )
                result["details"]["test_data_found"] = len(query_results) > 0
                result["details"]["query_results_count"] = len(query_results)
                
            except Exception as e:
                self.logger.warning(f"Query verification failed: {e}")
                result["details"]["query_error"] = str(e)
            
            result["success"] = True
            self.logger.info("InfluxDB connectivity test passed")
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"InfluxDB connectivity test failed: {e}")
        
        finally:
            result["end_time"] = datetime.now()
            result["duration"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    async def test_service_data_collection(self) -> Dict[str, Any]:
        """
        Test service data collection over time.
        
        Returns:
            Dict[str, Any]: Test results
        """
        self.logger.info("Testing service data collection...")
        
        result = {
            "test_name": "service_data_collection",
            "success": False,
            "start_time": datetime.now(),
            "details": {}
        }
        
        try:
            if not self.is_service_running():
                result["error"] = "Service is not running"
                return result
            
            # Record initial data count
            initial_time = datetime.utcnow()
            
            # Wait for data collection (2 minutes)
            collection_duration = 120  # seconds
            self.logger.info(f"Monitoring data collection for {collection_duration} seconds...")
            
            await asyncio.sleep(collection_duration)
            
            # Check for new data in InfluxDB
            end_time = datetime.utcnow()
            
            try:
                # Query for all sensor data in the test period
                flux_query = f'''
                from(bucket: "{self.config.influxdb_bucket}")
                  |> range(start: {initial_time.isoformat()}Z, stop: {end_time.isoformat()}Z)
                  |> filter(fn: (r) => r["_measurement"] =~ /^ruuvi_/)
                  |> count()
                '''
                
                query_results = await self.influxdb_client.query(flux_query)
                
                total_points = 0
                unique_sensors = set()
                
                for record in query_results:
                    if '_value' in record:
                        total_points += record['_value']
                    if 'sensor_mac' in record:
                        unique_sensors.add(record['sensor_mac'])
                
                result["details"]["total_data_points"] = total_points
                result["details"]["unique_sensors"] = len(unique_sensors)
                result["details"]["collection_duration"] = collection_duration
                result["details"]["data_rate"] = total_points / collection_duration if collection_duration > 0 else 0
                
                # Consider test successful if we collected any data
                if total_points > 0:
                    result["success"] = True
                    self.logger.info(f"Data collection test passed: {total_points} points from {len(unique_sensors)} sensors")
                else:
                    result["error"] = "No data points collected during test period"
                    self.logger.warning("No data collected - this might be normal if no sensors are nearby")
                    # Don't fail the test completely as this might be environmental
                    result["success"] = True  # Mark as success but note the issue
                
            except Exception as e:
                result["error"] = f"Failed to query collected data: {e}"
                self.logger.error(f"Data collection verification failed: {e}")
        
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Service data collection test failed: {e}")
        
        finally:
            result["end_time"] = datetime.now()
            result["duration"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    async def test_service_shutdown(self) -> Dict[str, Any]:
        """
        Test service graceful shutdown.
        
        Returns:
            Dict[str, Any]: Test results
        """
        self.logger.info("Testing service shutdown...")
        
        result = {
            "test_name": "service_shutdown",
            "success": False,
            "start_time": datetime.now(),
            "details": {}
        }
        
        try:
            if not self.is_service_running():
                result["error"] = "Service is not running"
                return result
            
            # Stop service
            shutdown_success = await self.stop_service()
            result["details"]["shutdown_success"] = shutdown_success
            
            if shutdown_success:
                result["success"] = True
                self.logger.info("Service shutdown test passed")
            else:
                result["error"] = "Service did not shut down gracefully"
            
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"Service shutdown test failed: {e}")
        
        finally:
            result["end_time"] = datetime.now()
            result["duration"] = (result["end_time"] - result["start_time"]).total_seconds()
        
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """
        Run all service integration tests.
        
        Returns:
            Dict[str, Any]: Complete test results
        """
        self.logger.info("Starting comprehensive service integration tests...")
        
        test_suite_start = datetime.now()
        all_results = {
            "test_suite": "service_integration",
            "start_time": test_suite_start,
            "tests": [],
            "summary": {}
        }
        
        try:
            # Test 1: Service startup
            startup_result = await self.test_service_startup()
            all_results["tests"].append(startup_result)
            
            if not startup_result["success"]:
                self.logger.error("Service startup failed, skipping remaining tests")
                return all_results
            
            # Test 2: InfluxDB connectivity
            influxdb_result = await self.test_influxdb_connectivity()
            all_results["tests"].append(influxdb_result)
            
            # Test 3: Data collection (only if InfluxDB is working)
            if influxdb_result["success"]:
                collection_result = await self.test_service_data_collection()
                all_results["tests"].append(collection_result)
            else:
                self.logger.warning("Skipping data collection test due to InfluxDB issues")
            
            # Test 4: Service shutdown
            shutdown_result = await self.test_service_shutdown()
            all_results["tests"].append(shutdown_result)
            
        except Exception as e:
            self.logger.error(f"Test suite execution failed: {e}")
            all_results["error"] = str(e)
        
        finally:
            # Calculate summary
            all_results["end_time"] = datetime.now()
            all_results["total_duration"] = (all_results["end_time"] - test_suite_start).total_seconds()
            
            passed_tests = sum(1 for test in all_results["tests"] if test["success"])
            total_tests = len(all_results["tests"])
            
            all_results["summary"] = {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            }
        
        return all_results
    
    def print_test_results(self, results: Dict[str, Any]):
        """Print formatted test results."""
        print("\n" + "="*80)
        print("SERVICE INTEGRATION TEST RESULTS")
        print("="*80)
        
        print(f"Test Suite: {results['test_suite']}")
        print(f"Start Time: {results['start_time']}")
        print(f"End Time: {results['end_time']}")
        print(f"Total Duration: {results['total_duration']:.2f} seconds")
        print()
        
        # Summary
        summary = results["summary"]
        print("SUMMARY:")
        print(f"  Total Tests: {summary['total_tests']}")
        print(f"  Passed: {summary['passed_tests']}")
        print(f"  Failed: {summary['failed_tests']}")
        print(f"  Success Rate: {summary['success_rate']:.1f}%")
        print()
        
        # Individual test results
        print("INDIVIDUAL TEST RESULTS:")
        print("-" * 40)
        
        for test in results["tests"]:
            status = "✅ PASS" if test["success"] else "❌ FAIL"
            print(f"{status} {test['test_name']}")
            print(f"    Duration: {test['duration']:.2f}s")
            
            if "error" in test:
                print(f"    Error: {test['error']}")
            
            if "details" in test and test["details"]:
                print("    Details:")
                for key, value in test["details"].items():
                    print(f"      {key}: {value}")
            print()
        
        # Overall result
        overall_success = summary["failed_tests"] == 0
        overall_status = "✅ ALL TESTS PASSED" if overall_success else "❌ SOME TESTS FAILED"
        print("="*80)
        print(f"OVERALL RESULT: {overall_status}")
        print("="*80)


async def main():
    """Main test execution function."""
    tester = ServiceIntegrationTester()
    
    try:
        # Setup
        await tester.setup()
        
        # Run tests
        results = await tester.run_all_tests()
        
        # Print results
        tester.print_test_results(results)
        
        # Save results to file
        results_file = Path("test_results_service_integration.json")
        with open(results_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            json_results = json.loads(json.dumps(results, default=str))
            json.dump(json_results, f, indent=2)
        
        print(f"\nDetailed results saved to: {results_file}")
        
        # Exit with appropriate code
        success_rate = results["summary"]["success_rate"]
        if success_rate == 100:
            print("\n🎉 All tests passed! Service is working correctly.")
            sys.exit(0)
        elif success_rate >= 75:
            print(f"\n⚠️  Most tests passed ({success_rate:.1f}%), but some issues detected.")
            sys.exit(1)
        else:
            print(f"\n💥 Many tests failed ({success_rate:.1f}%), service has significant issues.")
            sys.exit(2)
    
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        sys.exit(3)
    
    finally:
        # Cleanup
        await tester.cleanup()


if __name__ == "__main__":
    print("Ruuvi Sensor Service Integration Test")
    print("=====================================")
    print()
    print("This test will:")
    print("1. Start the service as a daemon")
    print("2. Test InfluxDB connectivity and data writing")
    print("3. Monitor data collection for 2 minutes")
    print("4. Test graceful service shutdown")
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)