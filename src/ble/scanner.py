"""
Bluetooth Low Energy scanner for Ruuvi sensors.
Handles async BLE scanning, device discovery, and data parsing with error handling and retry logic.
Includes comprehensive historical data retrieval system with GATT protocol implementation.
"""

import asyncio
import struct
import time
from typing import Dict, List, Optional, Callable, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

import bleak
from bleak import BleakScanner, BleakClient, BleakError
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


# Historical Data Retrieval System Components

class RuuviCommandType(Enum):
    """Ruuvi GATT command types."""
    GET_DEVICE_INFO = 0x01
    GET_HISTORICAL_DATA = 0x02
    SET_TIME = 0x03
    GET_CAPABILITIES = 0x04
    ACKNOWLEDGE_CHUNK = 0x05


class RuuviResponseStatus(Enum):
    """Ruuvi GATT response status codes."""
    SUCCESS = 0x00
    ERROR_INVALID_COMMAND = 0x01
    ERROR_INVALID_PARAMETER = 0x02
    ERROR_NOT_SUPPORTED = 0x03
    ERROR_BUSY = 0x04
    ERROR_TIMEOUT = 0x05


@dataclass
class RuuviCommand:
    """Ruuvi GATT command structure."""
    command_type: RuuviCommandType
    sequence_id: int
    parameters: bytes = field(default_factory=bytes)
    
    def to_bytes(self) -> bytes:
        """Serialize command to binary format."""
        header = struct.pack('<BBH',
                           self.command_type.value,
                           self.sequence_id,
                           len(self.parameters))
        return header + self.parameters
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RuuviCommand':
        """Deserialize command from binary format."""
        if len(data) < 4:
            raise ValueError("Invalid command data length")
        
        cmd_type, seq_id, param_len = struct.unpack('<BBH', data[:4])
        parameters = data[4:4+param_len] if param_len > 0 else bytes()
        
        return cls(
            command_type=RuuviCommandType(cmd_type),
            sequence_id=seq_id,
            parameters=parameters
        )


@dataclass
class RuuviResponse:
    """Ruuvi GATT response structure."""
    command_type: RuuviCommandType
    sequence_id: int
    status: RuuviResponseStatus
    data: bytes = field(default_factory=bytes)
    
    def to_bytes(self) -> bytes:
        """Serialize response to binary format."""
        header = struct.pack('<BBBH',
                           self.command_type.value,
                           self.sequence_id,
                           self.status.value,
                           len(self.data))
        return header + self.data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'RuuviResponse':
        """Deserialize response from binary format."""
        if len(data) < 5:
            raise ValueError("Invalid response data length")
        
        cmd_type, seq_id, status, data_len = struct.unpack('<BBBH', data[:5])
        response_data = data[5:5+data_len] if data_len > 0 else bytes()
        
        return cls(
            command_type=RuuviCommandType(cmd_type),
            sequence_id=seq_id,
            status=RuuviResponseStatus(status),
            data=response_data
        )


