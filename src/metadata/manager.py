"""
Metadata manager for Ruuvi sensor configuration and state management.
Handles JSON file operations with concurrent access safety and backup/recovery.
"""

import json
import os
import shutil
import fcntl
import time
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager

from .schema import MetadataFile, SensorMetadata, InfluxDBConfig, AppConfig, create_default_metadata, normalize_mac_address
from ..utils.config import Config
from ..utils.logging import ProductionLogger


class MetadataError(Exception):
    """Base exception for metadata operations."""
    pass


class MetadataFileError(MetadataError):
    """Exception for file operation errors."""
    pass


class MetadataValidationError(MetadataError):
    """Exception for validation errors."""
    pass


class MetadataManager:
    """
    Manages sensor metadata with JSON file persistence and concurrent access safety.
    
    Features:
    - File locking for concurrent access safety
    - Automatic backup and recovery
    - Validation using Pydantic schemas
    - CRUD operations for sensors
    - Configuration management
    """
    
    def __init__(self, config: Config, logger: ProductionLogger):
        """
        Initialize metadata manager.
        
        Args:
            config: Application configuration
            logger: Logger instance
        """
        self.config = config
        self.logger = logger
        self.metadata_file = Path(config.metadata_file)
        self.backup_dir = Path(config.backup_dir)
        self.lock_timeout = 30  # seconds
        self._metadata: Optional[MetadataFile] = None
        
        # Ensure directories exist
        self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"MetadataManager initialized with file: {self.metadata_file}")
    
    @contextmanager
    def _file_lock(self, file_path: Path, mode: str = 'r'):
        """
        Context manager for file locking.
        
        Args:
            file_path: Path to the file to lock
            mode: File open mode
            
        Yields:
            file: Opened file handle with lock
        """
        lock_acquired = False
        file_handle = None
        
        try:
            file_handle = open(file_path, mode)
            
            # Try to acquire lock with timeout
            start_time = time.time()
            while time.time() - start_time < self.lock_timeout:
                try:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_acquired = True
                    break
                except IOError:
                    time.sleep(0.1)
            
            if not lock_acquired:
                raise MetadataFileError(f"Could not acquire lock for {file_path} within {self.lock_timeout} seconds")
            
            yield file_handle
            
        finally:
            if file_handle:
                if lock_acquired:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
                file_handle.close()
    
    def _create_backup(self) -> Optional[Path]:
        """
        Create a backup of the current metadata file.
        
        Returns:
            Optional[Path]: Path to backup file or None if failed
        """
        if not self.metadata_file.exists():
            return None
        
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.backup_dir / f"metadata_backup_{timestamp}.json"
            
            shutil.copy2(self.metadata_file, backup_path)
            self.logger.debug(f"Created backup: {backup_path}")
            
            # Clean old backups (keep last 10)
            self._cleanup_old_backups()
            
            return backup_path
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return None
    
    def _cleanup_old_backups(self, keep_count: int = 10):
        """
        Remove old backup files, keeping only the most recent ones.
        
        Args:
            keep_count: Number of backups to keep
        """
        try:
            backup_files = list(self.backup_dir.glob("metadata_backup_*.json"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            for backup_file in backup_files[keep_count:]:
                backup_file.unlink()
                self.logger.debug(f"Removed old backup: {backup_file}")
                
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old backups: {e}")
    
    def _load_from_file(self) -> MetadataFile:
        """
        Load metadata from file with validation.
        
        Returns:
            MetadataFile: Loaded and validated metadata
            
        Raises:
            MetadataFileError: If file operations fail
            MetadataValidationError: If validation fails
        """
        if not self.metadata_file.exists():
            self.logger.info("Metadata file does not exist, creating default")
            return self._create_default_metadata()
        
        try:
            with self._file_lock(self.metadata_file, 'r') as f:
                data = json.load(f)
                metadata = MetadataFile(**data)
                self.logger.debug(f"Loaded metadata with {len(metadata.sensors)} sensors")
                return metadata
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in metadata file: {e}")
            return self._recover_from_backup()
            
        except Exception as e:
            self.logger.error(f"Failed to load metadata: {e}")
            raise MetadataFileError(f"Failed to load metadata: {e}")
    
    def _save_to_file(self, metadata: MetadataFile):
        """
        Save metadata to file with backup.
        
        Args:
            metadata: Metadata to save
            
        Raises:
            MetadataFileError: If save operation fails
        """
        try:
            # Create backup before saving
            self._create_backup()
            
            # Update timestamp
            metadata.update_timestamp()
            
            # Write to temporary file first
            temp_file = self.metadata_file.with_suffix('.tmp')
            
            with self._file_lock(temp_file, 'w') as f:
                json.dump(
                    metadata.dict(),
                    f,
                    indent=2,
                    default=str,
                    ensure_ascii=False
                )
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic move
            temp_file.replace(self.metadata_file)
            self.logger.debug(f"Saved metadata with {len(metadata.sensors)} sensors")
            
        except Exception as e:
            self.logger.error(f"Failed to save metadata: {e}")
            # Clean up temp file if it exists
            temp_file = self.metadata_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            raise MetadataFileError(f"Failed to save metadata: {e}")
    
    def _create_default_metadata(self) -> MetadataFile:
        """
        Create default metadata file.
        
        Returns:
            MetadataFile: Default metadata
        """
        influxdb_config = InfluxDBConfig(
            host=self.config.influxdb_host,
            port=self.config.influxdb_port,
            bucket=self.config.influxdb_bucket,
            org=self.config.influxdb_org,
            token=self.config.influxdb_token,
            timeout=self.config.influxdb_timeout,
            verify_ssl=self.config.influxdb_verify_ssl,
            enable_gzip=self.config.influxdb_enable_gzip
        )
        
        app_config = AppConfig(
            scan_interval=self.config.ble_scan_interval,
            batch_size=self.config.influxdb_batch_size,
            log_level=self.config.log_level,
            max_buffer_size=self.config.max_buffer_size,
            enable_auto_discovery=self.config.enable_auto_discovery,
            performance_monitoring=self.config.performance_monitoring
        )
        
        metadata = create_default_metadata(influxdb_config)
        metadata.config = app_config
        
        # Save the default metadata
        self._save_to_file(metadata)
        
        return metadata
    
    def _recover_from_backup(self) -> MetadataFile:
        """
        Attempt to recover metadata from backup files.
        
        Returns:
            MetadataFile: Recovered metadata or default if no valid backup
        """
        self.logger.warning("Attempting to recover from backup files")
        
        backup_files = list(self.backup_dir.glob("metadata_backup_*.json"))
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for backup_file in backup_files:
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    metadata = MetadataFile(**data)
                    
                self.logger.info(f"Successfully recovered from backup: {backup_file}")
                
                # Save recovered data as current
                self._save_to_file(metadata)
                return metadata
                
            except Exception as e:
                self.logger.warning(f"Failed to recover from {backup_file}: {e}")
                continue
        
        self.logger.error("No valid backup found, creating default metadata")
        return self._create_default_metadata()
    
    def load(self) -> MetadataFile:
        """
        Load metadata from file or cache.
        
        Returns:
            MetadataFile: Current metadata
        """
        if self._metadata is None:
            self._metadata = self._load_from_file()
        return self._metadata
    
    def save(self):
        """
        Save current metadata to file.
        
        Raises:
            MetadataError: If no metadata is loaded
        """
        if self._metadata is None:
            raise MetadataError("No metadata loaded to save")
        
        self._save_to_file(self._metadata)
    
    def reload(self) -> MetadataFile:
        """
        Force reload metadata from file.
        
        Returns:
            MetadataFile: Reloaded metadata
        """
        self._metadata = self._load_from_file()
        return self._metadata
    
    def add_sensor(self, mac_address: str, name: str, location: str = "") -> SensorMetadata:
        """
        Add a new sensor to the metadata.
        
        Args:
            mac_address: MAC address of the sensor
            name: Human-readable name for the sensor
            location: Physical location of the sensor
            
        Returns:
            SensorMetadata: The created sensor metadata
            
        Raises:
            MetadataValidationError: If MAC address is invalid or sensor already exists
        """
        try:
            mac_address = normalize_mac_address(mac_address)
        except ValueError as e:
            raise MetadataValidationError(f"Invalid MAC address: {e}")
        
        metadata = self.load()
        
        if mac_address in metadata.sensors:
            raise MetadataValidationError(f"Sensor with MAC {mac_address} already exists")
        
        sensor = metadata.add_sensor(mac_address, name, location)
        self.save()
        
        self.logger.info(f"Added sensor: {name} ({mac_address}) at {location}")
        return sensor
    
    def update_sensor(self, mac_address: str, **kwargs) -> Optional[SensorMetadata]:
        """
        Update sensor metadata.
        
        Args:
            mac_address: MAC address of the sensor
            **kwargs: Fields to update
            
        Returns:
            Optional[SensorMetadata]: Updated sensor metadata or None if not found
        """
        try:
            mac_address = normalize_mac_address(mac_address)
        except ValueError as e:
            raise MetadataValidationError(f"Invalid MAC address: {e}")
        
        metadata = self.load()
        sensor = metadata.update_sensor(mac_address, **kwargs)
        
        if sensor:
            self.save()
            self.logger.info(f"Updated sensor {mac_address}: {kwargs}")
        
        return sensor
    
    def remove_sensor(self, mac_address: str) -> bool:
        """
        Remove a sensor from the metadata.
        
        Args:
            mac_address: MAC address of the sensor to remove
            
        Returns:
            bool: True if sensor was removed, False if not found
        """
        try:
            mac_address = normalize_mac_address(mac_address)
        except ValueError as e:
            raise MetadataValidationError(f"Invalid MAC address: {e}")
        
        metadata = self.load()
        removed = metadata.remove_sensor(mac_address)
        
        if removed:
            self.save()
            self.logger.info(f"Removed sensor: {mac_address}")
        
        return removed
    
    def get_sensor(self, mac_address: str) -> Optional[SensorMetadata]:
        """
        Get sensor metadata by MAC address.
        
        Args:
            mac_address: MAC address of the sensor
            
        Returns:
            Optional[SensorMetadata]: Sensor metadata or None if not found
        """
        try:
            mac_address = normalize_mac_address(mac_address)
        except ValueError:
            return None
        
        metadata = self.load()
        return metadata.sensors.get(mac_address)
    
    def get_all_sensors(self) -> Dict[str, SensorMetadata]:
        """
        Get all sensors.
        
        Returns:
            Dict[str, SensorMetadata]: All sensors by MAC address
        """
        metadata = self.load()
        return metadata.sensors.copy()
    
    def get_active_sensors(self) -> Dict[str, SensorMetadata]:
        """
        Get all active sensors.
        
        Returns:
            Dict[str, SensorMetadata]: Active sensors by MAC address
        """
        metadata = self.load()
        return metadata.get_active_sensors()
    
    def get_sensor_by_name(self, name: str) -> Optional[Tuple[str, SensorMetadata]]:
        """
        Find sensor by name.
        
        Args:
            name: Sensor name to search for
            
        Returns:
            Optional[Tuple[str, SensorMetadata]]: (MAC address, sensor metadata) or None
        """
        metadata = self.load()
        return metadata.get_sensor_by_name(name)
    
    def get_sensors_by_location(self, location: str) -> Dict[str, SensorMetadata]:
        """
        Get sensors by location.
        
        Args:
            location: Location to search for
            
        Returns:
            Dict[str, SensorMetadata]: Sensors in the specified location
        """
        metadata = self.load()
        return metadata.get_sensors_by_location(location)
    
    def update_sensor_last_seen(self, mac_address: str, timestamp: Optional[datetime] = None):
        """
        Update sensor's last seen timestamp.
        
        Args:
            mac_address: MAC address of the sensor
            timestamp: Timestamp to set (defaults to current time)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        self.update_sensor(mac_address, last_seen=timestamp)
    
    def get_stale_sensors(self, threshold_hours: int = 24) -> Dict[str, SensorMetadata]:
        """
        Get sensors that haven't been seen for a specified time.
        
        Args:
            threshold_hours: Hours threshold for considering a sensor stale
            
        Returns:
            Dict[str, SensorMetadata]: Stale sensors by MAC address
        """
        threshold = datetime.utcnow() - timedelta(hours=threshold_hours)
        metadata = self.load()
        
        stale_sensors = {}
        for mac, sensor in metadata.sensors.items():
            if sensor.last_seen and sensor.last_seen < threshold:
                stale_sensors[mac] = sensor
        
        return stale_sensors
    
    def get_config(self) -> AppConfig:
        """
        Get application configuration.
        
        Returns:
            AppConfig: Current application configuration
        """
        metadata = self.load()
        return metadata.config
    
    def update_config(self, **kwargs) -> AppConfig:
        """
        Update application configuration.
        
        Args:
            **kwargs: Configuration fields to update
            
        Returns:
            AppConfig: Updated configuration
        """
        metadata = self.load()
        
        for field, value in kwargs.items():
            if hasattr(metadata.config, field):
                setattr(metadata.config, field, value)
        
        self.save()
        self.logger.info(f"Updated configuration: {kwargs}")
        
        return metadata.config
    
    def get_influxdb_config(self) -> InfluxDBConfig:
        """
        Get InfluxDB configuration.
        
        Returns:
            InfluxDBConfig: Current InfluxDB configuration
        """
        metadata = self.load()
        return metadata.influxdb
    
    def update_influxdb_config(self, **kwargs) -> InfluxDBConfig:
        """
        Update InfluxDB configuration.
        
        Args:
            **kwargs: InfluxDB configuration fields to update
            
        Returns:
            InfluxDBConfig: Updated InfluxDB configuration
        """
        metadata = self.load()
        
        for field, value in kwargs.items():
            if hasattr(metadata.influxdb, field):
                setattr(metadata.influxdb, field, value)
        
        self.save()
        self.logger.info(f"Updated InfluxDB configuration: {kwargs}")
        
        return metadata.influxdb
    
    def export_metadata(self, export_path: Path) -> bool:
        """
        Export metadata to a specified file.
        
        Args:
            export_path: Path to export the metadata
            
        Returns:
            bool: True if export successful
        """
        try:
            metadata = self.load()
            
            with open(export_path, 'w') as f:
                json.dump(
                    metadata.dict(),
                    f,
                    indent=2,
                    default=str,
                    ensure_ascii=False
                )
            
            self.logger.info(f"Exported metadata to: {export_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export metadata: {e}")
            return False
    
    def import_metadata(self, import_path: Path, merge: bool = False) -> bool:
        """
        Import metadata from a specified file.
        
        Args:
            import_path: Path to import the metadata from
            merge: If True, merge with existing data; if False, replace
            
        Returns:
            bool: True if import successful
        """
        try:
            with open(import_path, 'r') as f:
                data = json.load(f)
                imported_metadata = MetadataFile(**data)
            
            if merge:
                current_metadata = self.load()
                # Merge sensors
                current_metadata.sensors.update(imported_metadata.sensors)
                # Update configuration if newer
                if imported_metadata.last_updated > current_metadata.last_updated:
                    current_metadata.config = imported_metadata.config
                    current_metadata.influxdb = imported_metadata.influxdb
            else:
                self._metadata = imported_metadata
            
            self.save()
            self.logger.info(f"Imported metadata from: {import_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to import metadata: {e}")
            return False