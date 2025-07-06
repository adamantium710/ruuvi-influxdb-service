"""
Test helper utilities for Ruuvi Sensor Service tests.
Provides common testing functions, data generators, and assertion helpers.
"""

import random
import struct
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from unittest.mock import Mock

from src.ble.scanner import RuuviSensorData, RuuviDataFormat


class SensorDataGenerator:
    """Generator for realistic sensor data for testing."""
    
    @staticmethod
    def generate_realistic_temperature(base_temp: float = 20.0, variation: float = 5.0) -> float:
        """Generate realistic temperature reading."""
        return base_temp + random.uniform(-variation, variation)
    
    @staticmethod
    def generate_realistic_humidity(base_humidity: float = 50.0, variation: float = 20.0) -> float:
        """Generate realistic humidity reading."""
        humidity = base_humidity + random.uniform(-variation, variation)
        return max(0.0, min(100.0, humidity))
    
    @staticmethod
    def generate_realistic_pressure(base_pressure: float = 1013.25, variation: float = 50.0) -> float:
        """Generate realistic atmospheric pressure reading."""
        return base_pressure + random.uniform(-variation, variation)
    
    @staticmethod
    def generate_realistic_acceleration() -> Tuple[float, float, float]:
        """Generate realistic acceleration readings (typically around 1g for Z-axis)."""
        acc_x = random.uniform(-0.5, 0.5)
        acc_y = random.uniform(-0.5, 0.5)
        acc_z = random.uniform(0.8, 1.2)  # Usually pointing up
        return acc_x, acc_y, acc_z
    
    @staticmethod
    def generate_realistic_battery_voltage(min_voltage: float = 2.0, max_voltage: float = 3.6) -> float:
        """Generate realistic battery voltage."""
        return random.uniform(min_voltage, max_voltage)
    
    @staticmethod
    def generate_mac_address() -> str:
        """Generate a random MAC address."""
        return ':'.join([f'{random.randint(0, 255):02X}' for _ in range(6)])
    
    @staticmethod
    def generate_format3_data(
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        pressure: Optional[float] = None,
        battery_voltage: Optional[float] = None
    ) -> bytes:
        """Generate Format 3 manufacturer data."""
        temp = temperature or SensorDataGenerator.generate_realistic_temperature()
        hum = humidity or SensorDataGenerator.generate_realistic_humidity()
        press = pressure or SensorDataGenerator.generate_realistic_pressure()
        battery = battery_voltage or SensorDataGenerator.generate_realistic_battery_voltage()
        acc_x, acc_y, acc_z = SensorDataGenerator.generate_realistic_acceleration()
        
        # Format 3 encoding
        humidity_byte = int(hum * 2)
        temp_int = int(temp)
        temp_frac = int((temp - temp_int) * 100)
        
        pressure_pa = int(press * 100 - 50000)
        acc_x_mg = int(acc_x * 1000)
        acc_y_mg = int(acc_y * 1000)
        acc_z_mg = int(acc_z * 1000)
        battery_mv = int(battery * 1000)
        
        return bytes([
            3,  # Format
            humidity_byte,
            temp_int & 0xFF,
            temp_frac,
            (pressure_pa >> 8) & 0xFF,
            pressure_pa & 0xFF,
            (acc_x_mg >> 8) & 0xFF,
            acc_x_mg & 0xFF,
            (acc_y_mg >> 8) & 0xFF,
            acc_y_mg & 0xFF,
            (acc_z_mg >> 8) & 0xFF,
            acc_z_mg & 0xFF,
            (battery_mv >> 8) & 0xFF,
            battery_mv & 0xFF
        ])
    
    @staticmethod
    def generate_format5_data(
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        pressure: Optional[float] = None,
        battery_voltage: Optional[float] = None,
        mac_address: Optional[str] = None
    ) -> bytes:
        """Generate Format 5 manufacturer data."""
        temp = temperature or SensorDataGenerator.generate_realistic_temperature()
        hum = humidity or SensorDataGenerator.generate_realistic_humidity()
        press = pressure or SensorDataGenerator.generate_realistic_pressure()
        battery = battery_voltage or SensorDataGenerator.generate_realistic_battery_voltage()
        mac = mac_address or SensorDataGenerator.generate_mac_address()
        acc_x, acc_y, acc_z = SensorDataGenerator.generate_realistic_acceleration()
        
        # Format 5 encoding
        temp_raw = int(temp / 0.005)
        humidity_raw = int(hum / 0.0025)
        pressure_pa = int(press * 100 - 50000)
        
        acc_x_mg = int(acc_x * 1000)
        acc_y_mg = int(acc_y * 1000)
        acc_z_mg = int(acc_z * 1000)
        
        # Power info
        battery_mv = int(battery * 1000)
        battery_raw = battery_mv - 1600
        tx_power_raw = random.randint(0, 20)
        power_info = (battery_raw << 5) | tx_power_raw
        
        movement_counter = random.randint(0, 255)
        measurement_sequence = random.randint(0, 65535)
        
        # MAC address bytes
        mac_bytes = [int(b, 16) for b in mac.split(':')]
        
        return bytes([
            5,  # Format
            (temp_raw >> 8) & 0xFF,
            temp_raw & 0xFF,
            (humidity_raw >> 8) & 0xFF,
            humidity_raw & 0xFF,
            (pressure_pa >> 8) & 0xFF,
            pressure_pa & 0xFF,
            (acc_x_mg >> 8) & 0xFF,
            acc_x_mg & 0xFF,
            (acc_y_mg >> 8) & 0xFF,
            acc_y_mg & 0xFF,
            (acc_z_mg >> 8) & 0xFF,
            acc_z_mg & 0xFF,
            (power_info >> 8) & 0xFF,
            power_info & 0xFF,
            movement_counter,
            (measurement_sequence >> 8) & 0xFF,
            measurement_sequence & 0xFF,
        ] + mac_bytes)
    
    @staticmethod
    def generate_sensor_data(
        data_format: RuuviDataFormat = RuuviDataFormat.FORMAT_5,
        mac_address: Optional[str] = None,
        **kwargs
    ) -> RuuviSensorData:
        """Generate complete RuuviSensorData object."""
        mac = mac_address or SensorDataGenerator.generate_mac_address()
        
        if data_format == RuuviDataFormat.FORMAT_3:
            raw_data = SensorDataGenerator.generate_format3_data(**kwargs)
        elif data_format == RuuviDataFormat.FORMAT_5:
            raw_data = SensorDataGenerator.generate_format5_data(mac_address=mac, **kwargs)
        else:
            raise ValueError(f"Unsupported data format: {data_format}")
        
        # Generate realistic values
        temp = kwargs.get('temperature', SensorDataGenerator.generate_realistic_temperature())
        hum = kwargs.get('humidity', SensorDataGenerator.generate_realistic_humidity())
        press = kwargs.get('pressure', SensorDataGenerator.generate_realistic_pressure())
        battery = kwargs.get('battery_voltage', SensorDataGenerator.generate_realistic_battery_voltage())
        acc_x, acc_y, acc_z = SensorDataGenerator.generate_realistic_acceleration()
        
        sensor_data = RuuviSensorData(
            mac_address=mac,
            timestamp=datetime.utcnow(),
            data_format=data_format,
            temperature=temp,
            humidity=hum,
            pressure=press,
            acceleration_x=acc_x,
            acceleration_y=acc_y,
            acceleration_z=acc_z,
            battery_voltage=battery,
            rssi=random.randint(-80, -40),
            raw_data=raw_data
        )
        
        # Add Format 5 specific fields
        if data_format == RuuviDataFormat.FORMAT_5:
            sensor_data.tx_power = random.randint(-40, 20)
            sensor_data.movement_counter = random.randint(0, 255)
            sensor_data.measurement_sequence = random.randint(0, 65535)
        
        return sensor_data


