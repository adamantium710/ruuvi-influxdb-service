"""
Mock BLE scanner for testing Ruuvi sensor detection without hardware.
Provides realistic simulation of BLE scanning behavior and device discovery.
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from tests.fixtures.sensor_data import SensorDataFixtures


@dataclass
class MockRuuviDevice:
    """Mock Ruuvi device for testing."""
    mac_address: str
    name: str
    data_format: int
    base_temperature: float = 20.0
    base_humidity: float = 50.0
    base_pressure: float = 1013.25
    battery_voltage: float = 3.0
    rssi_range: tuple = (-80, -40)
    movement_probability: float = 0.1
    
    def __post_init__(self):
        """Initialize device state."""
        self.movement_counter = 0
        self.measurement_sequence = 0
        self.last_update = datetime.utcnow()
    
    def generate_advertisement_data(self) -> bytes:
        """Generate realistic advertisement data for this device."""
        # Add some realistic variation to sensor readings
        temp_variation = random.uniform(-2.0, 2.0)
        humidity_variation = random.uniform(-5.0, 5.0)
        pressure_variation = random.uniform(-10.0, 10.0)
        
        temperature = self.base_temperature + temp_variation
        humidity = max(0, min(100, self.base_humidity + humidity_variation))
        pressure = self.base_pressure + pressure_variation
        
        # Simulate movement
        if random.random() < self.movement_probability:
            self.movement_counter = (self.movement_counter + 1) % 256
        
        self.measurement_sequence = (self.measurement_sequence + 1) % 65536
        
        if self.data_format == 3:
            return self._generate_format3_data(temperature, humidity, pressure)
        elif self.data_format == 5:
            return self._generate_format5_data(temperature, humidity, pressure)
        else:
            raise ValueError(f"Unsupported data format: {self.data_format}")
    
    def _generate_format3_data(self, temperature: float, humidity: float, pressure: float) -> bytes:
        """Generate Format 3 manufacturer data."""
        # Format 3 structure
        humidity_byte = int(humidity * 2)  # 0.5% resolution
        temp_int = int(temperature)
        temp_frac = int((temperature - temp_int) * 100)
        
        pressure_pa = int(pressure * 100 - 50000)  # Convert to Pa and remove offset
        
        # Generate some acceleration data
        acc_x = random.randint(-2000, 2000)  # mg
        acc_y = random.randint(-2000, 2000)
        acc_z = random.randint(800, 1200)  # Usually pointing up
        
        battery_mv = int(self.battery_voltage * 1000)
        
        return bytes([
            3,  # Format
            humidity_byte,
            temp_int & 0xFF,
            temp_frac,
            (pressure_pa >> 8) & 0xFF,
            pressure_pa & 0xFF,
            (acc_x >> 8) & 0xFF,
            acc_x & 0xFF,
            (acc_y >> 8) & 0xFF,
            acc_y & 0xFF,
            (acc_z >> 8) & 0xFF,
            acc_z & 0xFF,
            (battery_mv >> 8) & 0xFF,
            battery_mv & 0xFF
        ])
    
    def _generate_format5_data(self, temperature: float, humidity: float, pressure: float) -> bytes:
        """Generate Format 5 manufacturer data."""
        # Format 5 structure
        temp_raw = int(temperature / 0.005)
        humidity_raw = int(humidity / 0.0025)
        pressure_pa = int(pressure * 100 - 50000)
        
        # Generate acceleration data
        acc_x = random.randint(-2000, 2000)  # mg
        acc_y = random.randint(-2000, 2000)
        acc_z = random.randint(800, 1200)
        
        # Power info: 11 bits battery + 5 bits TX power
        battery_mv = int(self.battery_voltage * 1000)
        battery_raw = battery_mv - 1600
        tx_power_raw = random.randint(0, 20)  # 0-20 range maps to -40 to 0 dBm
        power_info = (battery_raw << 5) | tx_power_raw
        
        # MAC address bytes
        mac_bytes = [int(b, 16) for b in self.mac_address.split(':')]
        
        return bytes([
            5,  # Format
            (temp_raw >> 8) & 0xFF,
            temp_raw & 0xFF,
            (humidity_raw >> 8) & 0xFF,
            humidity_raw & 0xFF,
            (pressure_pa >> 8) & 0xFF,
            pressure_pa & 0xFF,
            (acc_x >> 8) & 0xFF,
            acc_x & 0xFF,
            (acc_y >> 8) & 0xFF,
            acc_y & 0xFF,
            (acc_z >> 8) & 0xFF,
            acc_z & 0xFF,
            (power_info >> 8) & 0xFF,
            power_info & 0xFF,
            self.movement_counter,
            (self.measurement_sequence >> 8) & 0xFF,
            self.measurement_sequence & 0xFF,
        ] + mac_bytes)
    
    def get_rssi(self) -> int:
        """Get simulated RSSI value."""
        return random.randint(self.rssi_range[0], self.rssi_range[1])


class MockBLEDevice:
    """Mock BLE device that mimics bleak's BLEDevice."""
    
    def __init__(self, address: str, name: str = None):
        self.address = address
        self.name = name or f"Ruuvi {address[-4:]}"
    
    def __str__(self):
        return f"{self.address}: {self.name}"
    
    def __repr__(self):
        return f"MockBLEDevice(address='{self.address}', name='{self.name}')"


