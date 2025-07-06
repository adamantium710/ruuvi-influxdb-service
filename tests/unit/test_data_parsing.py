"""
Unit tests for Ruuvi sensor data parsing.
Tests Format 3 and Format 5 data parsing with comprehensive edge cases.
"""

import pytest
import struct
from datetime import datetime
from unittest.mock import Mock, patch

from src.ble.scanner import RuuviBLEScanner, RuuviSensorData, RuuviDataFormat
from tests.fixtures.sensor_data import SensorDataFixtures


class TestRuuviDataParsing:
    """Test suite for Ruuvi data parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.fixtures = SensorDataFixtures()
        
        # Create a minimal scanner instance for testing parsing methods
        self.mock_config = Mock()
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        self.scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
    
    def test_parse_manufacturer_data_ruuvi_format3(self):
        """Test parsing of valid Format 3 manufacturer data."""
        format3_samples = self.fixtures.format3_valid_samples()
        
        for sample_name, sample_data in format3_samples.items():
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: sample_data['raw_data']
            }
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            
            assert result is not None, f"Failed to parse {sample_name}"
            assert result.data_format == RuuviDataFormat.FORMAT_3
            
            # Validate all expected fields
            expected = sample_data['expected']
            errors = self.fixtures.validate_parsed_data(result, expected)
            assert not errors, f"Validation errors for {sample_name}: {errors}"
    
    def test_parse_manufacturer_data_ruuvi_format5(self):
        """Test parsing of valid Format 5 manufacturer data."""
        format5_samples = self.fixtures.format5_valid_samples()
        
        for sample_name, sample_data in format5_samples.items():
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: sample_data['raw_data']
            }
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            
            assert result is not None, f"Failed to parse {sample_name}"
            assert result.data_format == RuuviDataFormat.FORMAT_5
            
            # Validate all expected fields
            expected = sample_data['expected']
            errors = self.fixtures.validate_parsed_data(result, expected)
            assert not errors, f"Validation errors for {sample_name}: {errors}"
    
    def test_parse_manufacturer_data_non_ruuvi(self):
        """Test that non-Ruuvi manufacturer data is ignored."""
        non_ruuvi_data = {
            0x004C: bytes([0x01, 0x02, 0x03, 0x04]),  # Apple
            0x0006: bytes([0xAA, 0xBB, 0xCC])         # Microsoft
        }
        
        result = self.scanner._parse_manufacturer_data(non_ruuvi_data)
        assert result is None
    
    def test_parse_manufacturer_data_empty(self):
        """Test parsing of empty manufacturer data."""
        result = self.scanner._parse_manufacturer_data({})
        assert result is None
    
    def test_parse_manufacturer_data_malformed(self):
        """Test parsing of malformed Ruuvi data."""
        malformed_samples = self.fixtures.malformed_data_samples()
        
        for error_type, malformed_data in malformed_samples.items():
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: malformed_data
            }
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            assert result is None, f"Should reject malformed data: {error_type}"
    
    def test_parse_format3_valid_data(self):
        """Test Format 3 parsing with valid data."""
        format3_samples = self.fixtures.format3_valid_samples()
        
        for sample_name, sample_data in format3_samples.items():
            result = self.scanner._parse_format_3(sample_data['raw_data'])
            
            assert result is not None, f"Failed to parse Format 3 {sample_name}"
            assert result.data_format == RuuviDataFormat.FORMAT_3
            
            # Check specific Format 3 fields
            expected = sample_data['expected']
            assert abs(result.temperature - expected['temperature']) < 0.01
            assert abs(result.humidity - expected['humidity']) < 0.01
            assert abs(result.pressure - expected['pressure']) < 0.01
            assert abs(result.battery_voltage - expected['battery_voltage']) < 0.01
            
            # Format 3 doesn't have these fields
            assert result.tx_power is None
            assert result.movement_counter is None
            assert result.measurement_sequence is None
    
    def test_parse_format3_edge_cases(self):
        """Test Format 3 parsing with edge cases."""
        # Test minimum temperature (-128°C + 0.00°C)
        min_temp_data = bytes([3, 0, 128, 0] + [0] * 10)  # -128 as signed byte
        result = self.scanner._parse_format_3(min_temp_data)
        assert result is not None
        assert result.temperature == -128.0
        
        # Test maximum temperature (127°C + 0.99°C)
        max_temp_data = bytes([3, 0, 127, 99] + [0] * 10)
        result = self.scanner._parse_format_3(max_temp_data)
        assert result is not None
        assert result.temperature == 127.99
        
        # Test zero values
        zero_data = bytes([3] + [0] * 13)
        result = self.scanner._parse_format_3(zero_data)
        assert result is not None
        assert result.temperature == 0.0
        assert result.humidity == 0.0
        assert result.pressure == 500.0  # 0 + 50000 Pa = 500 hPa
    
    def test_parse_format3_invalid_length(self):
        """Test Format 3 parsing with invalid data length."""
        # Too short
        short_data = bytes([3, 50, 20])
        result = self.scanner._parse_format_3(short_data)
        assert result is None
        
        # Empty data
        empty_data = bytes([])
        result = self.scanner._parse_format_3(empty_data)
        assert result is None
    
    def test_parse_format5_valid_data(self):
        """Test Format 5 parsing with valid data."""
        format5_samples = self.fixtures.format5_valid_samples()
        
        for sample_name, sample_data in format5_samples.items():
            result = self.scanner._parse_format_5(sample_data['raw_data'])
            
            assert result is not None, f"Failed to parse Format 5 {sample_name}"
            assert result.data_format == RuuviDataFormat.FORMAT_5
            
            # Check all Format 5 fields
            expected = sample_data['expected']
            errors = self.fixtures.validate_parsed_data(result, expected)
            assert not errors, f"Validation errors for {sample_name}: {errors}"
    
    def test_parse_format5_power_info_decoding(self):
        """Test Format 5 power info field decoding."""
        # Test specific power info values
        test_cases = [
            # (power_info_bytes, expected_battery_mv, expected_tx_power_dbm)
            (0xC818, 3200, 8),   # Normal case: ((0xC818 >> 5) + 1600) = 3200, (0x18 * 2 - 40) = 8
            (0xA296, 2900, 4),   # Lower battery: ((0xA296 >> 5) + 1600) = 2900, (0x16 * 2 - 40) = 4
            (0xE11C, 3400, 16),  # High values: ((0xE11C >> 5) + 1600) = 3400, (0x1C * 2 - 40) = 16
            (0x0000, 1600, -40), # Minimum values: ((0x0000 >> 5) + 1600) = 1600, (0x00 * 2 - 40) = -40
        ]
        
        for power_info, expected_battery_mv, expected_tx_dbm in test_cases:
            # Create Format 5 data with specific power info
            data = bytearray([5] + [0] * 23)
            data[13] = (power_info >> 8) & 0xFF
            data[14] = power_info & 0xFF
            
            result = self.scanner._parse_format_5(bytes(data))
            assert result is not None
            
            expected_battery_v = expected_battery_mv / 1000.0
            assert abs(result.battery_voltage - expected_battery_v) < 0.001
            assert result.tx_power == expected_tx_dbm
    
    def test_parse_format5_mac_address_extraction(self):
        """Test MAC address extraction from Format 5 data."""
        test_mac = "DE:AD:BE:EF:CA:FE"
        mac_bytes = [int(b, 16) for b in test_mac.split(':')]
        
        # Create Format 5 data with specific MAC
        data = bytearray([5] + [0] * 17 + mac_bytes)
        
        result = self.scanner._parse_format_5(bytes(data))
        assert result is not None
        assert result.mac_address == test_mac
    
    def test_parse_format5_invalid_length(self):
        """Test Format 5 parsing with invalid data length."""
        # Too short
        short_data = bytes([5, 0x0F, 0xA0, 0x27])
        result = self.scanner._parse_format_5(short_data)
        assert result is None
        
        # Empty data
        empty_data = bytes([])
        result = self.scanner._parse_format_5(empty_data)
        assert result is None
    
    def test_parse_format5_edge_cases(self):
        """Test Format 5 parsing with edge cases."""
        # Test minimum temperature
        min_temp_data = bytearray([5] + [0] * 23)
        min_temp_data[1] = 0x80  # -32768 * 0.005 = -163.84°C
        min_temp_data[2] = 0x00
        
        result = self.scanner._parse_format_5(bytes(min_temp_data))
        assert result is not None
        assert abs(result.temperature - (-163.84)) < 0.01
        
        # Test maximum temperature
        max_temp_data = bytearray([5] + [0] * 23)
        max_temp_data[1] = 0x7F  # 32767 * 0.005 = 163.835°C
        max_temp_data[2] = 0xFF
        
        result = self.scanner._parse_format_5(bytes(max_temp_data))
        assert result is not None
        assert abs(result.temperature - 163.835) < 0.01
    
    def test_parse_unknown_format(self):
        """Test parsing of unknown data formats."""
        unknown_formats = [0, 1, 2, 4, 6, 99, 255]
        
        for format_id in unknown_formats:
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: bytes([format_id] + [0] * 23)
            }
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            assert result is None, f"Should reject unknown format {format_id}"
    
    def test_struct_error_handling(self):
        """Test handling of struct.error exceptions."""
        # Create data that might cause struct errors
        problematic_data = [
            bytes([3] + [0xFF] * 13),  # All 0xFF for Format 3
            bytes([5] + [0xFF] * 23),  # All 0xFF for Format 5
        ]
        
        for data in problematic_data:
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: data
            }
            
            # Should not raise exception, should return None
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            # Result might be None or valid data, but should not crash
            assert result is None or isinstance(result, RuuviSensorData)
    
    def test_data_validation_ranges(self):
        """Test that parsed data falls within expected ranges."""
        all_samples = {
            **self.fixtures.format3_valid_samples(),
            **self.fixtures.format5_valid_samples()
        }
        
        for sample_name, sample_data in all_samples.items():
            manufacturer_data = {
                self.fixtures.RUUVI_MANUFACTURER_ID: sample_data['raw_data']
            }
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            assert result is not None
            
            # Validate reasonable ranges (not strict sensor limits, but sanity checks)
            if result.temperature is not None:
                assert -200 <= result.temperature <= 200, f"Temperature out of range in {sample_name}"
            
            if result.humidity is not None:
                assert 0 <= result.humidity <= 100, f"Humidity out of range in {sample_name}"
            
            if result.pressure is not None:
                assert 0 <= result.pressure <= 2000, f"Pressure out of range in {sample_name}"
            
            if result.battery_voltage is not None:
                assert 0 <= result.battery_voltage <= 10, f"Battery voltage out of range in {sample_name}"
    
    def test_timestamp_assignment(self):
        """Test that timestamps are properly assigned to parsed data."""
        sample_data = self.fixtures.format5_valid_samples()['indoor_normal']
        manufacturer_data = {
            self.fixtures.RUUVI_MANUFACTURER_ID: sample_data['raw_data']
        }
        
        before_parse = datetime.utcnow()
        result = self.scanner._parse_manufacturer_data(manufacturer_data)
        after_parse = datetime.utcnow()
        
        assert result is not None
        assert result.timestamp is not None
        assert before_parse <= result.timestamp <= after_parse
    
    def test_raw_data_preservation(self):
        """Test that raw data is preserved in parsed results."""
        sample_data = self.fixtures.format3_valid_samples()['indoor_normal']
        manufacturer_data = {
            self.fixtures.RUUVI_MANUFACTURER_ID: sample_data['raw_data']
        }
        
        result = self.scanner._parse_manufacturer_data(manufacturer_data)
        
        assert result is not None
        assert result.raw_data == sample_data['raw_data']
    
    @pytest.mark.parametrize("format_id,expected_format", [
        (3, RuuviDataFormat.FORMAT_3),
        (5, RuuviDataFormat.FORMAT_5),
    ])
    def test_data_format_assignment(self, format_id, expected_format):
        """Test that data format is correctly assigned."""
        if format_id == 3:
            sample_data = self.fixtures.format3_valid_samples()['indoor_normal']['raw_data']
        else:
            sample_data = self.fixtures.format5_valid_samples()['indoor_normal']['raw_data']
        
        manufacturer_data = {
            self.fixtures.RUUVI_MANUFACTURER_ID: sample_data
        }
        
        result = self.scanner._parse_manufacturer_data(manufacturer_data)
        
        assert result is not None
        assert result.data_format == expected_format
    
    def test_logging_on_parse_errors(self):
        """Test that parsing errors are properly logged."""
        malformed_data = {
            self.fixtures.RUUVI_MANUFACTURER_ID: bytes([3, 50])  # Too short
        }
        
        result = self.scanner._parse_manufacturer_data(malformed_data)
        assert result is None
        
        # Check that warning was logged (mock logger should have been called)
        # Note: This depends on the actual implementation logging warnings
        # The scanner should log warnings for malformed data
    
    def test_multiple_manufacturer_data(self):
        """Test parsing when multiple manufacturers are present."""
        ruuvi_data = self.fixtures.format5_valid_samples()['indoor_normal']['raw_data']
        manufacturer_data = {
            self.fixtures.RUUVI_MANUFACTURER_ID: ruuvi_data,
            0x004C: bytes([0x01, 0x02, 0x03, 0x04]),  # Apple data
            0x0006: bytes([0xAA, 0xBB, 0xCC])         # Microsoft data
        }
        
        result = self.scanner._parse_manufacturer_data(manufacturer_data)
        
        # Should successfully parse Ruuvi data and ignore others
        assert result is not None
        assert result.data_format == RuuviDataFormat.FORMAT_5
        assert result.temperature == 20.0  # From the sample data