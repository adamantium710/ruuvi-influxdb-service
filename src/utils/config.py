"""
Configuration management for the Ruuvi Sensor Service.
Loads configuration from environment variables with validation and defaults.
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union
from dotenv import load_dotenv
import logging


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class Config:
    """
    Configuration manager that loads settings from environment variables.
    Provides validation and type conversion for configuration values.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            env_file: Path to .env file (defaults to .env in project root)
        """
        self.logger = logging.getLogger(__name__)
        
        # Load environment variables
        if env_file is None:
            env_file = Path(__file__).parent.parent.parent / ".env"
        
        if Path(env_file).exists():
            load_dotenv(env_file)
            self.logger.info(f"Loaded configuration from {env_file}")
        else:
            self.logger.warning(f"Environment file {env_file} not found, using system environment")
        
        # Validate virtual environment if required
        if self.get_bool("VIRTUAL_ENV_REQUIRED", True):
            self._check_virtual_environment()
    
    def _check_virtual_environment(self):
        """Check if running in a virtual environment."""
        if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            if 'VIRTUAL_ENV' not in os.environ:
                raise ConfigurationError(
                    "Virtual environment required but not detected. "
                    "Please activate the virtual environment or set VIRTUAL_ENV_REQUIRED=false"
                )
    
    def get_str(self, key: str, default: Optional[str] = None) -> str:
        """Get string configuration value."""
        value = os.getenv(key, default)
        if value is None:
            raise ConfigurationError(f"Required configuration key '{key}' not found")
        return value
    
    def get_int(self, key: str, default: Optional[int] = None) -> int:
        """Get integer configuration value."""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ConfigurationError(f"Required configuration key '{key}' not found")
            return default
        
        try:
            return int(value)
        except ValueError:
            raise ConfigurationError(f"Configuration key '{key}' must be an integer, got '{value}'")
    
    def get_float(self, key: str, default: Optional[float] = None) -> float:
        """Get float configuration value."""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ConfigurationError(f"Required configuration key '{key}' not found")
            return default
        
        try:
            return float(value)
        except ValueError:
            raise ConfigurationError(f"Configuration key '{key}' must be a float, got '{value}'")
    
    def get_bool(self, key: str, default: Optional[bool] = None) -> bool:
        """Get boolean configuration value."""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ConfigurationError(f"Required configuration key '{key}' not found")
            return default
        
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    
    def get_path(self, key: str, default: Optional[Union[str, Path]] = None) -> Path:
        """Get path configuration value."""
        value = os.getenv(key)
        if value is None:
            if default is None:
                raise ConfigurationError(f"Required configuration key '{key}' not found")
            value = str(default)
        
        path = Path(value)
        if not path.is_absolute():
            # Make relative paths relative to project root
            project_root = Path(__file__).parent.parent.parent
            path = project_root / path
        
        return path
    
    # InfluxDB Configuration
    @property
    def influxdb_host(self) -> str:
        return self.get_str("INFLUXDB_HOST")
    
    @property
    def influxdb_port(self) -> int:
        return self.get_int("INFLUXDB_PORT", 8086)
    
    @property
    def influxdb_token(self) -> str:
        return self.get_str("INFLUXDB_TOKEN")
    
    @property
    def influxdb_org(self) -> str:
        return self.get_str("INFLUXDB_ORG")
    
    @property
    def influxdb_bucket(self) -> str:
        return self.get_str("INFLUXDB_BUCKET")
    
    @property
    def influxdb_timeout(self) -> int:
        return self.get_int("INFLUXDB_TIMEOUT", 30)
    
    @property
    def influxdb_verify_ssl(self) -> bool:
        return self.get_bool("INFLUXDB_VERIFY_SSL", True)
    
    @property
    def influxdb_enable_gzip(self) -> bool:
        return self.get_bool("INFLUXDB_ENABLE_GZIP", True)
    
    # BLE Scanner Configuration
    @property
    def ble_scan_timeout(self) -> float:
        return self.get_float("BLE_SCAN_TIMEOUT", 10.0)
    
    @property
    def ble_retry_attempts(self) -> int:
        return self.get_int("BLE_RETRY_ATTEMPTS", 3)
    
    @property
    def ble_retry_delay(self) -> float:
        return self.get_float("BLE_RETRY_DELAY", 2.0)
    
    @property
    def ble_scan_interval(self) -> int:
        return self.get_int("BLE_SCAN_INTERVAL", 20)
    
    # Metadata Configuration
    @property
    def metadata_file_path(self) -> Path:
        return self.get_path("METADATA_FILE_PATH", "./config/ruuvi_sensors.json")
    
    @property
    def metadata_backup_count(self) -> int:
        return self.get_int("METADATA_BACKUP_COUNT", 5)
    
    # Logging Configuration
    @property
    def log_level(self) -> str:
        return self.get_str("LOG_LEVEL", "INFO").upper()
    
    @property
    def log_dir(self) -> Path:
        return self.get_path("LOG_DIR", "./logs")
    
    @property
    def log_max_file_size(self) -> int:
        return self.get_int("LOG_MAX_FILE_SIZE", 10 * 1024 * 1024)  # 10MB
    
    @property
    def log_backup_count(self) -> int:
        return self.get_int("LOG_BACKUP_COUNT", 5)
    
    @property
    def log_enable_console(self) -> bool:
        return self.get_bool("LOG_ENABLE_CONSOLE", True)
    
    @property
    def log_enable_syslog(self) -> bool:
        return self.get_bool("LOG_ENABLE_SYSLOG", False)
    
    # Service Configuration
    @property
    def service_batch_size(self) -> int:
        return self.get_int("SERVICE_BATCH_SIZE", 100)
    
    @property
    def service_flush_interval(self) -> int:
        return self.get_int("SERVICE_FLUSH_INTERVAL", 10)
    
    @property
    def service_max_retries(self) -> int:
        return self.get_int("SERVICE_MAX_RETRIES", 3)
    
    @property
    def service_retry_backoff(self) -> float:
        return self.get_float("SERVICE_RETRY_BACKOFF", 2.0)
    
    @property
    def service_buffer_size(self) -> int:
        return self.get_int("SERVICE_BUFFER_SIZE", 10000)
    
    # Performance Monitoring
    @property
    def enable_performance_monitoring(self) -> bool:
        return self.get_bool("ENABLE_PERFORMANCE_MONITORING", True)
    
    @property
    def performance_log_interval(self) -> int:
        return self.get_int("PERFORMANCE_LOG_INTERVAL", 300)
    
    def validate_configuration(self) -> bool:
        """
        Validate all configuration values.
        
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []
        
        # Validate InfluxDB configuration
        try:
            if not self.influxdb_host:
                errors.append("INFLUXDB_HOST cannot be empty")
            if not self.influxdb_token or self.influxdb_token == "your_influxdb_token_here":
                errors.append("INFLUXDB_TOKEN must be set to a valid token")
            if not self.influxdb_org or self.influxdb_org == "your_organization_name":
                errors.append("INFLUXDB_ORG must be set to a valid organization name")
            if not self.influxdb_bucket:
                errors.append("INFLUXDB_BUCKET cannot be empty")
            if self.influxdb_port < 1 or self.influxdb_port > 65535:
                errors.append("INFLUXDB_PORT must be between 1 and 65535")
        except ConfigurationError as e:
            errors.append(str(e))
        
        # Validate BLE configuration
        try:
            if self.ble_scan_timeout <= 0:
                errors.append("BLE_SCAN_TIMEOUT must be positive")
            if self.ble_retry_attempts < 1:
                errors.append("BLE_RETRY_ATTEMPTS must be at least 1")
            if self.ble_retry_delay < 0:
                errors.append("BLE_RETRY_DELAY cannot be negative")
        except ConfigurationError as e:
            errors.append(str(e))
        
        # Validate log level
        try:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if self.log_level not in valid_levels:
                errors.append(f"LOG_LEVEL must be one of {valid_levels}")
        except ConfigurationError as e:
            errors.append(str(e))
        
        # Validate weather configuration if enabled
        if self.weather_enabled:
            try:
                if self.weather_location_latitude < -90 or self.weather_location_latitude > 90:
                    errors.append("WEATHER_LOCATION_LATITUDE must be between -90 and 90")
                if self.weather_location_longitude < -180 or self.weather_location_longitude > 180:
                    errors.append("WEATHER_LOCATION_LONGITUDE must be between -180 and 180")
                if self.weather_api_timeout <= 0:
                    errors.append("WEATHER_API_TIMEOUT must be positive")
                if self.weather_api_retry_attempts < 1:
                    errors.append("WEATHER_API_RETRY_ATTEMPTS must be at least 1")
                if self.weather_forecast_interval <= 0:
                    errors.append("WEATHER_FORECAST_INTERVAL must be positive")
                if self.weather_forecast_days < 1 or self.weather_forecast_days > 16:
                    errors.append("WEATHER_FORECAST_DAYS must be between 1 and 16")
            except ConfigurationError as e:
                errors.append(str(e))
        
        if errors:
            raise ConfigurationError("Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        
        return True
    
    def get_summary(self) -> dict:
        """Get configuration summary for logging/debugging."""
        summary = {
            'influxdb': {
                'host': self.influxdb_host,
                'port': self.influxdb_port,
                'org': self.influxdb_org,
                'bucket': self.influxdb_bucket,
                'verify_ssl': self.influxdb_verify_ssl,
                'enable_gzip': self.influxdb_enable_gzip,
            },
            'ble': {
                'scan_timeout': self.ble_scan_timeout,
                'retry_attempts': self.ble_retry_attempts,
                'retry_delay': self.ble_retry_delay,
                'scan_interval': self.ble_scan_interval,
            },
            'metadata': {
                'file_path': str(self.metadata_file_path),
                'backup_count': self.metadata_backup_count,
            },
            'logging': {
                'level': self.log_level,
                'dir': str(self.log_dir),
                'enable_console': self.log_enable_console,
                'enable_syslog': self.log_enable_syslog,
            },
            'service': {
                'batch_size': self.service_batch_size,
                'flush_interval': self.service_flush_interval,
                'max_retries': self.service_max_retries,
                'buffer_size': self.service_buffer_size,
            }
        }
        
        # Add weather configuration if enabled
        if self.weather_enabled:
            summary['weather'] = {
                'enabled': self.weather_enabled,
                'location': {
                    'latitude': self.weather_location_latitude,
                    'longitude': self.weather_location_longitude,
                    'timezone': self.weather_timezone,
                },
                'api': {
                    'base_url': self.weather_api_base_url,
                    'timeout': self.weather_api_timeout,
                    'retry_attempts': self.weather_api_retry_attempts,
                    'rate_limit': self.weather_api_rate_limit_requests,
                },
                'storage': {
                    'bucket': self.weather_influxdb_bucket,
                },
                'scheduling': {
                    'forecast_interval': self.weather_forecast_interval,
                    'forecast_days': self.weather_forecast_days,
                    'historical_days': self.weather_historical_days,
                }
            }
        
        return summary
    
    def validate_environment(self):
        """Validate environment and configuration."""
        return self.validate_configuration()
    
    def is_virtual_environment(self) -> bool:
        """Check if running in a virtual environment."""
        return (hasattr(sys, 'real_prefix') or
                (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
                'VIRTUAL_ENV' in os.environ)
    
    @property
    def environment(self) -> str:
        """Get current environment."""
        return self.get_str("ENVIRONMENT", "development")
    
    @property
    def ble_adapter(self) -> str:
        """Get BLE adapter."""
        return self.get_str("BLE_ADAPTER", "auto")
    
    @property
    def ble_scan_duration(self) -> float:
        """Get BLE scan duration."""
        return self.get_float("BLE_SCAN_DURATION", 10.0)
    
    @property
    def metadata_file(self) -> str:
        """Get metadata file path."""
        return str(self.get_path("METADATA_FILE", "./data/metadata.json"))
    
    @property
    def backup_dir(self) -> str:
        """Get backup directory path."""
        return str(self.get_path("BACKUP_DIR", "./backups"))
    
    @property
    def influxdb_batch_size(self) -> int:
        """Get InfluxDB batch size."""
        return self.get_int("INFLUXDB_BATCH_SIZE", 100)
    
    @property
    def influxdb_flush_interval(self) -> int:
        """Get InfluxDB flush interval."""
        return self.get_int("INFLUXDB_FLUSH_INTERVAL", 10)
    
    @property
    def influxdb_retry_attempts(self) -> int:
        """Get InfluxDB retry attempts."""
        return self.get_int("INFLUXDB_RETRY_ATTEMPTS", 3)
    
    @property
    def influxdb_retry_delay(self) -> float:
        """Get InfluxDB retry delay."""
        return self.get_float("INFLUXDB_RETRY_DELAY", 2.0)
    
    @property
    def influxdb_retry_exponential_base(self) -> float:
        """Get InfluxDB retry exponential base."""
        return self.get_float("INFLUXDB_RETRY_EXPONENTIAL_BASE", 2.0)
    
    @property
    def max_buffer_size(self) -> int:
        """Get maximum buffer size."""
        return self.get_int("MAX_BUFFER_SIZE", 10000)
    
    @property
    def enable_auto_discovery(self) -> bool:
        """Get auto discovery setting."""
        return self.get_bool("ENABLE_AUTO_DISCOVERY", True)
    
    @property
    def performance_monitoring(self) -> bool:
        """Get performance monitoring setting."""
        return self.get_bool("PERFORMANCE_MONITORING", True)
    
    # Weather Configuration
    @property
    def weather_enabled(self) -> bool:
        """Get weather forecast enabled setting."""
        return self.get_bool("WEATHER_ENABLED", False)
    
    @property
    def weather_location_latitude(self) -> float:
        """Get weather location latitude (Planegg coordinates)."""
        return self.get_float("WEATHER_LOCATION_LATITUDE", 48.1031)
    
    @property
    def weather_location_longitude(self) -> float:
        """Get weather location longitude (Planegg coordinates)."""
        return self.get_float("WEATHER_LOCATION_LONGITUDE", 11.4247)
    
    @property
    def weather_api_base_url(self) -> str:
        """Get weather API base URL."""
        return self.get_str("WEATHER_API_BASE_URL", "https://api.open-meteo.com/v1")
    
    @property
    def weather_api_timeout(self) -> int:
        """Get weather API timeout in seconds."""
        return self.get_int("WEATHER_API_TIMEOUT", 30)
    
    @property
    def weather_api_retry_attempts(self) -> int:
        """Get weather API retry attempts."""
        return self.get_int("WEATHER_API_RETRY_ATTEMPTS", 3)
    
    @property
    def weather_api_retry_delay(self) -> float:
        """Get weather API retry delay in seconds."""
        return self.get_float("WEATHER_API_RETRY_DELAY", 2.0)
    
    @property
    def weather_api_rate_limit_requests(self) -> int:
        """Get weather API rate limit requests per minute."""
        return self.get_int("WEATHER_API_RATE_LIMIT_REQUESTS", 10)
    
    @property
    def weather_influxdb_bucket(self) -> str:
        """Get weather InfluxDB bucket name."""
        return self.get_str("WEATHER_INFLUXDB_BUCKET", "weather_forecasts")
    
    @property
    def weather_forecast_interval(self) -> int:
        """Get weather forecast fetch interval in minutes."""
        return self.get_int("WEATHER_FORECAST_INTERVAL", 60)
    
    @property
    def weather_forecast_days(self) -> int:
        """Get number of forecast days to retrieve."""
        return self.get_int("WEATHER_FORECAST_DAYS", 7)
    
    @property
    def weather_historical_days(self) -> int:
        """Get number of historical days to retrieve."""
        return self.get_int("WEATHER_HISTORICAL_DAYS", 7)
    
    @property
    def weather_circuit_breaker_failure_threshold(self) -> int:
        """Get circuit breaker failure threshold."""
        return self.get_int("WEATHER_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5)
    
    @property
    def weather_circuit_breaker_recovery_timeout(self) -> int:
        """Get circuit breaker recovery timeout in seconds."""
        return self.get_int("WEATHER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 300)
    
    @property
    def weather_timezone(self) -> str:
        """Get weather timezone."""
        return self.get_str("WEATHER_TIMEZONE", "Europe/Berlin")


# Global configuration instance
config = Config()