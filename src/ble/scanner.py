"""
Bluetooth Low Energy scanner for Ruuvi sensors.
Handles async BLE scanning, device discovery, and data parsing with error handling and retry logic.
"""

import asyncio
import struct
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

import bleak
from bleak import BleakScanner, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ..utils.config import Config
from ..utils.logging import ProductionLogger, PerformanceMonitor


class RuuviDataFormat(Enum):
    """Ruuvi data format versions."""
    FORMAT_3 = 3
    FORMAT_5 = 5
    UNKNOWN = -1


@dataclass
class RuuviSensorData:
    """Parsed Ruuvi sensor data."""
    mac_address: str
    timestamp: datetime
    data_format: RuuviDataFormat
    temperature: Optional[float] = None  # Celsius
    humidity: Optional[float] = None     # %RH
    pressure: Optional[float] = None     # hPa
    acceleration_x: Optional[float] = None  # g
    acceleration_y: Optional[float] = None  # g
    acceleration_z: Optional[float] = None  # g
    battery_voltage: Optional[float] = None  # V
    tx_power: Optional[int] = None       # dBm
    movement_counter: Optional[int] = None
    measurement_sequence: Optional[int] = None
    rssi: Optional[int] = None           # dBm
    raw_data: Optional[bytes] = None


class ScannerError(Exception):
    """Base exception for scanner operations."""
    pass


class ScannerInitError(ScannerError):
    """Exception for scanner initialization errors."""
    pass


class ScannerOperationError(ScannerError):
    """Exception for scanner operation errors."""
    pass