@dataclass
class HistoricalDataRecord:
    """Historical sensor data record."""
    timestamp: datetime
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    acceleration_x: Optional[float] = None
    acceleration_y: Optional[float] = None
    acceleration_z: Optional[float] = None
    battery_voltage: Optional[float] = None
    tx_power: Optional[int] = None
    movement_counter: Optional[int] = None
    measurement_sequence: Optional[int] = None
    
    @classmethod
    def from_bytes(cls, data: bytes, base_timestamp: datetime) -> 'HistoricalDataRecord':
        """Parse historical record from binary format."""
        if len(data) < 16:
            raise ValueError("Invalid historical record data length")
        
        # Parse timestamp offset (4 bytes, seconds from base)
        timestamp_offset = struct.unpack('<I', data[:4])[0]
        record_timestamp = base_timestamp + timedelta(seconds=timestamp_offset)
        
        # Parse sensor data (similar to format 5 but compressed)
        temperature = struct.unpack('<h', data[4:6])[0] * 0.005
        humidity = struct.unpack('<H', data[6:8])[0] * 0.0025
        pressure = (struct.unpack('<H', data[8:10])[0] + 50000) / 100.0
        
        # Acceleration data (6 bytes)
        acc_x = struct.unpack('<h', data[10:12])[0] / 1000.0
        acc_y = struct.unpack('<h', data[12:14])[0] / 1000.0
        acc_z = struct.unpack('<h', data[14:16])[0] / 1000.0
        
        # Optional fields if data is longer
        battery_voltage = None
        tx_power = None
        movement_counter = None
        measurement_sequence = None
        
        if len(data) >= 20:
            power_info = struct.unpack('<H', data[16:18])[0]
            battery_voltage = ((power_info >> 5) + 1600) / 1000.0
            tx_power = (power_info & 0x1F) * 2 - 40
            
        if len(data) >= 22:
            movement_counter = struct.unpack('<H', data[18:20])[0]
            
        if len(data) >= 24:
            measurement_sequence = struct.unpack('<H', data[20:22])[0]
        
        return cls(
            timestamp=record_timestamp,
            temperature=temperature,
            humidity=humidity,
            pressure=pressure,
            acceleration_x=acc_x,
            acceleration_y=acc_y,
            acceleration_z=acc_z,
            battery_voltage=battery_voltage,
            tx_power=tx_power,
            movement_counter=movement_counter,
            measurement_sequence=measurement_sequence
        )
    
    def to_ruuvi_sensor_data(self, mac_address: str) -> RuuviSensorData:
        """Convert to RuuviSensorData format for compatibility."""
        return RuuviSensorData(
            mac_address=mac_address,
            timestamp=self.timestamp,
            data_format=RuuviDataFormat.FORMAT_5,  # Historical data uses format 5 structure
            temperature=self.temperature,
            humidity=self.humidity,
            pressure=self.pressure,
            acceleration_x=self.acceleration_x,
            acceleration_y=self.acceleration_y,
            acceleration_z=self.acceleration_z,
            battery_voltage=self.battery_voltage,
            tx_power=self.tx_power,
            movement_counter=self.movement_counter,
            measurement_sequence=self.measurement_sequence,
            rssi=None,  # Not available in historical data
            raw_data=None
        )


@dataclass
class DeviceCapabilities:
    """Ruuvi device capabilities."""
    supports_historical_data: bool = False
    max_historical_records: int = 0
    historical_data_interval: int = 0  # seconds
    firmware_version: str = ""
    hardware_version: str = ""
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'DeviceCapabilities':
        """Parse capabilities from binary format."""
        if len(data) < 8:
            return cls()  # Return default capabilities
        
        flags = struct.unpack('<B', data[:1])[0]
        supports_historical = bool(flags & 0x01)
        max_records = struct.unpack('<H', data[1:3])[0]
        interval = struct.unpack('<H', data[3:5])[0]
        
        # Parse version strings if available
        fw_version = ""
        hw_version = ""
        
        if len(data) > 8:
            # Simple string parsing - versions are null-terminated
            version_data = data[8:]
            if b'\x00' in version_data:
                fw_end = version_data.find(b'\x00')
                fw_version = version_data[:fw_end].decode('utf-8', errors='ignore')
                
                if fw_end + 1 < len(version_data):
                    hw_data = version_data[fw_end + 1:]
                    if b'\x00' in hw_data:
                        hw_end = hw_data.find(b'\x00')
                        hw_version = hw_data[:hw_end].decode('utf-8', errors='ignore')
        
        return cls(
            supports_historical_data=supports_historical,
            max_historical_records=max_records,
            historical_data_interval=interval,
            firmware_version=fw_version,
            hardware_version=hw_version
        )