class TestAssertions:
    """Custom assertion helpers for sensor data testing."""
    
    @staticmethod
    def assert_sensor_data_valid(sensor_data: RuuviSensorData, tolerance: float = 0.01):
        """Assert that sensor data contains valid values."""
        assert sensor_data is not None, "Sensor data should not be None"
        assert sensor_data.mac_address is not None, "MAC address should not be None"
        assert sensor_data.timestamp is not None, "Timestamp should not be None"
        assert sensor_data.data_format is not None, "Data format should not be None"
        
        # Temperature validation
        if sensor_data.temperature is not None:
            assert -200 <= sensor_data.temperature <= 200, f"Temperature out of range: {sensor_data.temperature}"
        
        # Humidity validation
        if sensor_data.humidity is not None:
            assert 0 <= sensor_data.humidity <= 100, f"Humidity out of range: {sensor_data.humidity}"
        
        # Pressure validation
        if sensor_data.pressure is not None:
            assert 0 <= sensor_data.pressure <= 2000, f"Pressure out of range: {sensor_data.pressure}"
        
        # Battery voltage validation
        if sensor_data.battery_voltage is not None:
            assert 0 <= sensor_data.battery_voltage <= 10, f"Battery voltage out of range: {sensor_data.battery_voltage}"
        
        # RSSI validation
        if sensor_data.rssi is not None:
            assert -120 <= sensor_data.rssi <= 0, f"RSSI out of range: {sensor_data.rssi}"
    
    @staticmethod
    def assert_sensor_data_equals(
        actual: RuuviSensorData, 
        expected: RuuviSensorData, 
        tolerance: float = 0.01
    ):
        """Assert that two sensor data objects are equal within tolerance."""
        assert actual.mac_address == expected.mac_address
        assert actual.data_format == expected.data_format
        
        # Compare floating point values with tolerance
        if expected.temperature is not None:
            assert actual.temperature is not None
            assert abs(actual.temperature - expected.temperature) <= tolerance
        
        if expected.humidity is not None:
            assert actual.humidity is not None
            assert abs(actual.humidity - expected.humidity) <= tolerance
        
        if expected.pressure is not None:
            assert actual.pressure is not None
            assert abs(actual.pressure - expected.pressure) <= tolerance
        
        if expected.battery_voltage is not None:
            assert actual.battery_voltage is not None
            assert abs(actual.battery_voltage - expected.battery_voltage) <= tolerance
    
    @staticmethod
    def assert_mac_address_valid(mac_address: str):
        """Assert that MAC address is in valid format."""
        assert mac_address is not None, "MAC address should not be None"
        parts = mac_address.split(':')
        assert len(parts) == 6, f"MAC address should have 6 parts: {mac_address}"
        
        for part in parts:
            assert len(part) == 2, f"Each MAC part should be 2 characters: {part}"
            int(part, 16)  # Should not raise ValueError
    
    @staticmethod
    def assert_timestamp_recent(timestamp: datetime, max_age_seconds: float = 60.0):
        """Assert that timestamp is recent."""
        assert timestamp is not None, "Timestamp should not be None"
        age = (datetime.utcnow() - timestamp).total_seconds()
        assert age <= max_age_seconds, f"Timestamp too old: {age} seconds"