class RuuviBLEScanner:
    """
    Async BLE scanner for Ruuvi sensors with comprehensive error handling and retry logic.
    
    Features:
    - Async/await based scanning
    - Ruuvi data format parsing (v3 and v5)
    - Error handling and retry logic
    - Performance monitoring
    - Configurable scan parameters
    - Device filtering and validation
    """
    
    # Ruuvi manufacturer ID
    RUUVI_MANUFACTURER_ID = 0x0499
    
    def __init__(self, config: Config, logger: ProductionLogger, performance_monitor: PerformanceMonitor):
        """
        Initialize BLE scanner.
        
        Args:
            config: Application configuration
            logger: Logger instance
            performance_monitor: Performance monitoring instance
        """
        self.config = config
        self.logger = logger
        self.performance_monitor = performance_monitor
        
        # Scanner configuration
        self.scan_duration = config.ble_scan_duration
        self.scan_interval = config.ble_scan_interval
        self.retry_attempts = config.ble_retry_attempts
        self.retry_delay = config.ble_retry_delay
        self.adapter = config.ble_adapter
        
        # State management
        self._scanner: Optional[BleakScanner] = None
        self._is_scanning = False
        self._scan_task: Optional[asyncio.Task] = None
        self._discovered_devices: Dict[str, RuuviSensorData] = {}
        self._callbacks: List[Callable[[RuuviSensorData], None]] = []
        
        # Statistics
        self._scan_count = 0
        self._device_count = 0
        self._error_count = 0
        self._last_scan_time: Optional[datetime] = None
        
        self.logger.info(f"RuuviBLEScanner initialized with adapter: {self.adapter}")
    
    def add_callback(self, callback: Callable[[RuuviSensorData], None]):
        """
        Add callback for sensor data events.
        
        Args:
            callback: Function to call when sensor data is received
        """
        self._callbacks.append(callback)
        self.logger.debug(f"Added callback: {callback.__name__}")
    
    def remove_callback(self, callback: Callable[[RuuviSensorData], None]):
        """
        Remove callback for sensor data events.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            self.logger.debug(f"Removed callback: {callback.__name__}")
    
    def _notify_callbacks(self, sensor_data: RuuviSensorData):
        """
        Notify all registered callbacks with sensor data.
        
        Args:
            sensor_data: Parsed sensor data
        """
        for callback in self._callbacks:
            try:
                callback(sensor_data)
            except Exception as e:
                self.logger.error(f"Error in callback {callback.__name__}: {e}")
    
    def _parse_manufacturer_data(self, manufacturer_data: Dict[int, bytes]) -> Optional[RuuviSensorData]:
        """
        Parse manufacturer data for Ruuvi sensors.
        
        Args:
            manufacturer_data: Manufacturer data from BLE advertisement
            
        Returns:
            Optional[RuuviSensorData]: Parsed sensor data or None if not Ruuvi
        """
        if self.RUUVI_MANUFACTURER_ID not in manufacturer_data:
            return None
        
        data = manufacturer_data[self.RUUVI_MANUFACTURER_ID]
        
        if len(data) < 1:
            return None
        
        data_format = data[0]
        
        if data_format == 3:
            return self._parse_format_3(data)
        elif data_format == 5:
            return self._parse_format_5(data)
        else:
            self.logger.debug(f"Unknown Ruuvi data format: {data_format}")
            return None
    
    def _parse_format_3(self, data: bytes) -> Optional[RuuviSensorData]:
        """
        Parse Ruuvi data format 3.
        
        Args:
            data: Raw manufacturer data
            
        Returns:
            Optional[RuuviSensorData]: Parsed sensor data
        """
        if len(data) < 14:
            return None
        
        try:
            # Format 3: humidity (1 byte), temperature (1 byte, signed), 
            # temperature fraction (1 byte), pressure (2 bytes), 
            # acceleration X,Y,Z (2 bytes each), battery voltage (2 bytes)
            
            humidity = data[1] / 2.0  # 0.5% resolution
            temp_int = struct.unpack('b', data[2:3])[0]  # signed byte
            temp_frac = data[3] / 100.0
            temperature = temp_int + temp_frac
            
            pressure = struct.unpack('>H', data[4:6])[0] + 50000  # Pa, add offset
            pressure = pressure / 100.0  # Convert to hPa
            
            acc_x = struct.unpack('>h', data[6:8])[0] / 1000.0  # mg to g
            acc_y = struct.unpack('>h', data[8:10])[0] / 1000.0
            acc_z = struct.unpack('>h', data[10:12])[0] / 1000.0
            
            battery_voltage = struct.unpack('>H', data[12:14])[0] / 1000.0  # mV to V
            
            return RuuviSensorData(
                mac_address="",  # Will be set by caller
                timestamp=datetime.utcnow(),
                data_format=RuuviDataFormat.FORMAT_3,
                temperature=temperature,
                humidity=humidity,
                pressure=pressure,
                acceleration_x=acc_x,
                acceleration_y=acc_y,
                acceleration_z=acc_z,
                battery_voltage=battery_voltage,
                raw_data=data
            )
            
        except (struct.error, IndexError) as e:
            self.logger.warning(f"Failed to parse format 3 data: {e}")
            return None
    
    def _parse_format_5(self, data: bytes) -> Optional[RuuviSensorData]:
        """
        Parse Ruuvi data format 5.
        
        Args:
            data: Raw manufacturer data
            
        Returns:
            Optional[RuuviSensorData]: Parsed sensor data
        """
        if len(data) < 24:
            return None
        
        try:
            # Format 5: temperature (2 bytes), humidity (2 bytes), pressure (2 bytes),
            # acceleration X,Y,Z (2 bytes each), power info (2 bytes),
            # movement counter (1 byte), measurement sequence (2 bytes), MAC (6 bytes)
            
            temperature = struct.unpack('>h', data[1:3])[0] * 0.005  # 0.005°C resolution
            humidity = struct.unpack('>H', data[3:5])[0] * 0.0025   # 0.0025%RH resolution
            pressure = struct.unpack('>H', data[5:7])[0] + 50000    # Pa, add offset
            pressure = pressure / 100.0  # Convert to hPa
            
            acc_x = struct.unpack('>h', data[7:9])[0] / 1000.0      # mg to g
            acc_y = struct.unpack('>h', data[9:11])[0] / 1000.0
            acc_z = struct.unpack('>h', data[11:13])[0] / 1000.0
            
            # Power info: 11 bits battery voltage + 5 bits TX power
            power_info = struct.unpack('>H', data[13:15])[0]
            battery_voltage = ((power_info >> 5) + 1600) / 1000.0   # mV to V
            tx_power = (power_info & 0x1F) * 2 - 40                 # dBm
            
            movement_counter = data[15]
            measurement_sequence = struct.unpack('>H', data[16:18])[0]
            
            # MAC address (last 6 bytes)
            mac_bytes = data[18:24]
            mac_address = ':'.join(f'{b:02X}' for b in mac_bytes)
            
            return RuuviSensorData(
                mac_address=mac_address,
                timestamp=datetime.utcnow(),
                data_format=RuuviDataFormat.FORMAT_5,
                temperature=temperature,
                humidity=humidity,
                pressure=pressure,
                acceleration_x=acc_x,
                acceleration_y=acc_y,
                acceleration_z=acc_z,
                battery_voltage=battery_voltage,
                tx_power=tx_power,
                movement_counter=movement_counter,
                measurement_sequence=measurement_sequence,
                raw_data=data
            )
            
        except (struct.error, IndexError) as e:
            self.logger.warning(f"Failed to parse format 5 data: {e}")
            return None
    
    def _detection_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """
        Callback for BLE device detection.
        
        Args:
            device: Detected BLE device
            advertisement_data: Advertisement data
        """
        try:
            # Parse manufacturer data
            sensor_data = self._parse_manufacturer_data(advertisement_data.manufacturer_data)
            
            if sensor_data is None:
                return
            
            # Set MAC address and RSSI
            sensor_data.mac_address = device.address.upper()
            sensor_data.rssi = advertisement_data.rssi
            
            # Update discovered devices
            self._discovered_devices[sensor_data.mac_address] = sensor_data
            self._device_count += 1
            
            # Log discovery
            self.logger.debug(
                f"Discovered Ruuvi sensor: {sensor_data.mac_address} "
                f"(Format {sensor_data.data_format.value}, RSSI: {sensor_data.rssi}dBm, "
                f"Temp: {sensor_data.temperature}°C, Humidity: {sensor_data.humidity}%)"
            )
            
            # Notify callbacks
            self._notify_callbacks(sensor_data)
            
            # Update performance metrics
            self.performance_monitor.record_metric("ble_devices_discovered", 1)
            
        except Exception as e:
            self.logger.error(f"Error processing BLE device {device.address}: {e}")
            self._error_count += 1
            self.performance_monitor.record_metric("ble_scan_errors", 1)
    
    async def _initialize_scanner(self) -> BleakScanner:
        """
        Initialize BLE scanner with retry logic.
        
        Returns:
            BleakScanner: Initialized scanner
            
        Raises:
            ScannerInitError: If scanner initialization fails
        """
        for attempt in range(self.retry_attempts):
            try:
                scanner = BleakScanner(
                    detection_callback=self._detection_callback,
                    adapter=self.adapter if self.adapter != "auto" else None
                )
                
                # Test scanner availability
                await scanner.start()
                await asyncio.sleep(0.1)
                await scanner.stop()
                
                self.logger.debug(f"BLE scanner initialized successfully (attempt {attempt + 1})")
                return scanner
                
            except Exception as e:
                self.logger.warning(f"Scanner init attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise ScannerInitError(f"Failed to initialize scanner after {self.retry_attempts} attempts: {e}")
    
    async def scan_once(self, duration: Optional[float] = None) -> Dict[str, RuuviSensorData]:
        """
        Perform a single BLE scan for Ruuvi sensors.
        
        Args:
            duration: Scan duration in seconds (uses config default if None)
            
        Returns:
            Dict[str, RuuviSensorData]: Discovered sensors by MAC address
            
        Raises:
            ScannerOperationError: If scan operation fails
        """
        scan_duration = duration or self.scan_duration
        
        with self.performance_monitor.measure_time("ble_scan_duration"):
            try:
                # Clear previous results
                self._discovered_devices.clear()
                
                # Initialize scanner if needed
                if self._scanner is None:
                    self._scanner = await self._initialize_scanner()
                
                self.logger.info(f"Starting BLE scan for {scan_duration} seconds...")
                
                # Start scanning
                await self._scanner.start()
                self._is_scanning = True
                self._last_scan_time = datetime.utcnow()
                
                # Wait for scan duration
                await asyncio.sleep(scan_duration)
                
                # Stop scanning
                await self._scanner.stop()
                self._is_scanning = False
                
                self._scan_count += 1
                
                self.logger.info(
                    f"BLE scan completed. Found {len(self._discovered_devices)} Ruuvi sensors"
                )
                
                # Update performance metrics
                self.performance_monitor.record_metric("ble_scans_completed", 1)
                self.performance_monitor.record_metric("ble_sensors_found", len(self._discovered_devices))
                
                return self._discovered_devices.copy()
                
            except Exception as e:
                self._error_count += 1
                self.performance_monitor.record_metric("ble_scan_errors", 1)
                self.logger.error(f"BLE scan failed: {e}")
                
                # Try to stop scanner if it's running
                if self._is_scanning and self._scanner:
                    try:
                        await self._scanner.stop()
                    except:
                        pass
                    self._is_scanning = False
                
                raise ScannerOperationError(f"BLE scan failed: {e}")
    
    async def start_continuous_scan(self):
        """
        Start continuous BLE scanning with configured interval.
        
        Raises:
            ScannerOperationError: If continuous scan fails to start
        """
        if self._scan_task and not self._scan_task.done():
            self.logger.warning("Continuous scan already running")
            return
        
        self.logger.info(f"Starting continuous BLE scan (interval: {self.scan_interval}s)")
        self._scan_task = asyncio.create_task(self._continuous_scan_loop())
    
    async def stop_continuous_scan(self):
        """Stop continuous BLE scanning."""
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
            self.logger.info("Continuous BLE scan stopped")
        
        # Stop current scan if running
        if self._is_scanning and self._scanner:
            try:
                await self._scanner.stop()
                self._is_scanning = False
            except Exception as e:
                self.logger.warning(f"Error stopping scanner: {e}")
    
    async def _continuous_scan_loop(self):
        """Continuous scanning loop."""
        try:
            while True:
                try:
                    await self.scan_once()
                    await asyncio.sleep(self.scan_interval)
                    
                except ScannerOperationError as e:
                    self.logger.error(f"Scan error in continuous mode: {e}")
                    await asyncio.sleep(self.retry_delay)
                    
                except asyncio.CancelledError:
                    break
                    
                except Exception as e:
                    self.logger.error(f"Unexpected error in continuous scan: {e}")
                    await asyncio.sleep(self.retry_delay)
                    
        except asyncio.CancelledError:
            self.logger.debug("Continuous scan loop cancelled")
        finally:
            if self._is_scanning and self._scanner:
                try:
                    await self._scanner.stop()
                    self._is_scanning = False
                except:
                    pass
    
    def is_scanning(self) -> bool:
        """
        Check if scanner is currently scanning.
        
        Returns:
            bool: True if scanning is active
        """
        return self._is_scanning
    
    def get_discovered_devices(self) -> Dict[str, RuuviSensorData]:
        """
        Get currently discovered devices.
        
        Returns:
            Dict[str, RuuviSensorData]: Discovered devices by MAC address
        """
        return self._discovered_devices.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get scanner statistics.
        
        Returns:
            Dict[str, Any]: Scanner statistics
        """
        return {
            "scan_count": self._scan_count,
            "device_count": self._device_count,
            "error_count": self._error_count,
            "last_scan_time": self._last_scan_time,
            "is_scanning": self._is_scanning,
            "discovered_devices": len(self._discovered_devices),
            "callbacks_registered": len(self._callbacks)
        }
    
    def reset_statistics(self):
        """Reset scanner statistics."""
        self._scan_count = 0
        self._device_count = 0
        self._error_count = 0
        self._last_scan_time = None
        self.logger.debug("Scanner statistics reset")
    
    async def cleanup(self):
        """Cleanup scanner resources."""
        await self.stop_continuous_scan()
        
        if self._scanner:
            try:
                if self._is_scanning:
                    await self._scanner.stop()
            except:
                pass
            self._scanner = None
        
        self._callbacks.clear()
        self._discovered_devices.clear()
        
        self.logger.info("BLE scanner cleanup completed")