class ChunkedDataProcessor:
    """Handles chunked data transfer for large historical datasets."""
    
    def __init__(self, logger: ProductionLogger):
        self.logger = logger
        self.chunks: Dict[int, bytes] = {}
        self.total_chunks = 0
        self.received_chunks = 0
        self.total_size = 0
        self.start_time: Optional[datetime] = None
    
    def start_transfer(self, total_chunks: int, total_size: int):
        """Initialize a new chunked transfer."""
        self.chunks.clear()
        self.total_chunks = total_chunks
        self.received_chunks = 0
        self.total_size = total_size
        self.start_time = datetime.utcnow()
        self.logger.info(f"Starting chunked transfer: {total_chunks} chunks, {total_size} bytes")
    
    def add_chunk(self, chunk_id: int, data: bytes) -> bool:
        """
        Add a chunk to the transfer.
        
        Returns:
            bool: True if transfer is complete
        """
        if chunk_id in self.chunks:
            self.logger.warning(f"Duplicate chunk received: {chunk_id}")
            return False
        
        self.chunks[chunk_id] = data
        self.received_chunks += 1
        
        progress = (self.received_chunks / self.total_chunks) * 100
        self.logger.debug(f"Received chunk {chunk_id}: {len(data)} bytes ({progress:.1f}% complete)")
        
        return self.received_chunks >= self.total_chunks
    
    def get_complete_data(self) -> bytes:
        """Reassemble complete data from chunks."""
        if self.received_chunks < self.total_chunks:
            raise ValueError(f"Transfer incomplete: {self.received_chunks}/{self.total_chunks} chunks")
        
        # Sort chunks by ID and concatenate
        complete_data = b''
        for chunk_id in sorted(self.chunks.keys()):
            complete_data += self.chunks[chunk_id]
        
        elapsed = datetime.utcnow() - self.start_time if self.start_time else timedelta(0)
        self.logger.info(f"Transfer completed: {len(complete_data)} bytes in {elapsed.total_seconds():.1f}s")
        
        return complete_data
    
    def get_progress(self) -> Dict[str, Any]:
        """Get transfer progress information."""
        elapsed = datetime.utcnow() - self.start_time if self.start_time else timedelta(0)
        progress_pct = (self.received_chunks / self.total_chunks) * 100 if self.total_chunks > 0 else 0
        
        return {
            "total_chunks": self.total_chunks,
            "received_chunks": self.received_chunks,
            "progress_percent": progress_pct,
            "total_size": self.total_size,
            "elapsed_seconds": elapsed.total_seconds(),
            "is_complete": self.received_chunks >= self.total_chunks
        }