class MockFactory:
    """Factory for creating mock objects for testing."""
    
    @staticmethod
    def create_mock_config(**overrides) -> Mock:
        """Create a mock configuration object."""
        config = Mock()
        
        # Default values
        config.ble_scan_duration = 5.0
        config.ble_scan_interval = 10
        config.ble_retry_attempts = 3
        config.ble_retry_delay = 1.0
        config.ble_adapter = "auto"
        config.log_level = "INFO"
        config.enable_performance_monitoring = True
        
        # Apply overrides
        for key, value in overrides.items():
            setattr(config, key, value)
        
        return config
    
    @staticmethod
    def create_mock_logger() -> Mock:
        """Create a mock logger object."""
        logger = Mock()
        logger.debug = Mock()
        logger.info = Mock()
        logger.warning = Mock()
        logger.error = Mock()
        logger.critical = Mock()
        return logger
    
    @staticmethod
    def create_mock_performance_monitor() -> Mock:
        """Create a mock performance monitor object."""
        monitor = Mock()
        monitor.record_metric = Mock()
        monitor.get_metrics = Mock(return_value={})
        
        # Mock the context manager for measure_time
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        monitor.measure_time = Mock(return_value=mock_context)
        
        return monitor
    
    @staticmethod
    def create_mock_ble_device(mac_address: str, name: str = None) -> Mock:
        """Create a mock BLE device."""
        device = Mock()
        device.address = mac_address.upper()
        device.name = name or f"Ruuvi {mac_address[-4:]}"
        return device
    
    @staticmethod
    def create_mock_advertisement_data(
        manufacturer_data: Dict[int, bytes],
        rssi: int = -65,
        local_name: str = "Ruuvi Test"
    ) -> Mock:
        """Create mock advertisement data."""
        ad_data = Mock()
        ad_data.manufacturer_data = manufacturer_data
        ad_data.rssi = rssi
        ad_data.local_name = local_name
        ad_data.service_data = {}
        ad_data.service_uuids = []
        return ad_data


