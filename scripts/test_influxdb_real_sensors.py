#!/usr/bin/env python3
"""
Test script to verify InfluxDB integration with real Ruuvi sensor data.
This script will:
1. Scan for real Ruuvi sensors
2. Write the sensor data to InfluxDB
3. Retrieve the data back from InfluxDB
4. Verify data integrity
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.ble.scanner import RuuviBLEScanner, RuuviSensorData
from src.influxdb.client import RuuviInfluxDBClient
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor


class InfluxDBRealSensorTest:
    """Test InfluxDB operations with real sensor data."""
    
    def __init__(self):
        """Initialize test components."""
        self.config = Config()
        self.logger = ProductionLogger(self.config)
        self.performance_monitor = PerformanceMonitor(self.logger)
        
        # Initialize components
        self.scanner = RuuviBLEScanner(self.config, self.logger, self.performance_monitor)
        self.influx_client = RuuviInfluxDBClient(self.config, self.logger, self.performance_monitor)
        
        # Test data storage
        self.collected_data: List[RuuviSensorData] = []
        
        print("=" * 60)
        print("InfluxDB Real Sensor Data Test")
        print("=" * 60)
        print(f"InfluxDB Host: {self.config.influxdb_host}:{self.config.influxdb_port}")
        print(f"InfluxDB Bucket: {self.config.influxdb_bucket}")
        print(f"InfluxDB Org: {self.config.influxdb_org}")
        print("=" * 60)
    
    def sensor_data_callback(self, sensor_data: RuuviSensorData):
        """Callback for receiving sensor data during scan."""
        self.collected_data.append(sensor_data)
        print(f"📡 Sensor discovered: {sensor_data.mac_address}")
        print(f"   Temperature: {sensor_data.temperature}°C")
        print(f"   Humidity: {sensor_data.humidity}%")
        print(f"   Pressure: {sensor_data.pressure} hPa")
        print(f"   Battery: {sensor_data.battery_voltage}V")
        print(f"   RSSI: {sensor_data.rssi}dBm")
        print(f"   Format: {sensor_data.data_format.value}")
        print()
    
    async def test_influxdb_connection(self) -> bool:
        """Test InfluxDB connection."""
        print("🔗 Testing InfluxDB connection...")
        
        try:
            connected = await self.influx_client.connect()
            if connected:
                print("✅ InfluxDB connection successful")
                
                # Test health check
                health = await self.influx_client.health_check()
                if health:
                    print("✅ InfluxDB health check passed")
                else:
                    print("❌ InfluxDB health check failed")
                    return False
                
                return True
            else:
                print("❌ Failed to connect to InfluxDB")
                return False
                
        except Exception as e:
            print(f"❌ InfluxDB connection error: {e}")
            return False
    
    async def scan_for_sensors(self, duration: float = 30.0) -> List[RuuviSensorData]:
        """Scan for real Ruuvi sensors."""
        print(f"🔍 Scanning for Ruuvi sensors for {duration} seconds...")
        print("   Make sure your Ruuvi sensors are nearby and active!")
        print()
        
        # Clear previous data
        self.collected_data.clear()
        
        # Add callback to collect data
        self.scanner.add_callback(self.sensor_data_callback)
        
        try:
            # Perform scan
            discovered_devices = await self.scanner.scan_once(duration)
            
            print(f"📊 Scan completed. Found {len(discovered_devices)} unique sensors")
            print(f"📊 Collected {len(self.collected_data)} data points")
            
            if not self.collected_data:
                print("⚠️  No Ruuvi sensors found. Please check:")
                print("   - Sensors are powered on and nearby")
                print("   - Bluetooth is enabled on this system")
                print("   - No other applications are using Bluetooth")
                return []
            
            return self.collected_data.copy()
            
        except Exception as e:
            print(f"❌ Sensor scan failed: {e}")
            return []
        finally:
            self.scanner.remove_callback(self.sensor_data_callback)
    
    async def write_sensor_data_to_influxdb(self, sensor_data_list: List[RuuviSensorData]) -> bool:
        """Write sensor data to InfluxDB."""
        if not sensor_data_list:
            print("❌ No sensor data to write")
            return False
        
        print(f"💾 Writing {len(sensor_data_list)} sensor readings to InfluxDB...")
        
        try:
            # Write each sensor data point
            successful_writes = 0
            for i, sensor_data in enumerate(sensor_data_list, 1):
                success = await self.influx_client.write_sensor_data(sensor_data, buffer=False)
                if success:
                    successful_writes += 1
                    print(f"   ✅ Written {i}/{len(sensor_data_list)}: {sensor_data.mac_address}")
                else:
                    print(f"   ❌ Failed {i}/{len(sensor_data_list)}: {sensor_data.mac_address}")
            
            print(f"📊 Successfully wrote {successful_writes}/{len(sensor_data_list)} sensor readings")
            
            # Get and display statistics
            stats = self.influx_client.get_statistics()
            print(f"📊 InfluxDB Statistics:")
            print(f"   Points written: {stats['points_written']}")
            print(f"   Batches sent: {stats['batches_sent']}")
            print(f"   Write errors: {stats['points_failed']}")
            print(f"   Average write time: {stats['average_write_time']:.3f}s")
            
            return successful_writes > 0
            
        except Exception as e:
            print(f"❌ Error writing to InfluxDB: {e}")
            return False
    
    async def verify_data_retrieval(self, sensor_data_list: List[RuuviSensorData]) -> bool:
        """Retrieve and verify data from InfluxDB."""
        if not sensor_data_list:
            print("❌ No sensor data to verify")
            return False
        
        print("🔍 Retrieving data from InfluxDB to verify writes...")
        
        # Wait a moment for data to be available
        print("   Waiting 3 seconds for data to be indexed...")
        await asyncio.sleep(3)
        
        verification_results = []
        
        # Get unique MAC addresses
        unique_sensors = {}
        for sensor_data in sensor_data_list:
            if sensor_data.mac_address not in unique_sensors:
                unique_sensors[sensor_data.mac_address] = sensor_data
        
        print(f"🔍 Verifying data for {len(unique_sensors)} unique sensors...")
        
        for mac_address, sample_data in unique_sensors.items():
            try:
                print(f"   Checking sensor: {mac_address}")
                
                # Define time range around the sensor data
                start_time = sample_data.timestamp - timedelta(minutes=2)
                end_time = sample_data.timestamp + timedelta(minutes=2)
                
                # Query environmental data
                env_results = await self.influx_client.get_sensor_data(
                    mac_address=mac_address,
                    start_time=start_time,
                    end_time=end_time,
                    measurement="ruuvi_environmental"
                )
                
                if env_results:
                    print(f"   ✅ Found {len(env_results)} environmental data points")
                    
                    # Verify specific fields
                    fields_found = set()
                    for result in env_results:
                        field_name = result.get("_field")
                        if field_name:
                            fields_found.add(field_name)
                            value = result.get("_value")
                            print(f"      {field_name}: {value}")
                    
                    expected_fields = {"temperature", "humidity", "pressure"}
                    missing_fields = expected_fields - fields_found
                    if missing_fields:
                        print(f"   ⚠️  Missing fields: {missing_fields}")
                    else:
                        print(f"   ✅ All environmental fields present")
                    
                    verification_results.append(True)
                else:
                    print(f"   ❌ No environmental data found for {mac_address}")
                    verification_results.append(False)
                
                # Query motion data if available
                motion_results = await self.influx_client.get_sensor_data(
                    mac_address=mac_address,
                    start_time=start_time,
                    end_time=end_time,
                    measurement="ruuvi_motion"
                )
                
                if motion_results:
                    print(f"   ✅ Found {len(motion_results)} motion data points")
                
                # Query power data if available
                power_results = await self.influx_client.get_sensor_data(
                    mac_address=mac_address,
                    start_time=start_time,
                    end_time=end_time,
                    measurement="ruuvi_power"
                )
                
                if power_results:
                    print(f"   ✅ Found {len(power_results)} power data points")
                
                print()
                
            except Exception as e:
                print(f"   ❌ Error verifying data for {mac_address}: {e}")
                verification_results.append(False)
        
        successful_verifications = sum(verification_results)
        total_sensors = len(unique_sensors)
        
        print(f"📊 Verification Results: {successful_verifications}/{total_sensors} sensors verified")
        
        return successful_verifications > 0
    
    async def run_complete_test(self) -> bool:
        """Run the complete test workflow."""
        print("🚀 Starting complete InfluxDB integration test with real sensors")
        print()
        
        try:
            # Step 1: Test InfluxDB connection
            if not await self.test_influxdb_connection():
                return False
            
            print()
            
            # Step 2: Scan for real sensors
            sensor_data = await self.scan_for_sensors(duration=30.0)
            if not sensor_data:
                print("❌ Test failed: No sensor data collected")
                return False
            
            print()
            
            # Step 3: Write data to InfluxDB
            if not await self.write_sensor_data_to_influxdb(sensor_data):
                print("❌ Test failed: Could not write data to InfluxDB")
                return False
            
            print()
            
            # Step 4: Verify data retrieval
            if not await self.verify_data_retrieval(sensor_data):
                print("❌ Test failed: Could not retrieve/verify data from InfluxDB")
                return False
            
            print()
            print("🎉 Complete test PASSED!")
            print("✅ Successfully scanned real sensors")
            print("✅ Successfully wrote data to InfluxDB")
            print("✅ Successfully retrieved and verified data")
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            return False
        
        finally:
            # Cleanup
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources."""
        print("🧹 Cleaning up resources...")
        
        try:
            await self.scanner.cleanup()
            await self.influx_client.disconnect()
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")


async def main():
    """Main test function."""
    test = InfluxDBRealSensorTest()
    
    try:
        success = await test.run_complete_test()
        
        if success:
            print("\n" + "=" * 60)
            print("🎉 ALL TESTS PASSED!")
            print("InfluxDB integration with real sensor data is working correctly.")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ TESTS FAILED!")
            print("Please check the error messages above and fix any issues.")
            print("=" * 60)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        await test.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        await test.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    print("Starting InfluxDB Real Sensor Integration Test...")
    print("Make sure your Ruuvi sensors are nearby and active!")
    print()
    
    # Run the test
    asyncio.run(main())