class RuuviProtocolHandler:
    """Handles Ruuvi GATT protocol communication."""
    
    # Ruuvi GATT Service UUIDs
    RUUVI_SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
    RUUVI_COMMAND_CHAR_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
    RUUVI_RESPONSE_CHAR_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
    RUUVI_DATA_CHAR_UUID = "6E400004-B5A3-F393-E0A9-E50E24DCCA9E"
    
    def __init__(self, client: BleakClient, logger: ProductionLogger):
        self.client = client
        self.logger = logger
        self.sequence_id = 0
        self.response_queue: asyncio.Queue = asyncio.Queue()
        self.data_processor = ChunkedDataProcessor(logger)
        self._notification_handlers_started = False
    
    async def start_notifications(self):
        """Start GATT notifications for responses and data."""
        if self._notification_handlers_started:
            return
        
        try:
            await self.client.start_notify(self.RUUVI_RESPONSE_CHAR_UUID, self._response_handler)
            await self.client.start_notify(self.RUUVI_DATA_CHAR_UUID, self._data_handler)
            self._notification_handlers_started = True
            self.logger.debug("GATT notifications started")
        except Exception as e:
            self.logger.error(f"Failed to start notifications: {e}")
            raise
    
    async def stop_notifications(self):
        """Stop GATT notifications."""
        if not self._notification_handlers_started:
            return
        
        try:
            await self.client.stop_notify(self.RUUVI_RESPONSE_CHAR_UUID)
            await self.client.stop_notify(self.RUUVI_DATA_CHAR_UUID)
            self._notification_handlers_started = False
            self.logger.debug("GATT notifications stopped")
        except Exception as e:
            self.logger.warning(f"Error stopping notifications: {e}")
    
    def _response_handler(self, sender: int, data: bytes):
        """Handle GATT response notifications."""
        try:
            response = RuuviResponse.from_bytes(data)
            self.logger.debug(f"Received response: {response.command_type.name}, status: {response.status.name}")
            asyncio.create_task(self.response_queue.put(response))
        except Exception as e:
            self.logger.error(f"Error parsing response: {e}")
    
    def _data_handler(self, sender: int, data: bytes):
        """Handle GATT data notifications (chunked data)."""
        try:
            if len(data) < 6:
                self.logger.warning("Invalid data chunk received")
                return
            
            # Parse chunk header: chunk_id (2 bytes), total_chunks (2 bytes), chunk_size (2 bytes)
            chunk_id, total_chunks, chunk_size = struct.unpack('<HHH', data[:6])
            chunk_data = data[6:6+chunk_size]
            
            if chunk_id == 0:  # First chunk contains metadata
                if len(chunk_data) >= 4:
                    total_size = struct.unpack('<I', chunk_data[:4])[0]
                    self.data_processor.start_transfer(total_chunks, total_size)
                    # Remaining data is actual content
                    if len(chunk_data) > 4:
                        self.data_processor.add_chunk(chunk_id, chunk_data[4:])
            else:
                self.data_processor.add_chunk(chunk_id, chunk_data)
            
            # Send acknowledgment
            ack_command = RuuviCommand(
                command_type=RuuviCommandType.ACKNOWLEDGE_CHUNK,
                sequence_id=self.sequence_id,
                parameters=struct.pack('<H', chunk_id)
            )
            asyncio.create_task(self._send_command_async(ack_command))
            
        except Exception as e:
            self.logger.error(f"Error processing data chunk: {e}")
    
    async def _send_command_async(self, command: RuuviCommand):
        """Send command asynchronously (for use in notification handlers)."""
        try:
            await self.client.write_gatt_char(self.RUUVI_COMMAND_CHAR_UUID, command.to_bytes())
        except Exception as e:
            self.logger.error(f"Error sending async command: {e}")
    
    async def send_command(self, command: RuuviCommand, timeout: float = 10.0) -> RuuviResponse:
        """Send a command and wait for response."""
        command.sequence_id = self.sequence_id
        self.sequence_id = (self.sequence_id + 1) % 256
        
        try:
            # Send command
            await self.client.write_gatt_char(self.RUUVI_COMMAND_CHAR_UUID, command.to_bytes())
            self.logger.debug(f"Sent command: {command.command_type.name}")
            
            # Wait for response
            response = await asyncio.wait_for(self.response_queue.get(), timeout=timeout)
            
            if response.sequence_id != command.sequence_id:
                self.logger.warning(f"Sequence ID mismatch: expected {command.sequence_id}, got {response.sequence_id}")
            
            return response
            
        except asyncio.TimeoutError:
            raise ScannerOperationError(f"Command timeout: {command.command_type.name}")
        except Exception as e:
            raise ScannerOperationError(f"Command failed: {e}")
    
    async def get_device_capabilities(self) -> DeviceCapabilities:
        """Get device capabilities."""
        command = RuuviCommand(RuuviCommandType.GET_CAPABILITIES, 0)
        response = await self.send_command(command)
        
        if response.status != RuuviResponseStatus.SUCCESS:
            self.logger.warning(f"Capabilities request failed: {response.status.name}")
            return DeviceCapabilities()  # Return default capabilities
        
        return DeviceCapabilities.from_bytes(response.data)
    
    async def retrieve_historical_data(self, hours_back: int) -> List[HistoricalDataRecord]:
        """Retrieve historical data from the device."""
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Prepare command parameters: start_timestamp (4 bytes), end_timestamp (4 bytes)
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())
        parameters = struct.pack('<II', start_timestamp, end_timestamp)
        
        command = RuuviCommand(RuuviCommandType.GET_HISTORICAL_DATA, 0, parameters)
        response = await self.send_command(command, timeout=30.0)
        
        if response.status != RuuviResponseStatus.SUCCESS:
            raise ScannerOperationError(f"Historical data request failed: {response.status.name}")
        
        # Parse response metadata
        if len(response.data) < 8:
            raise ScannerOperationError("Invalid historical data response")
        
        record_count, base_timestamp = struct.unpack('<II', response.data[:8])
        base_dt = datetime.fromtimestamp(base_timestamp)
        
        self.logger.info(f"Expecting {record_count} historical records from {base_dt}")
        
        # Wait for chunked data transfer to complete
        max_wait_time = 60.0  # Maximum wait time for data transfer
        start_wait = datetime.utcnow()
        
        while not self.data_processor.get_progress()["is_complete"]:
            if (datetime.utcnow() - start_wait).total_seconds() > max_wait_time:
                raise ScannerOperationError("Historical data transfer timeout")
            await asyncio.sleep(0.1)
        
        # Parse historical records
        complete_data = self.data_processor.get_complete_data()
        records = []
        
        record_size = 24  # Size of each historical record
        for i in range(0, len(complete_data), record_size):
            if i + record_size <= len(complete_data):
                record_data = complete_data[i:i + record_size]
                try:
                    record = HistoricalDataRecord.from_bytes(record_data, base_dt)
                    records.append(record)
                except Exception as e:
                    self.logger.warning(f"Failed to parse record {i // record_size}: {e}")
        
        self.logger.info(f"Successfully parsed {len(records)} historical records")
        return records


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
        self.logger.debug(f"Notifying {len(self._callbacks)} callbacks for sensor {sensor_data.mac_address}")
        
        for i, callback in enumerate(self._callbacks):
            try:
                self.logger.debug(f"Calling callback {i+1}/{len(self._callbacks)}: {callback.__name__}")
                callback(sensor_data)
                self.logger.debug(f"Callback {i+1} completed successfully")
            except Exception as e:
                self.logger.error(f"Error in callback {callback.__name__}: {e}")
                import traceback
                self.logger.error(f"Callback error traceback: {traceback.format_exc()}")
        
        self.logger.debug(f"All callbacks completed for sensor {sensor_data.mac_address}")
    
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
            self.logger.debug(f"BLE detection callback triggered for device: {device.address}")
            
            # Parse manufacturer data
            self.logger.debug(f"Parsing manufacturer data for {device.address}")
            sensor_data = self._parse_manufacturer_data(advertisement_data.manufacturer_data)
            
            if sensor_data is None:
                self.logger.debug(f"No valid Ruuvi data found for {device.address}")
                return
            
            # Set MAC address and RSSI
            sensor_data.mac_address = device.address.upper()
            sensor_data.rssi = advertisement_data.rssi
            
            # Update discovered devices
            self._discovered_devices[sensor_data.mac_address] = sensor_data
            self._device_count += 1
            
            # Log discovery
            self.logger.info(
                f"Discovered Ruuvi sensor: {sensor_data.mac_address} "
                f"(Format {sensor_data.data_format.value}, RSSI: {sensor_data.rssi}dBm, "
                f"Temp: {sensor_data.temperature}°C, Humidity: {sensor_data.humidity}%)"
            )
            
            # Notify callbacks
            self.logger.debug(f"Notifying {len(self._callbacks)} callbacks for {sensor_data.mac_address}")
            self._notify_callbacks(sensor_data)
            self.logger.debug(f"Callbacks notified successfully for {sensor_data.mac_address}")
            
            # Update performance metrics
            self.performance_monitor.record_metric("ble_devices_discovered", 1)
            self.logger.debug(f"Performance metrics updated for {sensor_data.mac_address}")
            
        except Exception as e:
            self.logger.error(f"Error processing BLE device {device.address}: {e}")
            import traceback
            self.logger.error(f"Detection callback traceback: {traceback.format_exc()}")
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
        """True continuous scanning loop - listens to BLE advertisements continuously."""
        self.logger.info("Starting true continuous BLE advertisement listening...")
        
        try:
            # Determine the correct adapter
            adapter = None if self.adapter == "auto" else self.adapter
            self.logger.debug(f"Using BLE adapter: {adapter}")
            
            # Start continuous scanning without time limits
            self._scanner = BleakScanner(
                detection_callback=self._detection_callback,
                adapter=adapter
            )
            self.logger.debug("BleakScanner created successfully")
            
            self._is_scanning = True
            self.logger.debug("Starting BLE scanner...")
            await self._scanner.start()
            self.logger.info("Continuous BLE listening started - no scan gaps")
            
            # Keep running until cancelled - the scanner listens continuously
            loop_count = 0
            while True:
                await asyncio.sleep(1)  # Just keep the loop alive
                loop_count += 1
                if loop_count % 30 == 0:  # Log every 30 seconds
                    self.logger.debug(f"Continuous scan loop alive - iteration {loop_count}, "
                                    f"devices discovered: {len(self._discovered_devices)}")
                    
        except asyncio.CancelledError:
            self.logger.info("Continuous scan loop cancelled")
        except Exception as e:
            self.logger.error(f"Continuous scan error: {e}")
            import traceback
            self.logger.error(f"Continuous scan traceback: {traceback.format_exc()}")
        finally:
            if self._is_scanning and self._scanner:
                try:
                    self.logger.debug("Stopping BLE scanner...")
                    await self._scanner.stop()
                    self._is_scanning = False
                    self.logger.info("Continuous BLE listening stopped")
                except Exception as e:
                    self.logger.warning(f"Error stopping scanner: {e}")
    
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
    
    async def retrieve_historical_data(self, mac_address: str, hours_back: int = 24) -> List[RuuviSensorData]:
        """
        Connect to a Ruuvi sensor and retrieve historical data using GATT protocol.
        
        Args:
            mac_address: MAC address of the sensor to connect to
            hours_back: Number of hours of historical data to retrieve
            
        Returns:
            List[RuuviSensorData]: Historical sensor data converted to standard format
            
        Raises:
            ScannerOperationError: If connection or data retrieval fails
        """
        historical_data = []
        client = None
        protocol_handler = None
        
        try:
            self.logger.info(f"Connecting to Ruuvi sensor {mac_address} for historical data retrieval...")
            
            # Create BLE client for direct connection
            adapter = None if self.adapter == "auto" else self.adapter
            client = BleakClient(mac_address, adapter=adapter)
            
            # Connect to the device with extended timeout for historical data operations
            await client.connect(timeout=30.0)
            self.logger.info(f"Successfully connected to {mac_address}")
            
            # Get available services to verify Ruuvi GATT service
            services = await client.get_services()
            ruuvi_service = None
            
            for service in services:
                if str(service.uuid).upper() == RuuviProtocolHandler.RUUVI_SERVICE_UUID.upper():
                    ruuvi_service = service
                    break
            
            if not ruuvi_service:
                # Fallback: look for Nordic UART service which some Ruuvi devices use
                for service in services:
                    if str(service.uuid).upper() in [
                        "6E400001-B5A3-F393-E0A9-E50E24DCCA9E",  # Nordic UART
                        "00001800-0000-1000-8000-00805F9B34FB",  # Generic Access
                    ]:
                        ruuvi_service = service
                        break
            
            if not ruuvi_service:
                self.logger.warning(f"Ruuvi GATT service not found on {mac_address}")
                # Try to detect capabilities anyway
                capabilities = DeviceCapabilities()
            else:
                self.logger.info(f"Found Ruuvi service: {ruuvi_service.uuid}")
                
                # Initialize protocol handler
                protocol_handler = RuuviProtocolHandler(client, self.logger)
                await protocol_handler.start_notifications()
                
                # Get device capabilities
                try:
                    capabilities = await protocol_handler.get_device_capabilities()
                    self.logger.info(f"Device capabilities: historical_data={capabilities.supports_historical_data}, "
                                   f"max_records={capabilities.max_historical_records}, "
                                   f"interval={capabilities.historical_data_interval}s, "
                                   f"firmware={capabilities.firmware_version}")
                except Exception as e:
                    self.logger.warning(f"Failed to get capabilities: {e}")
                    capabilities = DeviceCapabilities()
            
            # Check if device supports historical data
            if not capabilities.supports_historical_data:
                self.logger.warning(f"Device {mac_address} does not support historical data retrieval")
                return []
            
            if not protocol_handler:
                self.logger.error(f"Cannot retrieve historical data: protocol handler not initialized")
                return []
            
            # Retrieve historical data
            self.logger.info(f"Retrieving {hours_back} hours of historical data from {mac_address}...")
            
            with self.performance_monitor.measure_time("historical_data_retrieval"):
                historical_records = await protocol_handler.retrieve_historical_data(hours_back)
            
            # Convert historical records to RuuviSensorData format for compatibility
            for record in historical_records:
                sensor_data = record.to_ruuvi_sensor_data(mac_address)
                historical_data.append(sensor_data)
            
            self.logger.info(f"Successfully retrieved {len(historical_data)} historical records from {mac_address}")
            
            # Update performance metrics
            self.performance_monitor.record_metric("historical_records_retrieved", len(historical_data))
            
        except ScannerOperationError:
            # Re-raise scanner operation errors
            raise
        except Exception as e:
            self.logger.error(f"Failed to retrieve historical data from {mac_address}: {e}")
            self.performance_monitor.record_metric("historical_retrieval_errors", 1)
            raise ScannerOperationError(f"Historical data retrieval failed: {e}")
            
        finally:
            # Clean up protocol handler
            if protocol_handler:
                try:
                    await protocol_handler.stop_notifications()
                except Exception as e:
                    self.logger.warning(f"Error stopping protocol notifications: {e}")
            
            # Disconnect from device
            if client and client.is_connected:
                try:
                    await client.disconnect()
                    self.logger.debug(f"Disconnected from {mac_address}")
                except Exception as e:
                    self.logger.warning(f"Error disconnecting from {mac_address}: {e}")
        
        return historical_data
    
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