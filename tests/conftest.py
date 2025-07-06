"""
Pytest configuration and shared fixtures for Ruuvi Sensor Service tests.
Provides common test fixtures, mock objects, and test utilities.
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock
from typing import Dict, List, Optional

# Import the modules we're testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.ble.scanner import RuuviBLEScanner, RuuviSensorData, RuuviDataFormat


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = Mock(spec=Config)
    
    # BLE configuration
    config.ble_scan_duration = 5.0
    config.ble_scan_interval = 10
    config.ble_retry_attempts = 2
    config.ble_retry_delay = 1.0
    config.ble_adapter = "auto"
    
    # Logging configuration
    config.log_level = "DEBUG"
    config.log_dir = Path("./test_logs")
    config.log_max_file_size = 1024 * 1024  # 1MB
    config.log_backup_count = 2
    config.log_enable_console = False  # Disable console logging in tests
    config.log_enable_syslog = False
    
    # Performance monitoring
    config.enable_performance_monitoring = True
    config.performance_log_interval = 60
    
    return config


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock(spec=ProductionLogger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture
def mock_performance_monitor():
    """Create a mock performance monitor for testing."""
    monitor = Mock(spec=PerformanceMonitor)
    monitor.record_metric = Mock()
    monitor.measure_time = Mock()
    monitor.get_metrics = Mock(return_value={})
    
    # Mock the context manager for measure_time
    mock_context = MagicMock()
    mock_context.__enter__ = Mock(return_value=mock_context)
    mock_context.__exit__ = Mock(return_value=None)
    monitor.measure_time.return_value = mock_context
    
    return monitor


@pytest.fixture
def sample_format3_data():
    """Sample Format 3 manufacturer data for testing."""
    # Format 3: [format, humidity, temp_int, temp_frac, pressure_high, pressure_low, 
    #           acc_x_high, acc_x_low, acc_y_high, acc_y_low, acc_z_high, acc_z_low,
    #           battery_high, battery_low]
    return bytes([
        3,          # Format 3
        50,         # Humidity: 25.0% (50 / 2)
        20,         # Temperature integer: 20°C
        50,         # Temperature fraction: 0.50°C (total: 20.50°C)
        0x27, 0x10, # Pressure: 10000 + 50000 = 60000 Pa = 600.00 hPa
        0x03, 0xE8, # Acceleration X: 1000 mg = 1.0 g
        0xFF, 0x38, # Acceleration Y: -200 mg = -0.2 g
        0x00, 0x64, # Acceleration Z: 100 mg = 0.1 g
        0x0B, 0xB8  # Battery: 3000 mV = 3.0 V
    ])


@pytest.fixture
def sample_format5_data():
    """Sample Format 5 manufacturer data for testing."""
    # Format 5: [format, temp_high, temp_low, humidity_high, humidity_low,
    #           pressure_high, pressure_low, acc_x_high, acc_x_low, acc_y_high, acc_y_low,
    #           acc_z_high, acc_z_low, power_high, power_low, movement_counter,
    #           seq_high, seq_low, mac1, mac2, mac3, mac4, mac5, mac6]
    return bytes([
        5,          # Format 5
        0x0F, 0xA0, # Temperature: 4000 * 0.005 = 20.0°C
        0x27, 0x10, # Humidity: 10000 * 0.0025 = 25.0%
        0x27, 0x10, # Pressure: 10000 + 50000 = 60000 Pa = 600.00 hPa
        0x03, 0xE8, # Acceleration X: 1000 mg = 1.0 g
        0xFF, 0x38, # Acceleration Y: -200 mg = -0.2 g
        0x00, 0x64, # Acceleration Z: 100 mg = 0.1 g
        0x67, 0x04, # Power info: battery=3200mV, tx_power=8dBm
        42,         # Movement counter
        0x01, 0x00, # Measurement sequence: 256
        0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF  # MAC address
    ])


@pytest.fixture
def sample_malformed_data():
    """Sample malformed manufacturer data for testing error handling."""
    return {
        'too_short_format3': bytes([3, 50, 20]),  # Only 3 bytes, needs 14
        'too_short_format5': bytes([5, 0x0F, 0xA0, 0x27]),  # Only 4 bytes, needs 24
        'unknown_format': bytes([99, 0x01, 0x02, 0x03]),  # Unknown format
        'empty_data': bytes([]),  # Empty data
        'invalid_struct': bytes([3] + [0xFF] * 13)  # Valid length but invalid values
    }


@pytest.fixture
def sample_sensor_data():
    """Sample parsed sensor data for testing."""
    return RuuviSensorData(
        mac_address="AA:BB:CC:DD:EE:FF",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        data_format=RuuviDataFormat.FORMAT_5,
        temperature=20.0,
        humidity=25.0,
        pressure=600.0,
        acceleration_x=1.0,
        acceleration_y=-0.2,
        acceleration_z=0.1,
        battery_voltage=3.2,
        tx_power=8,
        movement_counter=42,
        measurement_sequence=256,
        rssi=-65,
        raw_data=bytes([5] + [0] * 23)
    )


@pytest.fixture
def mock_ble_device():
    """Create a mock BLE device for testing."""
    device = Mock()
    device.address = "AA:BB:CC:DD:EE:FF"
    device.name = "Ruuvi 1234"
    return device


@pytest.fixture
def mock_advertisement_data():
    """Create mock advertisement data for testing."""
    def _create_ad_data(manufacturer_data: Dict[int, bytes], rssi: int = -65):
        ad_data = Mock()
        ad_data.manufacturer_data = manufacturer_data
        ad_data.rssi = rssi
        ad_data.local_name = "Ruuvi 1234"
        return ad_data
    
    return _create_ad_data


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_test_dir(tmp_path):
    """Create a temporary directory for test files."""
    test_dir = tmp_path / "ruuvi_tests"
    test_dir.mkdir()
    return test_dir


# Test data validation helpers
def validate_sensor_data(sensor_data: RuuviSensorData) -> bool:
    """Validate that sensor data contains expected fields and ranges."""
    if not sensor_data.mac_address:
        return False
    
    if sensor_data.temperature is not None:
        if not (-40 <= sensor_data.temperature <= 85):  # Typical sensor range
            return False
    
    if sensor_data.humidity is not None:
        if not (0 <= sensor_data.humidity <= 100):
            return False
    
    if sensor_data.pressure is not None:
        if not (300 <= sensor_data.pressure <= 1100):  # Typical atmospheric range
            return False
    
    if sensor_data.battery_voltage is not None:
        if not (1.0 <= sensor_data.battery_voltage <= 4.0):  # Typical battery range
            return False
    
    return True


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_bluetooth: mark test as requiring Bluetooth hardware"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add unit marker to tests in unit/ directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        
        # Add integration marker to tests in integration/ directory
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to tests that might be slow
        if "continuous" in item.name or "long" in item.name:
            item.add_marker(pytest.mark.slow)