class TestScenarios:
    """Pre-defined test scenarios for common testing patterns."""
    
    @staticmethod
    def create_indoor_scenario() -> Dict[str, Any]:
        """Create indoor environment test scenario."""
        return {
            'name': 'indoor',
            'temperature': 22.0,
            'humidity': 45.0,
            'pressure': 1013.25,
            'battery_voltage': 3.2,
            'expected_ranges': {
                'temperature': (18.0, 26.0),
                'humidity': (30.0, 60.0),
                'pressure': (1000.0, 1030.0)
            }
        }
    
    @staticmethod
    def create_outdoor_cold_scenario() -> Dict[str, Any]:
        """Create cold outdoor environment test scenario."""
        return {
            'name': 'outdoor_cold',
            'temperature': -5.0,
            'humidity': 80.0,
            'pressure': 1020.0,
            'battery_voltage': 2.8,
            'expected_ranges': {
                'temperature': (-10.0, 0.0),
                'humidity': (70.0, 90.0),
                'pressure': (1010.0, 1030.0)
            }
        }
    
    @staticmethod
    def create_outdoor_hot_scenario() -> Dict[str, Any]:
        """Create hot outdoor environment test scenario."""
        return {
            'name': 'outdoor_hot',
            'temperature': 35.0,
            'humidity': 25.0,
            'pressure': 1005.0,
            'battery_voltage': 3.0,
            'expected_ranges': {
                'temperature': (30.0, 40.0),
                'humidity': (15.0, 35.0),
                'pressure': (995.0, 1015.0)
            }
        }
    
    @staticmethod
    def create_low_battery_scenario() -> Dict[str, Any]:
        """Create low battery test scenario."""
        return {
            'name': 'low_battery',
            'temperature': 20.0,
            'humidity': 50.0,
            'pressure': 1013.25,
            'battery_voltage': 2.2,
            'expected_ranges': {
                'battery_voltage': (2.0, 2.5)
            }
        }
    
    @staticmethod
    def get_all_scenarios() -> List[Dict[str, Any]]:
        """Get all predefined test scenarios."""
        return [
            TestScenarios.create_indoor_scenario(),
            TestScenarios.create_outdoor_cold_scenario(),
            TestScenarios.create_outdoor_hot_scenario(),
            TestScenarios.create_low_battery_scenario()
        ]


