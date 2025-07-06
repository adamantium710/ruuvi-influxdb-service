"""
Unit tests for error scenarios in Ruuvi sensor scanning.
Tests error handling, edge cases, and failure recovery.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from src.ble.scanner import (
    RuuviBLEScanner, 
    ScannerError, 
    ScannerInitError, 
    ScannerOperationError,
    RuuviSensorData,
    RuuviDataFormat
)
from tests.mocks.mock_ble_scanner import MockBleakScannerFactory


class TestBLEAdapterErrors:
    """Test BLE adapter initialization and operation errors."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 5.0
        self.mock_config.ble_scan_interval = 10
        self.mock_config.ble_retry_attempts = 3
        self.mock_config.ble_retry_delay = 1.0
        self.mock_config.ble_adapter = "hci0"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager for measure_time
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_scanner_init_failure(self):
        """Test scanner initialization failure."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Mock BleakScanner to always fail initialization
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.side_effect = Exception("Bluetooth adapter not found")
            mock_scanner_class.return_value = mock_scanner
            
            with pytest.raises(ScannerInitError):
                await scanner._initialize_scanner()
            
            # Verify retry attempts were made
            assert mock_scanner.start.call_count == self.mock_config.ble_retry_attempts
    
    @pytest.mark.asyncio
    async def test_scanner_init_retry_success(self):
        """Test scanner initialization success after retries."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            # Fail first two attempts, succeed on third
            mock_scanner.start.side_effect = [
                Exception("First failure"),
                Exception("Second failure"),
                None  # Success
            ]
            mock_scanner_class.return_value = mock_scanner
            
            result = await scanner._initialize_scanner()
            
            assert result is not None
            assert mock_scanner.start.call_count == 3
    
    @pytest.mark.asyncio
    async def test_scan_operation_failure(self):
        """Test scan operation failure during scanning."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.side_effect = Exception("Scan failed")
            mock_scanner_class.return_value = mock_scanner
            
            with pytest.raises(ScannerOperationError):
                await scanner.scan_once()
    
    @pytest.mark.asyncio
    async def test_scan_stop_failure_handling(self):
        """Test handling of scanner stop failures."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.return_value = None
            mock_scanner.stop.side_effect = Exception("Stop failed")
            mock_scanner_class.return_value = mock_scanner
            
            # Should not raise exception even if stop fails
            try:
                await scanner.scan_once(duration=0.1)
            except ScannerOperationError:
                pass  # Expected due to stop failure
            
            # Scanner should handle stop failure gracefully
            assert not scanner.is_scanning()


class TestPermissionErrors:
    """Test permission denied scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 5.0
        self.mock_config.ble_retry_attempts = 2
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "hci0"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_permission_denied_error(self):
        """Test handling of permission denied errors."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.side_effect = PermissionError("Permission denied")
            mock_scanner_class.return_value = mock_scanner
            
            with pytest.raises(ScannerInitError) as exc_info:
                await scanner._initialize_scanner()
            
            assert "Permission denied" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_bluetooth_not_available_error(self):
        """Test handling when Bluetooth is not available."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner_class.side_effect = ImportError("No Bluetooth adapter found")
            
            with pytest.raises(ScannerInitError):
                await scanner._initialize_scanner()


class TestMalformedDataHandling:
    """Test handling of malformed advertisement data."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        self.scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
    
    def test_callback_exception_handling(self):
        """Test that exceptions in detection callback are handled."""
        # Create mock device and advertisement data
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        
        mock_ad_data = Mock()
        mock_ad_data.manufacturer_data = {}  # Empty data
        mock_ad_data.rssi = -65
        
        # This should not raise an exception
        self.scanner._detection_callback(mock_device, mock_ad_data)
        
        # Error should be logged but not propagated
        assert self.mock_logger.error.call_count == 0  # No error for empty data
    
    def test_invalid_manufacturer_data_structure(self):
        """Test handling of invalid manufacturer data structures."""
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        
        # Test with None manufacturer_data
        mock_ad_data = Mock()
        mock_ad_data.manufacturer_data = None
        mock_ad_data.rssi = -65
        
        # Should handle gracefully
        try:
            self.scanner._detection_callback(mock_device, mock_ad_data)
        except Exception as e:
            pytest.fail(f"Should handle None manufacturer_data gracefully: {e}")
    
    def test_corrupted_ruuvi_data(self):
        """Test handling of corrupted Ruuvi manufacturer data."""
        corrupted_data_samples = [
            bytes([3]),  # Format 3 with only format byte
            bytes([5, 0x00]),  # Format 5 with insufficient data
            bytes([3] + [0xFF] * 5),  # Format 3 with partial data
            bytes([99] + [0x00] * 23),  # Unknown format
            bytes([]),  # Empty data
        ]
        
        for corrupted_data in corrupted_data_samples:
            manufacturer_data = {0x0499: corrupted_data}
            
            result = self.scanner._parse_manufacturer_data(manufacturer_data)
            assert result is None, f"Should reject corrupted data: {corrupted_data.hex()}"


