"""
Ruuvi Sensor Service - BLE sensor monitoring and data collection.

A comprehensive Python service for discovering, monitoring, and collecting data
from Ruuvi environmental sensors via Bluetooth Low Energy (BLE) and storing
the data in InfluxDB for analysis and visualization.

Features:
- Automatic Ruuvi sensor discovery via BLE
- Real-time data collection and monitoring
- InfluxDB integration for time-series data storage
- Comprehensive metadata management
- Interactive CLI interface
- Performance monitoring and logging
- Configuration management with environment variables
"""

__version__ = "1.0.0"
__author__ = "Ruuvi Sensor Service Team"
__description__ = "BLE sensor monitoring and data collection service"

# Package imports for convenience
from .utils.config import Config
from .utils.logging import ProductionLogger, PerformanceMonitor
from .metadata.manager import MetadataManager
from .metadata.schema import MetadataFile, SensorMetadata
from .ble.scanner import RuuviBLEScanner, RuuviSensorData
from .influxdb.client import RuuviInfluxDBClient
from .cli.menu import RuuviCLI

__all__ = [
    "Config",
    "ProductionLogger", 
    "PerformanceMonitor",
    "MetadataManager",
    "MetadataFile",
    "SensorMetadata", 
    "RuuviBLEScanner",
    "RuuviSensorData",
    "RuuviInfluxDBClient",
    "RuuviCLI"
]