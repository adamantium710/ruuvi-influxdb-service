"""
Pydantic schemas for Ruuvi sensor metadata validation.
Defines the structure and validation rules for sensor metadata.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum


class SensorStatus(str, Enum):
    """Enumeration of possible sensor statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"


class InfluxDBConfig(BaseModel):
    """InfluxDB connection configuration."""
    host: str = Field(..., description="InfluxDB host address")
    port: int = Field(8086, ge=1, le=65535, description="InfluxDB port")
    bucket: str = Field(..., description="InfluxDB bucket name")
    org: str = Field(..., description="InfluxDB organization")
    token: str = Field(..., description="InfluxDB authentication token")
    timeout: int = Field(30, ge=5, le=300, description="Connection timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    enable_gzip: bool = Field(True, description="Enable GZIP compression")


class SensorMetadata(BaseModel):
    """Metadata for a single Ruuvi sensor."""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable sensor name")
    location: str = Field("", max_length=100, description="Physical location")
    discovered_at: datetime = Field(default_factory=datetime.utcnow, description="When sensor was first discovered")
    last_seen: Optional[datetime] = Field(None, description="Last time sensor was detected")
    status: SensorStatus = Field(SensorStatus.UNKNOWN, description="Current sensor status")
    enabled: bool = Field(True, description="Whether sensor data collection is enabled")
    notes: str = Field("", max_length=500, description="Additional notes")
    firmware_version: Optional[str] = Field(None, description="RuuviTag firmware version")
    battery_level: Optional[float] = Field(None, ge=0, le=100, description="Battery percentage")
    
    @validator('name')
    def name_must_not_be_empty(cls, v):
        """Validate that sensor name is not empty."""
        if not v.strip():
            raise ValueError('Sensor name cannot be empty')
        return v.strip()
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AppConfig(BaseModel):
    """Application configuration settings."""
    scan_interval: int = Field(20, ge=5, le=300, description="BLE scan interval in seconds")
    batch_size: int = Field(100, ge=1, le=1000, description="InfluxDB batch size")
    log_level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Logging level")
    max_buffer_size: int = Field(10000, ge=100, le=100000, description="Maximum buffer size for data points")
    enable_auto_discovery: bool = Field(True, description="Enable automatic sensor discovery")
    performance_monitoring: bool = Field(True, description="Enable performance monitoring")
    
    @validator('log_level')
    def log_level_uppercase(cls, v):
        """Ensure log level is uppercase."""
        return v.upper()


class MetadataFile(BaseModel):
    """Root metadata file structure."""
    version: str = Field("1.0", description="Schema version")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="File creation timestamp")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    sensors: Dict[str, SensorMetadata] = Field(default_factory=dict, description="Sensor metadata by MAC address")
    influxdb: InfluxDBConfig = Field(..., description="InfluxDB configuration")
    config: AppConfig = Field(default_factory=AppConfig, description="Application configuration")
    
    @validator('sensors')
    def validate_mac_addresses(cls, v):
        """Validate MAC address format in sensor keys."""
        import re
        mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
        for mac_address in v.keys():
            if not mac_pattern.match(mac_address):
                raise ValueError(f'Invalid MAC address format: {mac_address}')
        return v
    
    def update_timestamp(self):
        """Update the last_updated timestamp."""
        self.last_updated = datetime.utcnow()
    
    def add_sensor(self, mac_address: str, name: str, location: str = "") -> SensorMetadata:
        """
        Add a new sensor to the metadata.
        
        Args:
            mac_address: MAC address of the sensor
            name: Human-readable name for the sensor
            location: Physical location of the sensor
            
        Returns:
            SensorMetadata: The created sensor metadata
        """
        sensor = SensorMetadata(
            name=name,
            location=location,
            discovered_at=datetime.utcnow(),
            status=SensorStatus.ACTIVE
        )
        self.sensors[mac_address] = sensor
        self.update_timestamp()
        return sensor
    
    def update_sensor(self, mac_address: str, **kwargs) -> Optional[SensorMetadata]:
        """
        Update sensor metadata.
        
        Args:
            mac_address: MAC address of the sensor
            **kwargs: Fields to update
            
        Returns:
            SensorMetadata: Updated sensor metadata or None if not found
        """
        if mac_address not in self.sensors:
            return None
        
        sensor = self.sensors[mac_address]
        for field, value in kwargs.items():
            if hasattr(sensor, field):
                setattr(sensor, field, value)
        
        self.update_timestamp()
        return sensor
    
    def remove_sensor(self, mac_address: str) -> bool:
        """
        Remove a sensor from the metadata.
        
        Args:
            mac_address: MAC address of the sensor to remove
            
        Returns:
            bool: True if sensor was removed, False if not found
        """
        if mac_address in self.sensors:
            del self.sensors[mac_address]
            self.update_timestamp()
            return True
        return False
    
    def get_active_sensors(self) -> Dict[str, SensorMetadata]:
        """
        Get all active sensors.
        
        Returns:
            Dict[str, SensorMetadata]: Active sensors by MAC address
        """
        return {
            mac: sensor for mac, sensor in self.sensors.items()
            if sensor.enabled and sensor.status == SensorStatus.ACTIVE
        }
    
    def get_sensor_by_name(self, name: str) -> Optional[tuple[str, SensorMetadata]]:
        """
        Find sensor by name.
        
        Args:
            name: Sensor name to search for
            
        Returns:
            Optional[tuple[str, SensorMetadata]]: (MAC address, sensor metadata) or None
        """
        for mac, sensor in self.sensors.items():
            if sensor.name.lower() == name.lower():
                return mac, sensor
        return None
    
    def get_sensors_by_location(self, location: str) -> Dict[str, SensorMetadata]:
        """
        Get sensors by location.
        
        Args:
            location: Location to search for
            
        Returns:
            Dict[str, SensorMetadata]: Sensors in the specified location
        """
        return {
            mac: sensor for mac, sensor in self.sensors.items()
            if sensor.location.lower() == location.lower()
        }
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


def create_default_metadata(influxdb_config: InfluxDBConfig) -> MetadataFile:
    """
    Create a default metadata file with the provided InfluxDB configuration.
    
    Args:
        influxdb_config: InfluxDB configuration
        
    Returns:
        MetadataFile: Default metadata file
    """
    return MetadataFile(
        influxdb=influxdb_config,
        config=AppConfig()
    )


def validate_mac_address(mac_address: str) -> bool:
    """
    Validate MAC address format.
    
    Args:
        mac_address: MAC address to validate
        
    Returns:
        bool: True if valid MAC address format
    """
    import re
    mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    return bool(mac_pattern.match(mac_address))


def normalize_mac_address(mac_address: str) -> str:
    """
    Normalize MAC address to uppercase with colon separators.
    
    Args:
        mac_address: MAC address to normalize
        
    Returns:
        str: Normalized MAC address
    """
    # Remove any separators and convert to uppercase
    clean_mac = ''.join(c for c in mac_address.upper() if c.isalnum())
    
    # Add colons every 2 characters
    if len(clean_mac) == 12:
        return ':'.join(clean_mac[i:i+2] for i in range(0, 12, 2))
    else:
        raise ValueError(f"Invalid MAC address length: {mac_address}")