class TestTimeoutHandling:
    """Test timeout scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0  # Short duration for tests
        self.mock_config.ble_retry_attempts = 2
        self.mock_config.ble_retry_delay = 0.1
        self.mock_config.ble_adapter = "auto"
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_scan_timeout_handling(self):
        """Test that scan respects timeout duration."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.return_value = None
            mock_scanner.stop.return_value = None
            mock_scanner_class.return_value = mock_scanner
            
            start_time = asyncio.get_event_loop().time()
            await scanner.scan_once(duration=0.5)
            end_time = asyncio.get_event_loop().time()
            
            # Should complete in approximately the specified duration
            assert 0.4 <= (end_time - start_time) <= 1.0
    
    @pytest.mark.asyncio
    async def test_continuous_scan_cancellation(self):
        """Test that continuous scan can be cancelled."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.return_value = None
            mock_scanner.stop.return_value = None
            mock_scanner_class.return_value = mock_scanner
            
            # Start continuous scan
            await scanner.start_continuous_scan()
            
            # Let it run briefly
            await asyncio.sleep(0.1)
            
            # Stop should complete quickly
            start_time = asyncio.get_event_loop().time()
            await scanner.stop_continuous_scan()
            end_time = asyncio.get_event_loop().time()
            
            assert (end_time - start_time) < 1.0  # Should stop quickly


class TestCallbackErrors:
    """Test error handling in callback functions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        self.scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
    
    def test_callback_exception_isolation(self):
        """Test that exceptions in one callback don't affect others."""
        # Add multiple callbacks, one that raises an exception
        callback_results = []
        
        def good_callback1(data):
            callback_results.append("good1")
        
        def bad_callback(data):
            raise ValueError("Callback error")
        
        def good_callback2(data):
            callback_results.append("good2")
        
        self.scanner.add_callback(good_callback1)
        self.scanner.add_callback(bad_callback)
        self.scanner.add_callback(good_callback2)
        
        # Create valid sensor data
        sensor_data = RuuviSensorData(
            mac_address="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.utcnow(),
            data_format=RuuviDataFormat.FORMAT_5,
            temperature=20.0
        )
        
        # Notify callbacks - should not raise exception
        self.scanner._notify_callbacks(sensor_data)
        
        # Good callbacks should have been called
        assert "good1" in callback_results
        assert "good2" in callback_results
        
        # Error should have been logged
        self.mock_logger.error.assert_called()
    
    def test_callback_removal(self):
        """Test callback removal functionality."""
        callback_called = False
        
        def test_callback(data):
            nonlocal callback_called
            callback_called = True
        
        # Add and then remove callback
        self.scanner.add_callback(test_callback)
        self.scanner.remove_callback(test_callback)
        
        # Create sensor data
        sensor_data = RuuviSensorData(
            mac_address="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.utcnow(),
            data_format=RuuviDataFormat.FORMAT_5
        )
        
        # Notify callbacks
        self.scanner._notify_callbacks(sensor_data)
        
        # Callback should not have been called
        assert not callback_called


class TestResourceCleanup:
    """Test proper resource cleanup in error scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0
        self.mock_config.ble_retry_attempts = 1
        self.mock_config.ble_retry_delay = 0.1
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        # Mock the context manager
        mock_context = MagicMock()
        mock_context.__enter__ = Mock(return_value=mock_context)
        mock_context.__exit__ = Mock(return_value=None)
        self.mock_performance_monitor.measure_time.return_value = mock_context
    
    @pytest.mark.asyncio
    async def test_cleanup_after_scan_failure(self):
        """Test that resources are cleaned up after scan failure."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.start.side_effect = Exception("Scan failed")
            mock_scanner.stop.return_value = None
            mock_scanner_class.return_value = mock_scanner
            
            try:
                await scanner.scan_once()
            except ScannerOperationError:
                pass  # Expected
            
            # Scanner should not be in scanning state
            assert not scanner.is_scanning()
    
    @pytest.mark.asyncio
    async def test_cleanup_method(self):
        """Test the cleanup method."""
        scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
        
        # Add some callbacks and discovered devices
        scanner.add_callback(lambda x: None)
        scanner._discovered_devices["test"] = Mock()
        
        with patch('src.ble.scanner.BleakScanner') as mock_scanner_class:
            mock_scanner = AsyncMock()
            mock_scanner.stop.return_value = None
            mock_scanner_class.return_value = mock_scanner
            scanner._scanner = mock_scanner
            scanner._is_scanning = True
            
            await scanner.cleanup()
            
            # Should have stopped scanner
            mock_scanner.stop.assert_called()
            
            # Should have cleared state
            assert len(scanner._callbacks) == 0
            assert len(scanner._discovered_devices) == 0
            assert scanner._scanner is None


