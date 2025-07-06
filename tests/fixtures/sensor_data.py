"""
Sample sensor data fixtures for testing Ruuvi data parsing.
Provides realistic Format 3 and Format 5 manufacturer data samples.
"""

import struct
from typing import Dict, List, Tuple, Any
from datetime import datetime


class SensorDataFixtures:
    """Collection of sample sensor data for testing."""
    
    # Ruuvi manufacturer ID
    RUUVI_MANUFACTURER_ID = 0x0499
    
    @staticmethod
    def format3_valid_samples() -> Dict[str, Dict[str, Any]]:
        """
        Valid Format 3 data samples with expected parsed values.
        
        Returns:
            Dict mapping sample names to data and expected values
        """
        samples = {}
        
        # Sample 1: Normal indoor conditions
        samples['indoor_normal'] = {
            'raw_data': bytes([
                3,          # Format 3
                50,         # Humidity: 25.0% (50 / 2)
                20,         # Temperature integer: 20°C
                50,         # Temperature fraction: 0.50°C (total: 20.50°C)
                0x27, 0x10, # Pressure: 10000 + 50000 = 60000 Pa = 600.00 hPa
                0x03, 0xE8, # Acceleration X: 1000 mg = 1.0 g
                0xFF, 0x38, # Acceleration Y: -200 mg = -0.2 g (signed)
                0x00, 0x64, # Acceleration Z: 100 mg = 0.1 g
                0x0B, 0xB8  # Battery: 3000 mV = 3.0 V
            ]),
            'expected': {
                'temperature': 20.5,
                'humidity': 25.0,
                'pressure': 600.0,
                'acceleration_x': 1.0,
                'acceleration_y': -0.2,
                'acceleration_z': 0.1,
                'battery_voltage': 3.0,
                'data_format': 3
            }
        }
        
        # Sample 2: Cold outdoor conditions
        samples['outdoor_cold'] = {
            'raw_data': bytes([
                3,          # Format 3
                160,        # Humidity: 80.0% (160 / 2)
                -10 & 0xFF, # Temperature integer: -10°C (signed byte)
                25,         # Temperature fraction: 0.25°C (total: -9.75°C)
                0x1E, 0x14, # Pressure: 7700 + 50000 = 57700 Pa = 577.00 hPa
                0x00, 0x32, # Acceleration X: 50 mg = 0.05 g
                0x00, 0x64, # Acceleration Y: 100 mg = 0.1 g
                0x03, 0xE8, # Acceleration Z: 1000 mg = 1.0 g
                0x0A, 0x8C  # Battery: 2700 mV = 2.7 V
            ]),
            'expected': {
                'temperature': -9.75,
                'humidity': 80.0,
                'pressure': 577.0,
                'acceleration_x': 0.05,
                'acceleration_y': 0.1,
                'acceleration_z': 1.0,
                'battery_voltage': 2.7,
                'data_format': 3
            }
        }
        
        # Sample 3: Hot conditions with low battery
        samples['hot_low_battery'] = {
            'raw_data': bytes([
                3,          # Format 3
                60,         # Humidity: 30.0% (60 / 2)
                35,         # Temperature integer: 35°C
                75,         # Temperature fraction: 0.75°C (total: 35.75°C)
                0x26, 0x2C, # Pressure: 9772 + 50000 = 59772 Pa = 597.72 hPa
                0xFF, 0xCE, # Acceleration X: -50 mg = -0.05 g (signed)
                0x00, 0x00, # Acceleration Y: 0 mg = 0.0 g
                0x03, 0xE8, # Acceleration Z: 1000 mg = 1.0 g
                0x08, 0x98  # Battery: 2200 mV = 2.2 V (low)
            ]),
            'expected': {
                'temperature': 35.75,
                'humidity': 30.0,
                'pressure': 597.72,
                'acceleration_x': -0.05,
                'acceleration_y': 0.0,
                'acceleration_z': 1.0,
                'battery_voltage': 2.2,
                'data_format': 3
            }
        }
        
        # Sample 4: Edge case - maximum values
        samples['max_values'] = {
            'raw_data': bytes([
                3,          # Format 3
                200,        # Humidity: 100.0% (200 / 2)
                127,        # Temperature integer: 127°C (max signed byte)
                99,         # Temperature fraction: 0.99°C
                0xFF, 0xFF, # Pressure: 65535 + 50000 = 115535 Pa = 1155.35 hPa
                0x7F, 0xFF, # Acceleration X: 32767 mg = 32.767 g (max)
                0x7F, 0xFF, # Acceleration Y: 32767 mg = 32.767 g (max)
                0x7F, 0xFF, # Acceleration Z: 32767 mg = 32.767 g (max)
                0x0E, 0x10  # Battery: 3600 mV = 3.6 V (realistic max)
            ]),
            'expected': {
                'temperature': 127.99,
                'humidity': 100.0,
                'pressure': 1155.35,
                'acceleration_x': 32.767,
                'acceleration_y': 32.767,
                'acceleration_z': 32.767,
                'battery_voltage': 3.6,
                'data_format': 3
            }
        }
        
        return samples
    
    @staticmethod
    def format5_valid_samples() -> Dict[str, Dict[str, Any]]:
        """
        Valid Format 5 data samples with expected parsed values.
        
        Returns:
            Dict mapping sample names to data and expected values
        """
        samples = {}
        
        # Sample 1: Normal indoor conditions
        samples['indoor_normal'] = {
            'raw_data': bytes([
                5,          # Format 5
                0x0F, 0xA0, # Temperature: 4000 * 0.005 = 20.0°C
                0x27, 0x10, # Humidity: 10000 * 0.0025 = 25.0%
                0x27, 0x10, # Pressure: 10000 + 50000 = 60000 Pa = 600.00 hPa
                0x03, 0xE8, # Acceleration X: 1000 mg = 1.0 g
                0xFF, 0x38, # Acceleration Y: -200 mg = -0.2 g (signed)
                0x00, 0x64, # Acceleration Z: 100 mg = 0.1 g
                0xC8, 0x18, # Power info: battery=3200mV, tx_power=8dBm
                42,         # Movement counter
                0x01, 0x00, # Measurement sequence: 256
                0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF  # MAC address
            ]),
            'expected': {
                'temperature': 20.0,
                'humidity': 25.0,
                'pressure': 600.0,
                'acceleration_x': 1.0,
                'acceleration_y': -0.2,
                'acceleration_z': 0.1,
                'battery_voltage': 3.2,
                'tx_power': 8,
                'movement_counter': 42,
                'measurement_sequence': 256,
                'mac_address': 'AA:BB:CC:DD:EE:FF',
                'data_format': 5
            }
        }
        
        # Sample 2: Cold outdoor conditions
        samples['outdoor_cold'] = {
            'raw_data': bytes([
                5,          # Format 5
                0xF8, 0x30, # Temperature: -2000 * 0.005 = -10.0°C
                0x4E, 0x20, # Humidity: 20000 * 0.0025 = 50.0%
                0x1E, 0x14, # Pressure: 7700 + 50000 = 57700 Pa = 577.0 hPa
                0x00, 0x32, # Acceleration X: 50 mg = 0.05 g
                0x00, 0x64, # Acceleration Y: 100 mg = 0.1 g
                0x03, 0xE8, # Acceleration Z: 1000 mg = 1.0 g
                0xA2, 0x96, # Power info: battery=2900mV, tx_power=4dBm
                15,         # Movement counter
                0x02, 0x10, # Measurement sequence: 528
                0x11, 0x22, 0x33, 0x44, 0x55, 0x66  # MAC address
            ]),
            'expected': {
                'temperature': -10.0,
                'humidity': 50.0,
                'pressure': 577.0,
                'acceleration_x': 0.05,
                'acceleration_y': 0.1,
                'acceleration_z': 1.0,
                'battery_voltage': 2.9,
                'tx_power': 4,
                'movement_counter': 15,
                'measurement_sequence': 528,
                'mac_address': '11:22:33:44:55:66',
                'data_format': 5
            }
        }
        
        # Sample 3: High precision measurements
        samples['high_precision'] = {
            'raw_data': bytes([
                5,          # Format 5
                0x10, 0x68, # Temperature: 4200 * 0.005 = 21.0°C
                0x2A, 0xF8, # Humidity: 11000 * 0.0025 = 27.5%
                0x28, 0x6A, # Pressure: 10346 + 50000 = 60346 Pa = 603.46 hPa
                0x01, 0x2C, # Acceleration X: 300 mg = 0.3 g
                0xFE, 0xD4, # Acceleration Y: -300 mg = -0.3 g
                0x03, 0xF2, # Acceleration Z: 1010 mg = 1.01 g
                0xE1, 0x1C, # Power info: battery=3400mV, tx_power=16dBm
                128,        # Movement counter
                0x0A, 0xBC, # Measurement sequence: 2748
                0xDE, 0xAD, 0xBE, 0xEF, 0xCA, 0xFE  # MAC address
            ]),
            'expected': {
                'temperature': 21.0,
                'humidity': 27.5,
                'pressure': 603.46,
                'acceleration_x': 0.3,
                'acceleration_y': -0.3,
                'acceleration_z': 1.01,
                'battery_voltage': 3.4,
                'tx_power': 16,
                'movement_counter': 128,
                'measurement_sequence': 2748,
                'mac_address': 'DE:AD:BE:EF:CA:FE',
                'data_format': 5
            }
        }
        
        return samples
    
    @staticmethod
    def malformed_data_samples() -> Dict[str, bytes]:
        """
        Malformed data samples for testing error handling.
        
        Returns:
            Dict mapping error type to malformed data
        """
        return {
            # Format 3 errors
            'format3_too_short': bytes([3, 50, 20]),  # Only 3 bytes, needs 14
            'format3_empty': bytes([3]),  # Only format byte
            'format3_partial': bytes([3, 50, 20, 50, 0x27]),  # Partial data
            
            # Format 5 errors
            'format5_too_short': bytes([5, 0x0F, 0xA0, 0x27]),  # Only 4 bytes, needs 24
            'format5_empty': bytes([5]),  # Only format byte
            'format5_partial': bytes([5] + [0x00] * 10),  # Partial data
            
            # General errors
            'unknown_format': bytes([99, 0x01, 0x02, 0x03]),  # Unknown format
            'empty_data': bytes([]),  # Completely empty
            'invalid_format_byte': bytes([255, 255]),  # Invalid format sequence
            
            # Edge cases that might cause struct errors
            'format3_invalid_struct': bytes([3] + [0xFF] * 5),   # Too short for Format 3
            'format5_invalid_struct': bytes([5] + [0xFF] * 10),  # Too short for Format 5
        }
    
    @staticmethod
    def manufacturer_data_samples() -> Dict[str, Dict[int, bytes]]:
        """
        Complete manufacturer data samples as they would appear in BLE advertisements.
        
        Returns:
            Dict mapping sample names to manufacturer data dictionaries
        """
        format3_samples = SensorDataFixtures.format3_valid_samples()
        format5_samples = SensorDataFixtures.format5_valid_samples()
        malformed_samples = SensorDataFixtures.malformed_data_samples()
        
        samples = {}
        
        # Valid Ruuvi data
        for name, data in format3_samples.items():
            samples[f'ruuvi_format3_{name}'] = {
                SensorDataFixtures.RUUVI_MANUFACTURER_ID: data['raw_data']
            }
        
        for name, data in format5_samples.items():
            samples[f'ruuvi_format5_{name}'] = {
                SensorDataFixtures.RUUVI_MANUFACTURER_ID: data['raw_data']
            }
        
        # Malformed Ruuvi data
        for name, data in malformed_samples.items():
            samples[f'ruuvi_malformed_{name}'] = {
                SensorDataFixtures.RUUVI_MANUFACTURER_ID: data
            }
        
        # Non-Ruuvi manufacturer data (should be ignored)
        samples['non_ruuvi_apple'] = {
            0x004C: bytes([0x01, 0x02, 0x03, 0x04])  # Apple manufacturer ID
        }
        
        samples['non_ruuvi_unknown'] = {
            0x9999: bytes([0xAA, 0xBB, 0xCC])  # Unknown manufacturer
        }
        
        # Empty manufacturer data
        samples['empty_manufacturer_data'] = {}
        
        # Multiple manufacturers (Ruuvi + others)
        samples['multiple_manufacturers'] = {
            SensorDataFixtures.RUUVI_MANUFACTURER_ID: format5_samples['indoor_normal']['raw_data'],
            0x004C: bytes([0x01, 0x02, 0x03, 0x04])  # Apple data should be ignored
        }
        
        return samples
    
    @staticmethod
    def create_test_advertisement_data(manufacturer_data: Dict[int, bytes], 
                                     rssi: int = -65, 
                                     local_name: str = "Ruuvi Test") -> 'AdvertisementData':
        """
        Create mock advertisement data for testing.
        
        Args:
            manufacturer_data: Manufacturer data dictionary
            rssi: Signal strength
            local_name: Device local name
            
        Returns:
            Mock AdvertisementData object
        """
        from unittest.mock import Mock
        
        ad_data = Mock()
        ad_data.manufacturer_data = manufacturer_data
        ad_data.rssi = rssi
        ad_data.local_name = local_name
        ad_data.service_data = {}
        ad_data.service_uuids = []
        
        return ad_data
    
    @staticmethod
    def create_test_ble_device(mac_address: str, name: str = None) -> 'BLEDevice':
        """
        Create mock BLE device for testing.
        
        Args:
            mac_address: Device MAC address
            name: Device name
            
        Returns:
            Mock BLEDevice object
        """
        from unittest.mock import Mock
        
        device = Mock()
        device.address = mac_address.upper()
        device.name = name or f"Ruuvi {mac_address[-4:]}"
        
        return device
    
    @staticmethod
    def get_expected_values(sample_name: str, data_format: int) -> Dict[str, Any]:
        """
        Get expected parsed values for a sample.
        
        Args:
            sample_name: Name of the sample
            data_format: Data format (3 or 5)
            
        Returns:
            Dictionary of expected values
        """
        if data_format == 3:
            samples = SensorDataFixtures.format3_valid_samples()
        elif data_format == 5:
            samples = SensorDataFixtures.format5_valid_samples()
        else:
            raise ValueError(f"Unsupported data format: {data_format}")
        
        if sample_name not in samples:
            raise ValueError(f"Unknown sample: {sample_name}")
        
        return samples[sample_name]['expected']
    
    @staticmethod
    def validate_parsed_data(parsed_data, expected_data, tolerance: float = 0.01) -> List[str]:
        """
        Validate parsed sensor data against expected values.
        
        Args:
            parsed_data: Parsed RuuviSensorData object
            expected_data: Dictionary of expected values
            tolerance: Tolerance for floating point comparisons
            
        Returns:
            List of validation errors (empty if all valid)
        """
        errors = []
        
        for field, expected_value in expected_data.items():
            if not hasattr(parsed_data, field):
                errors.append(f"Missing field: {field}")
                continue
            
            actual_value = getattr(parsed_data, field)
            
            if isinstance(expected_value, float):
                if actual_value is None:
                    errors.append(f"Field {field} is None, expected {expected_value}")
                elif abs(actual_value - expected_value) > tolerance:
                    errors.append(f"Field {field}: expected {expected_value}, got {actual_value}")
            else:
                # Handle enum comparisons - convert enum values to their underlying type
                actual_compare_value = actual_value
                if hasattr(actual_value, 'value'):
                    actual_compare_value = actual_value.value
                elif hasattr(actual_value, '__int__'):
                    try:
                        actual_compare_value = int(actual_value)
                    except (ValueError, TypeError):
                        pass
                
                if actual_compare_value != expected_value:
                    errors.append(f"Field {field}: expected {expected_value}, got {actual_value}")
        
        return errors