class MockAdvertisementData:
    """Mock advertisement data that mimics bleak's AdvertisementData."""
    
    def __init__(self, manufacturer_data: Dict[int, bytes], rssi: int, local_name: str = None):
        self.manufacturer_data = manufacturer_data
        self.rssi = rssi
        self.local_name = local_name
        self.service_data = {}
        self.service_uuids = []


class MockBleakScanner:
    """
    Mock BLE scanner that simulates device discovery without requiring hardware.
    Provides realistic behavior for testing scanner functionality.
    """
    
    def __init__(self, detection_callback=None, adapter=None):
        self.detection_callback = detection_callback
        self.adapter = adapter
        self._is_scanning = False
        self._scan_task = None
        
        # Default mock devices
        self.mock_devices = [
            MockRuuviDevice(
                mac_address="AA:BB:CC:DD:EE:01",
                name="Ruuvi 0001",
                data_format=5,
                base_temperature=22.5,
                base_humidity=45.0,
                battery_voltage=3.2
            ),
            MockRuuviDevice(
                mac_address="AA:BB:CC:DD:EE:02", 
                name="Ruuvi 0002",
                data_format=3,
                base_temperature=18.0,
                base_humidity=60.0,
                battery_voltage=2.8
            ),
            MockRuuviDevice(
                mac_address="AA:BB:CC:DD:EE:03",
                name="Ruuvi 0003", 
                data_format=5,
                base_temperature=25.0,
                base_humidity=35.0,
                battery_voltage=3.1
            )
        ]
        
        # Configuration for simulation behavior
        self.discovery_probability = 0.8  # Probability of discovering each device
        self.discovery_delay_range = (0.1, 2.0)  # Random delay between discoveries
        self.scan_failure_probability = 0.0  # Probability of scan failure
    
    def add_mock_device(self, device: MockRuuviDevice):
        """Add a mock device to the scanner."""
        self.mock_devices.append(device)
    
    def remove_mock_device(self, mac_address: str):
        """Remove a mock device by MAC address."""
        self.mock_devices = [d for d in self.mock_devices if d.mac_address != mac_address]
    
    def set_failure_mode(self, failure_probability: float = 0.1):
        """Set the probability of scan failures for testing error handling."""
        self.scan_failure_probability = failure_probability
    
    async def start(self):
        """Start the mock scanner."""
        if self._is_scanning:
            raise RuntimeError("Scanner is already running")
        
        # Simulate potential initialization failure
        if random.random() < self.scan_failure_probability:
            raise Exception("Mock BLE adapter initialization failed")
        
        self._is_scanning = True
        
        # Start the discovery simulation task
        if self.detection_callback:
            self._scan_task = asyncio.create_task(self._simulate_discovery())
    
    async def stop(self):
        """Stop the mock scanner."""
        self._is_scanning = False
        
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
    
    async def _simulate_discovery(self):
        """Simulate device discovery during scanning."""
        try:
            while self._is_scanning:
                for device in self.mock_devices:
                    if not self._is_scanning:
                        break
                    
                    # Randomly decide if this device is discovered this round
                    if random.random() < self.discovery_probability:
                        await self._simulate_device_discovery(device)
                    
                    # Random delay between device discoveries
                    delay = random.uniform(*self.discovery_delay_range)
                    await asyncio.sleep(delay)
                
                # Wait before next discovery round
                await asyncio.sleep(1.0)
                
        except asyncio.CancelledError:
            pass
    
    async def _simulate_device_discovery(self, mock_device: MockRuuviDevice):
        """Simulate discovery of a specific device."""
        if not self.detection_callback:
            return
        
        # Create mock BLE device
        ble_device = MockBLEDevice(
            address=mock_device.mac_address,
            name=mock_device.name
        )
        
        # Generate advertisement data
        manufacturer_data = mock_device.generate_advertisement_data()
        ad_data = MockAdvertisementData(
            manufacturer_data={0x0499: manufacturer_data},  # Ruuvi manufacturer ID
            rssi=mock_device.get_rssi(),
            local_name=mock_device.name
        )
        
        # Call the detection callback
        try:
            self.detection_callback(ble_device, ad_data)
        except Exception as e:
            # Log error but continue scanning
            print(f"Error in detection callback: {e}")