class TestStatisticsAndMonitoring:
    """Test statistics and monitoring in error scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        self.scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
    
    def test_error_count_tracking(self):
        """Test that error counts are properly tracked."""
        initial_stats = self.scanner.get_statistics()
        initial_error_count = initial_stats['error_count']
        
        # Simulate detection callback error
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        
        mock_ad_data = Mock()
        mock_ad_data.manufacturer_data = {0x0499: bytes([99])}  # Invalid format
        mock_ad_data.rssi = -65
        
        # This should increment error count
        self.scanner._detection_callback(mock_device, mock_ad_data)
        
        # Error count should not increase for invalid format (it's handled gracefully)
        # But let's test with actual error scenario
        
        # Force an exception in the callback
        with patch.object(self.scanner, '_parse_manufacturer_data', side_effect=Exception("Test error")):
            self.scanner._detection_callback(mock_device, mock_ad_data)
        
        final_stats = self.scanner.get_statistics()
        assert final_stats['error_count'] > initial_error_count
    
    def test_statistics_reset(self):
        """Test statistics reset functionality."""
        # Set some statistics
        self.scanner._scan_count = 5
        self.scanner._device_count = 10
        self.scanner._error_count = 2
        
        self.scanner.reset_statistics()
        
        stats = self.scanner.get_statistics()
        assert stats['scan_count'] == 0
        assert stats['device_count'] == 0
        assert stats['error_count'] == 0
        assert stats['last_scan_time'] is None


class TestEdgeCaseScenarios:
    """Test various edge case scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock()
        self.mock_config.ble_scan_duration = 1.0
        self.mock_config.ble_retry_attempts = 1
        
        self.mock_logger = Mock()
        self.mock_performance_monitor = Mock()
        
        self.scanner = RuuviBLEScanner(
            self.mock_config,
            self.mock_logger,
            self.mock_performance_monitor
        )
    
    def test_duplicate_device_handling(self):
        """Test handling of duplicate device discoveries."""
        # Create mock device and advertisement data
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        
        # Valid Format 5 data
        valid_data = bytes([5] + [0] * 23)
        mock_ad_data = Mock()
        mock_ad_data.manufacturer_data = {0x0499: valid_data}
        mock_ad_data.rssi = -65
        
        # Simulate multiple discoveries of the same device
        self.scanner._detection_callback(mock_device, mock_ad_data)
        initial_count = len(self.scanner._discovered_devices)
        
        self.scanner._detection_callback(mock_device, mock_ad_data)
        final_count = len(self.scanner._discovered_devices)
        
        # Should still have only one device (updated, not duplicated)
        assert initial_count == final_count == 1
        assert "AA:BB:CC:DD:EE:FF" in self.scanner._discovered_devices
    
    def test_empty_scan_results(self):
        """Test handling of scans that find no devices."""
        devices = self.scanner.get_discovered_devices()
        assert len(devices) == 0
        
        stats = self.scanner.get_statistics()
        assert stats['discovered_devices'] == 0
    
    def test_very_weak_signal_handling(self):
        """Test handling of devices with very weak signals."""
        mock_device = Mock()
        mock_device.address = "AA:BB:CC:DD:EE:FF"
        
        valid_data = bytes([5] + [0] * 23)
        mock_ad_data = Mock()
        mock_ad_data.manufacturer_data = {0x0499: valid_data}
        mock_ad_data.rssi = -120  # Very weak signal
        
        self.scanner._detection_callback(mock_device, mock_ad_data)
        
        devices = self.scanner.get_discovered_devices()
        assert len(devices) == 1
        assert devices["AA:BB:CC:DD:EE:FF"].rssi == -120