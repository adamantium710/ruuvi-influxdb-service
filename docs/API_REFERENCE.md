# API Reference

This document provides detailed API reference for the Ruuvi Sensor Service components.

## 📋 Table of Contents

- [Core Classes](#core-classes)
- [BLE Scanner](#ble-scanner)
- [InfluxDB Client](#influxdb-client)
- [Metadata Manager](#metadata-manager)
- [Service Manager](#service-manager)
- [Configuration](#configuration)
- [Logging](#logging)
- [CLI Components](#cli-components)
- [Exception Handling](#exception-handling)
- [Data Models](#data-models)

## 🏗️ Core Classes

### RuuviCLI

Main CLI application class providing interactive interface.

```python
from src.cli.menu import RuuviCLI

class RuuviCLI:
    """Main CLI application for Ruuvi Sensor Service."""
    
    def __init__(self):
        """Initialize CLI application."""
    
    async def initialize(self) -> bool:
        """Initialize all components."""
    
    async def run(self) -> None:
        """Run the main CLI loop."""
    
    async def cleanup(self) -> None:
        """Clean up resources."""
```

**Methods:**

- `initialize()`: Initialize all components and validate configuration
- `run()`: Start the interactive CLI menu system
- `cleanup()`: Clean up resources and close connections

**Example Usage:**

```python
import asyncio
from src.cli.menu import RuuviCLI

async def main():
    cli = RuuviCLI()
    try:
        if await cli.initialize():
            await cli.run()
    finally:
        await cli.cleanup()

asyncio.run(main())
```

## 📡 BLE Scanner

### RuuviBLEScanner

Bluetooth Low Energy scanner for Ruuvi sensors.

```python
from src.ble.scanner import RuuviBLEScanner, RuuviSensorData

class RuuviBLEScanner:
    """BLE scanner for Ruuvi sensors with advanced features."""
    
    def __init__(self, 
                 scan_interval: int = 10,
                 scan_timeout: int = 5,
                 adapter_id: int = 0):
        """Initialize BLE scanner."""
    
    async def start_scanning(self) -> None:
        """Start continuous BLE scanning."""
    
    async def stop_scanning(self) -> None:
        """Stop BLE scanning."""
    
    async def discover_sensors(self, duration: int = 10) -> List[str]:
        """Discover nearby Ruuvi sensors."""
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scanner statistics."""
```

**Parameters:**

- `scan_interval`: Time between scans in seconds (default: 10)
- `scan_timeout`: Scan duration in seconds (default: 5)
- `adapter_id`: Bluetooth adapter ID (default: 0)

**Methods:**

- `start_scanning()`: Begin continuous scanning for sensor data
- `stop_scanning()`: Stop the scanning process
- `discover_sensors(duration)`: Scan for new sensors for specified duration
- `get_statistics()`: Return performance metrics and statistics

**Events:**

The scanner emits events for sensor data:

```python
scanner.on_sensor_data = lambda data: handle_sensor_data(data)
scanner.on_sensor_discovered = lambda mac: handle_new_sensor(mac)
scanner.on_error = lambda error: handle_error(error)
```

**Example Usage:**

```python
import asyncio
from src.ble.scanner import RuuviBLEScanner

async def handle_sensor_data(data):
    print(f"Sensor {data.mac_address}: {data.temperature}°C")

async def main():
    scanner = RuuviBLEScanner(scan_interval=5)
    scanner.on_sensor_data = handle_sensor_data
    
    await scanner.start_scanning()
    await asyncio.sleep(60)  # Scan for 1 minute
    await scanner.stop_scanning()

asyncio.run(main())
```

### RuuviSensorData

Data model for Ruuvi sensor measurements.

```python
@dataclass
class RuuviSensorData:
    """Ruuvi sensor data model."""
    
    mac_address: str
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
    rssi: Optional[int] = None
    data_format: Optional[int] = None
```

**Properties:**

- `mac_address`: Sensor MAC address (required)
- `timestamp`: Measurement timestamp (required)
- `temperature`: Temperature in Celsius
- `humidity`: Relative humidity percentage
- `pressure`: Atmospheric pressure in hPa
- `acceleration_x/y/z`: Acceleration in g-force
- `battery_voltage`: Battery voltage in volts
- `tx_power`: Transmission power in dBm
- `movement_counter`: Movement detection counter
- `measurement_sequence`: Measurement sequence number
- `rssi`: Received Signal Strength Indicator
- `data_format`: Ruuvi data format version

## 🗄️ InfluxDB Client

### RuuviInfluxDBClient

InfluxDB client for time-series data storage.

```python
from src.influxdb.client import RuuviInfluxDBClient

class RuuviInfluxDBClient:
    """InfluxDB client for Ruuvi sensor data."""
    
    def __init__(self,
                 host: str = "localhost",
                 port: int = 8086,
                 database: str = "ruuvi_sensors",
                 username: Optional[str] = None,
                 password: Optional[str] = None):
        """Initialize InfluxDB client."""
    
    async def connect(self) -> bool:
        """Connect to InfluxDB server."""
    
    async def disconnect(self) -> None:
        """Disconnect from InfluxDB server."""
    
    async def write_sensor_data(self, data: RuuviSensorData) -> bool:
        """Write sensor data to InfluxDB."""
    
    async def write_batch_data(self, data_list: List[RuuviSensorData]) -> bool:
        """Write multiple sensor data points."""
    
    async def query_sensor_data(self,
                               mac_address: Optional[str] = None,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> List[Dict]:
        """Query sensor data from InfluxDB."""
    
    async def health_check(self) -> bool:
        """Check InfluxDB server health."""
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get client statistics."""
```

**Parameters:**

- `host`: InfluxDB server hostname
- `port`: InfluxDB server port
- `database`: Database name
- `username`: Authentication username (optional)
- `password`: Authentication password (optional)

**Methods:**

- `connect()`: Establish connection to InfluxDB
- `disconnect()`: Close connection
- `write_sensor_data(data)`: Write single sensor measurement
- `write_batch_data(data_list)`: Write multiple measurements efficiently
- `query_sensor_data()`: Query historical data with filters
- `health_check()`: Verify server connectivity and health
- `get_statistics()`: Return performance metrics

**Example Usage:**

```python
import asyncio
from src.influxdb.client import RuuviInfluxDBClient
from src.ble.scanner import RuuviSensorData
from datetime import datetime

async def main():
    client = RuuviInfluxDBClient(
        host="localhost",
        database="ruuvi_sensors"
    )
    
    if await client.connect():
        # Write data
        data = RuuviSensorData(
            mac_address="AA:BB:CC:DD:EE:FF",
            timestamp=datetime.now(),
            temperature=22.5,
            humidity=45.0
        )
        await client.write_sensor_data(data)
        
        # Query data
        results = await client.query_sensor_data(
            mac_address="AA:BB:CC:DD:EE:FF",
            start_time=datetime.now() - timedelta(hours=1)
        )
        
        await client.disconnect()

asyncio.run(main())
```

## 📊 Metadata Manager

### MetadataManager

Manages sensor metadata and registration.

```python
from src.metadata.manager import MetadataManager

class MetadataManager:
    """Manages sensor metadata and registration."""
    
    def __init__(self, metadata_file: str = "data/sensor_metadata.json"):
        """Initialize metadata manager."""
    
    async def load_metadata(self) -> bool:
        """Load metadata from file."""
    
    async def save_metadata(self) -> bool:
        """Save metadata to file."""
    
    async def register_sensor(self, 
                             mac_address: str, 
                             metadata: Dict[str, Any]) -> bool:
        """Register a new sensor."""
    
    async def update_sensor(self, 
                           mac_address: str, 
                           updates: Dict[str, Any]) -> bool:
        """Update sensor metadata."""
    
    async def get_sensor(self, mac_address: str) -> Optional[Dict[str, Any]]:
        """Get sensor metadata."""
    
    async def list_sensors(self) -> List[Dict[str, Any]]:
        """List all registered sensors."""
    
    async def remove_sensor(self, mac_address: str) -> bool:
        """Remove sensor from registry."""
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Validate metadata structure."""
```

**Methods:**

- `load_metadata()`: Load sensor metadata from JSON file
- `save_metadata()`: Save metadata to JSON file
- `register_sensor()`: Add new sensor to registry
- `update_sensor()`: Update existing sensor information
- `get_sensor()`: Retrieve specific sensor metadata
- `list_sensors()`: Get all registered sensors
- `remove_sensor()`: Remove sensor from registry
- `validate_metadata()`: Validate metadata structure

**Metadata Schema:**

```json
{
  "mac_address": {
    "name": "Human-readable name",
    "location": "Physical location",
    "description": "Sensor description",
    "first_seen": "ISO timestamp",
    "last_seen": "ISO timestamp",
    "data_format": 5,
    "firmware_version": "3.31.0",
    "calibration": {
      "temperature_offset": 0.0,
      "humidity_offset": 0.0,
      "pressure_offset": 0.0
    },
    "alerts": {
      "temperature_min": -40.0,
      "temperature_max": 85.0,
      "humidity_min": 0.0,
      "humidity_max": 100.0
    }
  }
}
```

**Example Usage:**

```python
import asyncio
from src.metadata.manager import MetadataManager

async def main():
    manager = MetadataManager()
    await manager.load_metadata()
    
    # Register new sensor
    await manager.register_sensor(
        "AA:BB:CC:DD:EE:FF",
        {
            "name": "Living Room",
            "location": "Indoor",
            "description": "Temperature and humidity sensor"
        }
    )
    
    # List all sensors
    sensors = await manager.list_sensors()
    for sensor in sensors:
        print(f"{sensor['mac_address']}: {sensor['name']}")
    
    await manager.save_metadata()

asyncio.run(main())
```

## ⚙️ Service Manager

### ServiceManager

Manages systemd service operations.

```python
from src.service.manager import ServiceManager, ServiceStatus

class ServiceManager:
    """Manages systemd service operations."""
    
    def __init__(self, service_name: str = "ruuvi-sensor"):
        """Initialize service manager."""
    
    async def get_status(self) -> ServiceStatus:
        """Get service status."""
    
    async def start_service(self) -> bool:
        """Start the service."""
    
    async def stop_service(self) -> bool:
        """Stop the service."""
    
    async def restart_service(self) -> bool:
        """Restart the service."""
    
    async def enable_service(self) -> bool:
        """Enable service auto-start."""
    
    async def disable_service(self) -> bool:
        """Disable service auto-start."""
    
    async def get_logs(self, lines: int = 50) -> List[str]:
        """Get service logs."""
    
    async def install_service(self, service_file_path: str) -> bool:
        """Install service file."""
```

**ServiceStatus Enum:**

```python
from enum import Enum

class ServiceStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    UNKNOWN = "unknown"
```

**Example Usage:**

```python
import asyncio
from src.service.manager import ServiceManager

async def main():
    manager = ServiceManager("ruuvi-sensor")
    
    # Check status
    status = await manager.get_status()
    print(f"Service status: {status.value}")
    
    # Start service if not running
    if status != ServiceStatus.ACTIVE:
        await manager.start_service()
    
    # Get recent logs
    logs = await manager.get_logs(20)
    for log in logs:
        print(log)

asyncio.run(main())
```

## 🔧 Configuration

### Config

Configuration management with validation.

```python
from src.utils.config import Config

class Config:
    """Configuration manager with validation."""
    
    def __init__(self, config_file: str = ".env"):
        """Initialize configuration."""
    
    def load(self) -> bool:
        """Load configuration from file."""
    
    def validate(self) -> bool:
        """Validate configuration values."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
    
    def save(self) -> bool:
        """Save configuration to file."""
    
    @property
    def influxdb_config(self) -> Dict[str, Any]:
        """Get InfluxDB configuration."""
    
    @property
    def ble_config(self) -> Dict[str, Any]:
        """Get BLE configuration."""
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
```

**Configuration Keys:**

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `INFLUXDB_HOST` | str | localhost | InfluxDB hostname |
| `INFLUXDB_PORT` | int | 8086 | InfluxDB port |
| `INFLUXDB_DATABASE` | str | ruuvi_sensors | Database name |
| `INFLUXDB_USERNAME` | str | None | Username |
| `INFLUXDB_PASSWORD` | str | None | Password |
| `BLE_SCAN_INTERVAL` | int | 10 | Scan interval (seconds) |
| `BLE_SCAN_TIMEOUT` | int | 5 | Scan timeout (seconds) |
| `BLE_ADAPTER_ID` | int | 0 | Bluetooth adapter ID |
| `LOG_LEVEL` | str | INFO | Logging level |
| `LOG_FILE` | str | logs/ruuvi_sensor.log | Log file path |

**Example Usage:**

```python
from src.utils.config import Config

config = Config()
if config.load() and config.validate():
    influxdb_config = config.influxdb_config
    print(f"InfluxDB: {influxdb_config['host']}:{influxdb_config['port']}")
```

## 📝 Logging

### ProductionLogger

Advanced logging with multiple outputs and performance monitoring.

```python
from src.utils.logging import ProductionLogger, PerformanceMonitor

class ProductionLogger:
    """Production-grade logger with multiple outputs."""
    
    def __init__(self,
                 name: str,
                 level: str = "INFO",
                 log_file: Optional[str] = None,
                 max_size: int = 10485760,
                 backup_count: int = 5):
        """Initialize logger."""
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
    
    def log_performance(self, operation: str, duration: float, **kwargs) -> None:
        """Log performance metrics."""
```

### PerformanceMonitor

Performance monitoring and metrics collection.

```python
class PerformanceMonitor:
    """Performance monitoring and metrics collection."""
    
    def __init__(self):
        """Initialize performance monitor."""
    
    def start_operation(self, operation: str) -> str:
        """Start timing an operation."""
    
    def end_operation(self, operation_id: str) -> float:
        """End timing and return duration."""
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None) -> None:
        """Record a metric value."""
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics."""
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
```

**Example Usage:**

```python
from src.utils.logging import ProductionLogger, PerformanceMonitor

# Initialize logger
logger = ProductionLogger("ruuvi-sensor", level="INFO", log_file="app.log")

# Initialize performance monitor
perf_monitor = PerformanceMonitor()

# Log with performance monitoring
operation_id = perf_monitor.start_operation("ble_scan")
try:
    # Perform BLE scan
    await scanner.discover_sensors(10)
    logger.info("BLE scan completed successfully")
except Exception as e:
    logger.error(f"BLE scan failed: {e}")
finally:
    duration = perf_monitor.end_operation(operation_id)
    logger.log_performance("ble_scan", duration)
```

## 🖥️ CLI Components

### AdvancedCLIFeatures

Advanced CLI functionality including wizards and data operations.

```python
from src.cli.advanced_features import AdvancedCLIFeatures

class AdvancedCLIFeatures:
    """Advanced CLI features and utilities."""
    
    def __init__(self, 
                 config: Config,
                 logger: ProductionLogger,
                 metadata_manager: MetadataManager,
                 influxdb_client: RuuviInfluxDBClient):
        """Initialize advanced features."""
    
    async def interactive_setup_wizard(self) -> bool:
        """Run interactive setup wizard."""
    
    async def export_data(self, 
                         format: str,
                         filename: Optional[str] = None,
                         **kwargs) -> bool:
        """Export sensor data."""
    
    async def import_data(self, filename: str) -> bool:
        """Import sensor data."""
    
    async def sensor_calibration_test(self, 
                                     mac_address: str,
                                     test_type: str) -> Dict[str, Any]:
        """Run sensor calibration tests."""
    
    async def batch_operations(self, 
                              sensors: List[str],
                              operation: str) -> bool:
        """Perform batch operations on multiple sensors."""
    
    async def real_time_dashboard(self) -> None:
        """Display real-time sensor dashboard."""
```

**Export Formats:**

- `json`: JSON format with full metadata
- `csv`: CSV format for spreadsheet applications
- `influxdb`: Direct InfluxDB export to another instance

**Test Types:**

- `signal_strength`: Test BLE signal quality
- `data_consistency`: Validate measurement consistency
- `range_validation`: Check measurement ranges
- `battery_health`: Monitor battery levels
- `response_time`: Measure sensor response times
- `all`: Run all tests

**Example Usage:**

```python
import asyncio
from src.cli.advanced_features import AdvancedCLIFeatures

async def main():
    # Initialize components (config, logger, etc.)
    advanced = AdvancedCLIFeatures(config, logger, metadata_manager, influxdb_client)
    
    # Run setup wizard
    await advanced.interactive_setup_wizard()
    
    # Export data
    await advanced.export_data("json", "backup.json")
    
    # Test sensor
    results = await advanced.sensor_calibration_test("AA:BB:CC:DD:EE:FF", "all")
    print(f"Test results: {results}")

asyncio.run(main())
```

## ⚠️ Exception Handling

### EdgeCaseHandler

Comprehensive error handling and recovery.

```python
from src.exceptions.edge_cases import EdgeCaseHandler

class EdgeCaseHandler:
    """Handles edge cases and error recovery."""
    
    def __init__(self, logger: ProductionLogger):
        """Initialize edge case handler."""
    
    async def handle_ble_adapter_error(self, error: Exception) -> bool:
        """Handle BLE adapter errors with recovery."""
    
    async def handle_file_corruption(self, file_path: str) -> bool:
        """Handle file corruption with backup recovery."""
    
    async def handle_network_connectivity_issue(self, host: str, port: int) -> bool:
        """Handle network connectivity issues."""
    
    async def handle_resource_exhaustion(self, resource_type: str) -> bool:
        """Handle resource exhaustion scenarios."""
    
    async def handle_permission_error(self, operation: str, path: str) -> bool:
        """Handle permission errors with guidance."""
    
    async def handle_concurrent_access_error(self, resource: str) -> bool:
        """Handle concurrent access conflicts."""
```

**Error Recovery Strategies:**

- **BLE Adapter**: Reset adapter, reload drivers, provide troubleshooting steps
- **File Corruption**: Restore from backup, recreate with defaults
- **Network Issues**: Retry with backoff, check connectivity, validate configuration
- **Resource Exhaustion**: Clean up resources, provide system recommendations
- **Permissions**: Provide specific fix commands and explanations
- **Concurrency**: Implement locking, retry mechanisms

**Example Usage:**

```python
from src.exceptions.edge_cases import EdgeCaseHandler

handler = EdgeCaseHandler(logger)

try:
    await scanner.start_scanning()
except BluetoothError as e:
    if await handler.handle_ble_adapter_error(e):
        # Retry operation
        await scanner.start_scanning()
    else:
        logger.error("Could not recover from BLE error")
```

## 📊 Data Models

### Complete Data Schema

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List

@dataclass
class RuuviSensorData:
    """Complete Ruuvi sensor data model."""
    mac_address: str
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
    rssi: Optional[int] = None
    data_format: Optional[int] = None

@dataclass
class SensorMetadata:
    """Sensor metadata model."""
    mac_address: str
    name: str
    location: str
    description: str
    first_seen: datetime
    last_seen: datetime
    data_format: int
    firmware_version: str
    calibration: Dict[str, float]
    alerts: Dict[str, float]
    tags: List[str]

@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, int]
    ble_scan_count: int
    influxdb_write_count: int
    error_count: int
```

## 🔗 Integration Examples

### Complete Application Setup

```python
import asyncio
from src.utils.config import Config
from src.utils.logging import ProductionLogger, PerformanceMonitor
from src.metadata.manager import MetadataManager
from src.ble.scanner import RuuviBLEScanner
from src.influxdb.client import RuuviInfluxDBClient
from src.exceptions.edge_cases import EdgeCaseHandler

async def main():
    # Initialize configuration
    config = Config()
    if not (config.load() and config.validate()):
        print("Configuration error")
        return
    
    # Initialize logging
    logger = ProductionLogger("ruuvi-app", **config.logging_config)
    perf_monitor = PerformanceMonitor()
    
    # Initialize edge case handler
    edge_handler = EdgeCaseHandler(logger)
    
    # Initialize metadata manager
    metadata_manager = MetadataManager()
    await metadata_manager.load_metadata()
    
    # Initialize InfluxDB client
    influxdb_client = RuuviInfluxDBClient(**config.influxdb_config)
    if not await influxdb_client.connect():
        logger.error("Failed to connect to InfluxDB")
        return
    
    # Initialize BLE scanner
    ble_scanner = RuuviBLEScanner(**config.ble_config)
    
    # Set up event handlers
    async def handle_sensor_data(data):
        # Register new sensors
        if not await metadata_manager.get_sensor(data.mac_address):
            await metadata_manager.register_sensor(data.mac_address, {
                "name": f"Sensor {data.mac_address[-5:]}",
                "location": "Unknown",
                "description": "Auto-discovered sensor"
            })
        
        # Write to InfluxDB
        await influxdb_client.write_sensor_data(data)
        logger.info(f"Data written for sensor {data.mac_address}")
    
    ble_scanner.on_sensor_data = handle_sensor_data
    
    try:
        # Start scanning
        await ble_scanner.start_scanning()
        logger.info("Started BLE scanning")
        
        # Run for specified duration
        await asyncio.sleep(3600)  # Run for 1 hour
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        # Handle with edge case handler
        await edge_handler.handle_ble_adapter_error(e)
    
    finally:
        # Cleanup
        await ble_scanner.stop_scanning()
        await influxdb_client.disconnect()
        await metadata_manager.save_metadata()
        logger.info("Application shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

This API reference provides comprehensive documentation for all components of the Ruuvi Sensor Service. For additional examples and use cases, refer to the source code and test files.