async def test_scanner(config: Config, logger: ProductionLogger, performance_monitor: PerformanceMonitor):
    """
    Test function for BLE scanner.
    
    Args:
        config: Application configuration
        logger: Logger instance
        performance_monitor: Performance monitor instance
    """
    scanner = RuuviBLEScanner(config, logger, performance_monitor)
    
    def data_callback(sensor_data: RuuviSensorData):
        print(f"Sensor: {sensor_data.mac_address}")
        print(f"  Temperature: {sensor_data.temperature}°C")
        print(f"  Humidity: {sensor_data.humidity}%")
        print(f"  Pressure: {sensor_data.pressure} hPa")
        print(f"  Battery: {sensor_data.battery_voltage}V")
        print(f"  RSSI: {sensor_data.rssi}dBm")
        print()
    
    scanner.add_callback(data_callback)
    
    try:
        # Single scan test
        devices = await scanner.scan_once(10)
        print(f"Found {len(devices)} devices")
        
        # Print statistics
        stats = scanner.get_statistics()
        print(f"Statistics: {stats}")
        
    finally:
        await scanner.cleanup()


if __name__ == "__main__":
    # Simple test when run directly
    import sys
    sys.path.append(str(Path(__file__).parent.parent.parent))
    
    from src.utils.config import Config
    from src.utils.logging import ProductionLogger, PerformanceMonitor
    
    config = Config()
    logger = ProductionLogger(config)
    performance_monitor = PerformanceMonitor(logger)
    
    asyncio.run(test_scanner(config, logger, performance_monitor))