class DataValidation:
    """Data validation utilities for testing."""
    
    @staticmethod
    def validate_sensor_reading_ranges(sensor_data: RuuviSensorData) -> List[str]:
        """Validate sensor readings are within expected ranges."""
        errors = []
        
        # Temperature validation (-40°C to +85°C for typical sensors)
        if sensor_data.temperature is not None:
            if not (-40 <= sensor_data.temperature <= 85):
                errors.append(f"Temperature {sensor_data.temperature}°C out of range [-40, 85]")
        
        # Humidity validation (0% to 100%)
        if sensor_data.humidity is not None:
            if not (0 <= sensor_data.humidity <= 100):
                errors.append(f"Humidity {sensor_data.humidity}% out of range [0, 100]")
        
        # Pressure validation (300 to 1100 hPa for atmospheric pressure)
        if sensor_data.pressure is not None:
            if not (300 <= sensor_data.pressure <= 1100):
                errors.append(f"Pressure {sensor_data.pressure} hPa out of range [300, 1100]")
        
        # Battery voltage validation (1.0V to 4.0V for typical batteries)
        if sensor_data.battery_voltage is not None:
            if not (1.0 <= sensor_data.battery_voltage <= 4.0):
                errors.append(f"Battery voltage {sensor_data.battery_voltage}V out of range [1.0, 4.0]")
        
        # Acceleration validation (-32g to +32g for typical accelerometers)
        for axis, value in [('X', sensor_data.acceleration_x), 
                           ('Y', sensor_data.acceleration_y), 
                           ('Z', sensor_data.acceleration_z)]:
            if value is not None:
                if not (-32 <= value <= 32):
                    errors.append(f"Acceleration {axis} {value}g out of range [-32, 32]")
        
        # RSSI validation (-120 dBm to 0 dBm)
        if sensor_data.rssi is not None:
            if not (-120 <= sensor_data.rssi <= 0):
                errors.append(f"RSSI {sensor_data.rssi} dBm out of range [-120, 0]")
        
        return errors
    
    @staticmethod
    def validate_data_consistency(sensor_data: RuuviSensorData) -> List[str]:
        """Validate internal data consistency."""
        errors = []
        
        # Check that MAC address is set for Format 5
        if sensor_data.data_format == RuuviDataFormat.FORMAT_5:
            if not sensor_data.mac_address or sensor_data.mac_address == "":
                errors.append("Format 5 data should have MAC address")
        
        # Check that Format 5 specific fields are present
        if sensor_data.data_format == RuuviDataFormat.FORMAT_5:
            if sensor_data.tx_power is None:
                errors.append("Format 5 data should have TX power")
            if sensor_data.movement_counter is None:
                errors.append("Format 5 data should have movement counter")
            if sensor_data.measurement_sequence is None:
                errors.append("Format 5 data should have measurement sequence")
        
        # Check timestamp is reasonable
        if sensor_data.timestamp:
            age = (datetime.utcnow() - sensor_data.timestamp).total_seconds()
            if age > 3600:  # More than 1 hour old
                errors.append(f"Timestamp is too old: {age} seconds")
            if age < -60:  # More than 1 minute in the future
                errors.append(f"Timestamp is in the future: {age} seconds")
        
        return errors


# Convenience functions for common test patterns
def create_test_sensor_data(data_format: int = 5, **kwargs) -> RuuviSensorData:
    """Convenience function to create test sensor data."""
    format_enum = RuuviDataFormat.FORMAT_5 if data_format == 5 else RuuviDataFormat.FORMAT_3
    return SensorDataGenerator.generate_sensor_data(format_enum, **kwargs)


def assert_valid_ruuvi_data(sensor_data: RuuviSensorData):
    """Convenience function to assert valid Ruuvi sensor data."""
    TestAssertions.assert_sensor_data_valid(sensor_data)
    
    validation_errors = DataValidation.validate_sensor_reading_ranges(sensor_data)
    assert not validation_errors, f"Validation errors: {validation_errors}"
    
    consistency_errors = DataValidation.validate_data_consistency(sensor_data)
    assert not consistency_errors, f"Consistency errors: {consistency_errors}"


def create_mock_scanner_components():
    """Convenience function to create all mock scanner components."""
    return (
        MockFactory.create_mock_config(),
        MockFactory.create_mock_logger(),
        MockFactory.create_mock_performance_monitor()
    )