class MockBleakScannerFactory:
    """Factory for creating mock BLE scanners with different configurations."""
    
    @staticmethod
    def create_empty_scanner(detection_callback=None, adapter=None):
        """Create a scanner that finds no devices."""
        scanner = MockBleakScanner(detection_callback, adapter)
        scanner.mock_devices = []
        return scanner
    
    @staticmethod
    def create_failing_scanner(detection_callback=None, adapter=None):
        """Create a scanner that always fails to initialize."""
        scanner = MockBleakScanner(detection_callback, adapter)
        scanner.set_failure_mode(1.0)  # Always fail
        return scanner
    
    @staticmethod
    def create_unreliable_scanner(detection_callback=None, adapter=None):
        """Create a scanner with intermittent failures."""
        scanner = MockBleakScanner(detection_callback, adapter)
        scanner.set_failure_mode(0.3)  # 30% failure rate
        scanner.discovery_probability = 0.5  # 50% discovery rate
        return scanner
    
    @staticmethod
    def create_single_device_scanner(mac_address: str, data_format: int = 5, 
                                   detection_callback=None, adapter=None):
        """Create a scanner with a single specific device."""
        scanner = MockBleakScanner(detection_callback, adapter)
        scanner.mock_devices = [
            MockRuuviDevice(
                mac_address=mac_address,
                name=f"Ruuvi {mac_address[-4:]}",
                data_format=data_format
            )
        ]
        return scanner


# Monkey patch helper for tests
def patch_bleak_scanner(monkeypatch, scanner_factory=None):
    """
    Monkey patch bleak.BleakScanner with mock implementation.
    
    Args:
        monkeypatch: pytest monkeypatch fixture
        scanner_factory: Optional factory function for creating scanners
    """
    if scanner_factory is None:
        scanner_factory = MockBleakScanner
    
    monkeypatch.setattr("bleak.BleakScanner", scanner_factory)
    monkeypatch.setattr("src.ble.scanner.BleakScanner", scanner_factory)


# Context manager for temporary scanner patching
class MockScannerContext:
    """Context manager for temporarily using mock scanner."""
    
    def __init__(self, scanner_factory=None):
        self.scanner_factory = scanner_factory or MockBleakScanner
        self.original_scanner = None
    
    def __enter__(self):
        import bleak
        import src.ble.scanner
        
        self.original_scanner = bleak.BleakScanner
        bleak.BleakScanner = self.scanner_factory
        src.ble.scanner.BleakScanner = self.scanner_factory
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.original_scanner:
            import bleak
            import src.ble.scanner
            
            bleak.BleakScanner = self.original_scanner
            src.ble.scanner.BleakScanner = self.original_scanner