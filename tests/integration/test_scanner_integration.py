"""
Integration tests for BLE scanner functionality.
Tests scanner initialization, device discovery, and callback system integration.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.ble.scanner import RuuviBLEScanner, RuuviSensorData, RuuviDataFormat
from tests.mocks.mock_ble_scanner import (
    MockBleakScanner, 
    MockBleakScannerFactory,
    patch_bleak_scanner
)
from tests.fixtures.sensor_data import SensorDataFixtures


class TestScannerInitialization:
    """Test scanner initialization with different configurations."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 5.0
        self.mock_config.ble_scan_interval = 10
        self.mock_config.ble_retry_attempts = 3
        self.mock_config.ble_retry_delay = 1.0
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager for measure_time
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_scanner_initialization_success(self, monkeypatch):
        """Test successful scanner initialization."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Initialize scanner
        result = await scanner._initialize_scanner()
        
        assert result is not None
        assert isinstance(result, MockBleakScanner)
    
    @pytest.mark.asyncio
    async def test_scanner_initialization_with_specific_adapter(self, monkeypatch):
        """Test scanner initialization with specific adapter."""
        self.mock_config.ble_adapter = "hci0"
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        result = await scanner._initialize_scanner()
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_scanner_initialization_failure_retry(self, monkeypatch):
        """Test scanner initialization with retry on failure."""
        patch_bleak_scanner(monkeypatch, MockBleakScannerFactory.create_failing_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with pytest.raises(Exception):  # Should eventually fail after retries
            await scanner._initialize_scanner()


class TestDeviceDiscovery:
    """Test device discovery workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 2.0  # Short duration for tests
        self.mock_config.ble_scan_interval = 5
        self.mock_config.ble_retry_attempts = 2
        self.mock_config.ble_retry_delay = 0.5
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
        
        self.discovered_devices = []
    
    def device_callback(self, sensor_data: RuuviSensorData):
        """Callback to collect discovered devices."""
        self.discovered_devices.append(sensor_data)
    
    @pytest.mark.asyncio
    async def test_single_scan_device_discovery(self, monkeypatch):
        """Test device discovery in a single scan."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        scanner.add_callback(self.device_callback)
        
        # Perform scan
        devices = await scanner.scan_once(duration=1.0)
        
        # Should discover mock devices
        assert len(devices) > 0
        assert len(self.discovered_devices) > 0
        
        # Verify device data
        for device in self.discovered_devices:
            assert isinstance(device, RuuviSensorData)
            assert device.mac_address is not None
            assert device.timestamp is not None
            assert device.data_format in [RuuviDataFormat.FORMAT_3, RuuviDataFormat.FORMAT_5]
    
    @pytest.mark.asyncio
    async def test_empty_scan_results(self, monkeypatch):
        """Test scan with no devices found."""
        patch_bleak_scanner(monkeypatch, MockBleakScannerFactory.create_empty_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        scanner.add_callback(self.device_callback)
        
        devices = await scanner.scan_once(duration=0.5)
        
        assert len(devices) == 0
        assert len(self.discovered_devices) == 0
    
    @pytest.mark.asyncio
    async def test_specific_device_discovery(self, monkeypatch):
        """Test discovery of a specific device."""
        target_mac = "AA:BB:CC:DD:EE:99"
        
        def create_single_device_scanner(detection_callback=None, adapter=None):
            return MockBleakScannerFactory.create_single_device_scanner(
                target_mac, 5, detection_callback, adapter
            )
        
        patch_bleak_scanner(monkeypatch, create_single_device_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        scanner.add_callback(self.device_callback)
        
        devices = await scanner.scan_once(duration=1.0)
        
        assert len(devices) == 1
        assert target_mac in devices
        assert devices[target_mac].mac_address == target_mac
    
    @pytest.mark.asyncio
    async def test_continuous_scan_workflow(self, monkeypatch):
        """Test continuous scanning workflow."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        scanner.add_callback(self.device_callback)
        
        # Start continuous scan
        await scanner.start_continuous_scan()
        
        # Let it run briefly
        await asyncio.sleep(1.0)
        
        # Stop continuous scan
        await scanner.stop_continuous_scan()
        
        # Should have discovered some devices
        assert len(self.discovered_devices) > 0
        assert not scanner.is_scanning()


