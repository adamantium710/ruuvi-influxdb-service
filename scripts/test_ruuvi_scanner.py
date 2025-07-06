#!/usr/bin/env python3
"""
Ruuvi Sensor Scanner Test
Tests the actual Ruuvi BLE scanner implementation after Bluetooth fixes
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.ble.scanner import RuuviBLEScanner

async def test_ruuvi_scanner():
    """Test the Ruuvi BLE scanner implementation."""
    print("🔍 Testing Ruuvi BLE Scanner Implementation")
    print("=" * 50)
    
    try:
        # Initialize configuration
        config = Config()
        logger = ProductionLogger(config)
        performance_monitor = PerformanceMonitor(logger)
        
        print("✅ Configuration loaded successfully")
        print(f"   BLE Adapter: {config.ble_adapter}")
        print(f"   Scan Duration: {config.ble_scan_duration}s")
        print(f"   Scan Interval: {config.ble_scan_interval}s")
        print()
        
        # Initialize scanner
        scanner = RuuviBLEScanner(config, logger, performance_monitor)
        print("✅ RuuviBLEScanner initialized")
        
        # Add callback to display discovered sensors
        def sensor_callback(sensor_data):
            print(f"📡 Ruuvi Sensor Discovered:")
            print(f"   MAC: {sensor_data.mac_address}")
            print(f"   Format: {sensor_data.data_format.value}")
            print(f"   Temperature: {sensor_data.temperature}°C")
            print(f"   Humidity: {sensor_data.humidity}%")
            print(f"   Pressure: {sensor_data.pressure} hPa")
            print(f"   Battery: {sensor_data.battery_voltage}V")
            print(f"   RSSI: {sensor_data.rssi}dBm")
            print()
        
        scanner.add_callback(sensor_callback)
        print("✅ Sensor callback registered")
        print()
        
        # Perform scan
        print(f"🔄 Starting {config.ble_scan_duration}s BLE scan for Ruuvi sensors...")
        devices = await scanner.scan_once()
        
        print(f"✅ Scan completed successfully!")
        print(f"   Found {len(devices)} Ruuvi sensors")
        
        if devices:
            print("\n📊 Discovered Ruuvi Sensors:")
            for mac, sensor_data in devices.items():
                print(f"   {mac}: Temp={sensor_data.temperature}°C, "
                      f"Humidity={sensor_data.humidity}%, "
                      f"RSSI={sensor_data.rssi}dBm")
        else:
            print("\n⚠️  No Ruuvi sensors found")
            print("   This could mean:")
            print("   - No Ruuvi sensors are nearby")
            print("   - Sensors are not advertising")
            print("   - Bluetooth range issues")
            print("   - Sensors need battery replacement")
        
        # Display statistics
        stats = scanner.get_statistics()
        print(f"\n📈 Scanner Statistics:")
        print(f"   Scans completed: {stats['scan_count']}")
        print(f"   Devices discovered: {stats['device_count']}")
        print(f"   Errors: {stats['error_count']}")
        
        # Cleanup
        await scanner.cleanup()
        print("\n✅ Scanner cleanup completed")
        
    except Exception as e:
        print(f"❌ Scanner test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_basic_ble_scan():
    """Test basic BLE scanning without Ruuvi-specific parsing."""
    print("\n🔍 Testing Basic BLE Scanning")
    print("=" * 30)
    
    try:
        import bleak
        
        print("Performing 5-second general BLE scan...")
        devices = await bleak.BleakScanner.discover(timeout=5.0)
        
        print(f"✅ Found {len(devices)} BLE devices total")
        
        if devices:
            print("\n📱 All BLE Devices:")
            for device in devices[:10]:  # Show first 10
                print(f"   {device.address} - {device.name or 'Unknown'} (RSSI: {device.rssi}dBm)")
            
            if len(devices) > 10:
                print(f"   ... and {len(devices) - 10} more devices")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic BLE scan failed: {e}")
        return False

def main():
    """Main test function."""
    print("🧪 Ruuvi Sensor Scanner Test Suite")
    print("=" * 60)
    print()
    
    # Test basic BLE functionality first
    basic_success = asyncio.run(test_basic_ble_scan())
    
    if not basic_success:
        print("\n❌ Basic BLE scanning failed. Check Bluetooth configuration.")
        print("   Run: python scripts/bluetooth_diagnostic.py")
        return 1
    
    # Test Ruuvi-specific scanner
    ruuvi_success = asyncio.run(test_ruuvi_scanner())
    
    if ruuvi_success:
        print("\n🎉 All tests passed! Ruuvi sensor scanning is working.")
        print("\nNext steps:")
        print("1. Run: python main.py discover")
        print("2. Run: python main.py monitor")
        return 0
    else:
        print("\n❌ Ruuvi scanner test failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())