class TestCallbackSystem:
    """Test callback system integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0
        self.mock_config.ble_scan_interval = 5
        self.mock_config.ble_retry_attempts = 1
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
        
        self.callback_results = []
    
    def create_test_callback(self, callback_id: str):
        """Create a test callback with specific ID."""
        def callback(sensor_data: RuuviSensorData):
            self.callback_results.append({
                'callback_id': callback_id,
                'mac_address': sensor_data.mac_address,
                'temperature': sensor_data.temperature,
                'timestamp': sensor_data.timestamp
            })
        return callback
    
    @pytest.mark.asyncio
    async def test_multiple_callbacks(self, monkeypatch):
        """Test multiple callbacks receiving data."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Add multiple callbacks
        callback1 = self.create_test_callback("callback1")
        callback2 = self.create_test_callback("callback2")
        callback3 = self.create_test_callback("callback3")
        
        scanner.add_callback(callback1)
        scanner.add_callback(callback2)
        scanner.add_callback(callback3)
        
        # Perform scan
        await scanner.scan_once(duration=0.5)
        
        # All callbacks should have received data
        callback_ids = {result['callback_id'] for result in self.callback_results}
        assert 'callback1' in callback_ids
        assert 'callback2' in callback_ids
        assert 'callback3' in callback_ids
    
    @pytest.mark.asyncio
    async def test_callback_removal_during_scan(self, monkeypatch):
        """Test callback removal functionality."""
        def create_reliable_scanner(detection_callback=None, adapter=None):
            scanner = MockBleakScanner(detection_callback, adapter)
            scanner.discovery_probability = 1.0  # Always discover devices
            return scanner
        
        patch_bleak_scanner(monkeypatch, create_reliable_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        callback1 = self.create_test_callback("callback1")
        callback2 = self.create_test_callback("callback2")
        
        scanner.add_callback(callback1)
        scanner.add_callback(callback2)
        
        # Remove one callback
        scanner.remove_callback(callback1)
        
        # Perform scan with longer duration to ensure device discovery
        await scanner.scan_once(duration=1.0)
        
        # Only callback2 should have received data
        callback_ids = {result['callback_id'] for result in self.callback_results}
        assert 'callback1' not in callback_ids
        assert 'callback2' in callback_ids
    
    def test_callback_error_isolation(self):
        """Test that callback errors don't affect other callbacks."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        def good_callback(data):
            self.callback_results.append("good_callback")
        
        def error_callback(data):
            raise ValueError("Callback error")
        
        def another_good_callback(data):
            self.callback_results.append("another_good_callback")
        
        scanner.add_callback(good_callback)
        scanner.add_callback(error_callback)
        scanner.add_callback(another_good_callback)
        
        # Create test sensor data
        sensor_data = RuuviSensorData(
            mac_address="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.utcnow(),
            data_format=RuuviDataFormat.FORMAT_5,
            temperature=20.0
        )
        
        # Notify callbacks
        scanner._notify_callbacks(sensor_data)
        
        # Good callbacks should have been called despite error in one
        assert "good_callback" in self.callback_results
        assert "another_good_callback" in self.callback_results


class TestDataValidationIntegration:
    """Test data validation in the complete workflow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0
        self.mock_config.ble_retry_attempts = 1
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
        
        self.validated_devices = []
    
    def validation_callback(self, sensor_data: RuuviSensorData):
        """Callback that validates sensor data."""
        # Perform validation checks
        validation_results = {
            'mac_address': sensor_data.mac_address,
            'valid_temperature': (
                sensor_data.temperature is None or 
                -40 <= sensor_data.temperature <= 85
            ),
            'valid_humidity': (
                sensor_data.humidity is None or 
                0 <= sensor_data.humidity <= 100
            ),
            'valid_pressure': (
                sensor_data.pressure is None or 
                300 <= sensor_data.pressure <= 1100
            ),
            'valid_battery': (
                sensor_data.battery_voltage is None or 
                1.0 <= sensor_data.battery_voltage <= 4.0
            ),
            'has_timestamp': sensor_data.timestamp is not None,
            'has_format': sensor_data.data_format is not None
        }
        
        self.validated_devices.append(validation_results)
    
    @pytest.mark.asyncio
    async def test_end_to_end_data_validation(self, monkeypatch):
        """Test complete data validation workflow."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        scanner.add_callback(self.validation_callback)
        
        # Perform scan
        devices = await scanner.scan_once(duration=0.5)
        
        # Validate that all discovered devices passed validation
        assert len(self.validated_devices) > 0
        
        for validation in self.validated_devices:
            assert validation['valid_temperature'], f"Invalid temperature for {validation['mac_address']}"
            assert validation['valid_humidity'], f"Invalid humidity for {validation['mac_address']}"
            assert validation['valid_pressure'], f"Invalid pressure for {validation['mac_address']}"
            assert validation['valid_battery'], f"Invalid battery for {validation['mac_address']}"
            assert validation['has_timestamp'], f"Missing timestamp for {validation['mac_address']}"
            assert validation['has_format'], f"Missing format for {validation['mac_address']}"


class TestPerformanceMonitoring:
    """Test performance monitoring integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0
        self.mock_config.ble_retry_attempts = 1
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_performance_metrics_recording(self, monkeypatch):
        """Test that performance metrics are recorded during scanning."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Perform scan
        await scanner.scan_once(duration=0.5)
        
        # Verify performance monitoring calls
        self.mock_performance_monitor.measure_time.assert_called_with("ble_scan_duration")
        self.mock_performance_monitor.record_metric.assert_called()
        
        # Check specific metrics
        metric_calls = self.mock_performance_monitor.record_metric.call_args_list
        metric_names = [call[0][0] for call in metric_calls]
        
        assert "ble_scans_completed" in metric_names
        assert "ble_sensors_found" in metric_names
    
    @pytest.mark.asyncio
    async def test_error_metrics_recording(self, monkeypatch):
        """Test that error metrics are recorded on failures."""
        patch_bleak_scanner(monkeypatch, MockBleakScannerFactory.create_failing_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Attempt scan (should fail)
        try:
            await scanner.scan_once(duration=0.1)
        except Exception:
            pass  # Expected to fail
        
        # Verify error metrics were recorded
        metric_calls = self.mock_performance_monitor.record_metric.call_args_list
        metric_names = [call[0][0] for call in metric_calls]
        
        assert "ble_scan_errors" in metric_names


class TestStatisticsIntegration:
    """Test statistics tracking integration."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 0.5
        self.mock_config.ble_retry_attempts = 1
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_statistics_tracking_during_scans(self, monkeypatch):
        """Test that statistics are properly tracked during scans."""
        patch_bleak_scanner(monkeypatch, MockBleakScanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Get initial statistics
        initial_stats = scanner.get_statistics()
        
        # Perform multiple scans
        await scanner.scan_once(duration=0.2)
        await scanner.scan_once(duration=0.2)
        
        # Get final statistics
        final_stats = scanner.get_statistics()
        
        # Verify statistics were updated
        assert final_stats['scan_count'] > initial_stats['scan_count']
        assert final_stats['device_count'] >= initial_stats['device_count']
        assert final_stats['last_scan_time'] is not None
        if initial_stats['last_scan_time'] is not None:
            assert final_stats['last_scan_time'] > initial_stats['last_scan_time']
    
    def test_statistics_structure(self):
        """Test that statistics contain all expected fields."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        stats = scanner.get_statistics()
        
        expected_fields = [
            'scan_count', 'device_count', 'error_count',
            'last_scan_time', 'is_scanning', 'discovered_devices',
            'callbacks_registered'
        ]
        
        for field in expected_fields:
            assert field in stats, f"Missing statistics field: {field}"


class TestErrorRecoveryIntegration:
    """Test error recovery in integrated scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 0.5
        self.mock_config.ble_retry_attempts = 2
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        from unittest.mock import MagicMock
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_recovery_after_scan_failure(self, monkeypatch):
        """Test recovery after scan failure."""
        # Create a scanner that fails initially but then works
        call_count = 0
        
        def create_unreliable_scanner(detection_callback=None, adapter=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockBleakScannerFactory.create_failing_scanner(detection_callback, adapter)
            else:
                return MockBleakScanner(detection_callback, adapter)
        
        patch_bleak_scanner(monkeypatch, create_unreliable_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # First scan should fail
        try:
            await scanner.scan_once(duration=0.1)
            assert False, "Expected scan to fail"
        except Exception:
            pass  # Expected
        
        # Second scan should succeed (new scanner instance)
        devices = await scanner.scan_once(duration=0.1)
        # Should not raise exception and may find devices
        assert isinstance(devices, dict)
    
    @pytest.mark.asyncio
    async def test_cleanup_after_errors(self, monkeypatch):
        """Test that cleanup works properly after errors."""
        patch_bleak_scanner(monkeypatch, MockBleakScannerFactory.create_failing_scanner)
        
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Attempt operations that will fail
        try:
            await scanner.scan_once(duration=0.1)
        except Exception:
            pass
        
        try:
            await scanner.start_continuous_scan()
            await asyncio.sleep(0.1)
        except Exception:
            pass
        
        # Cleanup should work without errors
        await scanner.cleanup()
        
        # Scanner should be in clean state
        assert not scanner.is_scanning()
        assert len(scanner.get_discovered_devices()) == 0