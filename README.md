# Ruuvi Sensor Service with Weather Forecast Analysis

A comprehensive Python application for monitoring Ruuvi environmental sensors via Bluetooth Low Energy (BLE) and storing data in InfluxDB, enhanced with **Phase 2 Weather Forecast Analysis System** for advanced environmental data correlation and forecast accuracy tracking.

## 🌟 Features

### Core Functionality
- **Bluetooth Low Energy (BLE) Scanning**: Automatic discovery and monitoring of Ruuvi sensors
- **InfluxDB Integration**: High-performance time-series data storage with automatic retention policies
- **Real-time Monitoring**: Live sensor data collection with configurable intervals
- **Metadata Management**: Comprehensive sensor information tracking and validation
- **Service Management**: Systemd integration for production deployment

### ✨ Phase 2 Weather Forecast Analysis System
- **🌤️ Weather Forecast Integration**: Open-Meteo and OpenWeatherMap API support
- **📊 Forecast Accuracy Tracking**: Automated error calculation and bias analysis
- **🔍 Advanced Data Analysis**: Automated profiling and association rule mining
- **📈 Grafana Dashboard Support**: Complete visualization configuration guidance
- **⚡ Automated Orchestration**: Systemd-scheduled workflow execution
- **🎯 Production Ready**: Comprehensive monitoring, health checks, and error handling

### Advanced Features
- **Interactive Setup Wizard**: Guided configuration for new installations
- **Data Export/Import**: Multiple format support (JSON, CSV, InfluxDB)
- **Sensor Testing & Calibration**: Comprehensive diagnostic tools
- **Batch Operations**: Multi-sensor management capabilities
- **Real-time Dashboard**: Live monitoring interface
- **Historical Data Retrieval**: ✅ **FULLY IMPLEMENTED** - Complete GATT protocol implementation for accessing stored sensor data
- **Edge Case Handling**: Robust error recovery and system resilience

### Production Ready
- **Comprehensive Error Handling**: Graceful recovery from hardware and network failures
- **Performance Monitoring**: Built-in metrics and resource usage tracking
- **Professional Logging**: Structured logging with multiple output formats
- **Configuration Validation**: Extensive validation with helpful error messages
- **Security Features**: Permission management and secure credential handling

## 📋 Requirements

### System Requirements
- **Operating System**: Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+)
- **Python**: 3.8 or higher (3.9+ recommended for Phase 2 features)
- **Bluetooth**: Bluetooth 4.0+ adapter with BLE support
- **Memory**: Minimum 512MB RAM (1GB+ recommended for weather analysis)
- **Storage**: 1GB+ free space for application, logs, and reports

### Dependencies
- **InfluxDB**: 2.x (required for Phase 2 weather features)
- **Python Packages**: See `requirements.txt`
- **System Packages**: `bluetooth`, `bluez`, `python3-dev`

### Phase 2 Additional Requirements
- **Weather APIs**: Open-Meteo (free) or OpenWeatherMap (API key required)
- **Grafana**: 8.0+ for dashboard visualization (optional but recommended)
- **Systemd**: For automated scheduling and service management

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ruuvi-sensor-service.git
cd ruuvi-sensor-service

# Run the installation script
sudo ./install.sh
```

### 2. Configuration

#### Basic Sensor Configuration
```bash
# Run the interactive setup wizard
python main.py --setup-wizard

# Or manually edit the configuration
cp .env.sample .env
nano .env
```

#### Phase 2 Weather Configuration
```bash
# Copy weather configuration template
cp .env.weather.sample .env.weather

# Edit weather settings
nano .env.weather
```

**Essential Weather Configuration**:
```bash
# Enable weather forecast functionality
WEATHER_ENABLED=true

# Location coordinates (adjust for your location)
WEATHER_LOCATION_LATITUDE=52.5200
WEATHER_LOCATION_LONGITUDE=13.4050
WEATHER_TIMEZONE=Europe/Berlin

# InfluxDB Configuration
INFLUXDB_URL=http://192.168.1.100:8086
INFLUXDB_TOKEN=your_influxdb_token_here
INFLUXDB_ORG=your_organization
INFLUXDB_BUCKET=ruuvi_sensors
WEATHER_INFLUXDB_BUCKET=weather_forecasts

# Optional: OpenWeatherMap API (for enhanced features)
OPENWEATHER_API_KEY=your_api_key_here
```

### 3. Start Services

#### Core Sensor Service
```bash
# Start the sensor service
sudo systemctl start ruuvi-sensor
sudo systemctl enable ruuvi-sensor

# Or run interactively
python main.py
```

#### Phase 2 Weather Service
```bash
# Install and enable weather forecast service
sudo ./scripts/install_weather_service.sh --enable

# Check service status
sudo systemctl status weather-forecast.service
sudo systemctl status weather-forecast.timer

# View logs
sudo journalctl -u weather-forecast.service -f
```

## 📖 Detailed Installation

### Manual Installation

1. **Install System Dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip python3-dev bluetooth bluez

   # CentOS/RHEL
   sudo yum install python3 python3-pip python3-devel bluez
   ```

2. **Install Python Dependencies**:
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure Bluetooth**:
   ```bash
   # Enable Bluetooth service
   sudo systemctl enable bluetooth
   sudo systemctl start bluetooth
   
   # Add user to bluetooth group
   sudo usermod -a -G bluetooth $USER
   ```

4. **Setup InfluxDB 2.x** (Choose one option):

   **Option A: Local Installation**
   ```bash
   # Ubuntu/Debian
   wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
   echo "deb https://repos.influxdata.com/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
   sudo apt update
   sudo apt install influxdb2
   sudo systemctl enable influxdb
   sudo systemctl start influxdb
   
   # Initial setup
   influx setup
   ```

   **Option B: Docker Container**
   ```bash
   # Run InfluxDB in Docker
   docker run -d \
     --name influxdb \
     -p 8086:8086 \
     -v influxdb-storage:/var/lib/influxdb2 \
     -v influxdb-config:/etc/influxdb2 \
     influxdb:2.7
   
   # Setup via web UI at http://localhost:8086
   ```

   **Option C: Remote InfluxDB Server**
   - Use an existing InfluxDB server on your network
   - Configure connection details in the `.env` file
   - No local installation required

5. **Create InfluxDB Buckets**:
   ```bash
   # Create weather forecasts bucket (adjust command for your setup)
   influx bucket create -n weather_forecasts -o your_organization -r 90d
   
   # Verify buckets
   influx bucket list
   ```

### Configuration Options

#### Core Sensor Configuration

The application uses environment variables for configuration. Copy `.env.sample` to `.env` and customize:

```bash
# InfluxDB Configuration
INFLUXDB_HOST=localhost
INFLUXDB_PORT=8086
INFLUXDB_DATABASE=ruuvi_sensors
INFLUXDB_USERNAME=
INFLUXDB_PASSWORD=

# BLE Scanner Configuration
BLE_SCAN_INTERVAL=10
BLE_SCAN_TIMEOUT=5
BLE_ADAPTER_ID=0

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=logs/ruuvi_sensor.log
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5

# Service Configuration
SERVICE_NAME=ruuvi-sensor
METADATA_FILE=data/sensor_metadata.json
```

#### Phase 2 Weather Configuration

Complete weather configuration options in `.env.weather`:

```bash
# Weather API Configuration
WEATHER_API_BASE_URL=https://api.open-meteo.com/v1
WEATHER_API_TIMEOUT=30
WEATHER_API_RETRY_ATTEMPTS=3
WEATHER_API_RETRY_DELAY=2.0
WEATHER_API_RATE_LIMIT_REQUESTS=10

# Forecast Scheduling
WEATHER_FORECAST_INTERVAL=60
WEATHER_FORECAST_DAYS=7
WEATHER_HISTORICAL_DAYS=7

# Circuit Breaker Configuration
WEATHER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
WEATHER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300
```

## 🎯 Usage

### Interactive CLI

Run the main application to access the interactive menu:

```bash
python main.py
```

**Main Menu Options:**
1. **List Known Sensors** - View all registered sensors
2. **Discover New Sensors** - Scan for nearby Ruuvi sensors
3. **Start Monitoring** - Begin real-time data collection
4. **Service Management** - Control systemd service
5. **Configuration** - View current settings
6. **Statistics** - System performance metrics
7. **Advanced Features** - Access advanced tools
8. **Setup Wizard** - Interactive configuration
9. **Exit** - Close application

### Phase 2 Weather Operations

#### Manual Weather Workflow Execution
```bash
# Run complete weather forecast workflow once
python scripts/weather_forecast_main.py --once

# Run in continuous mode (for testing)
python scripts/weather_forecast_main.py

# Enable debug logging
export LOG_LEVEL=DEBUG
python scripts/weather_forecast_main.py --once
```

#### Health Monitoring
```bash
# Comprehensive health check
./scripts/weather_service_health_check.py

# JSON output for monitoring systems
./scripts/weather_service_health_check.py --json

# Check specific components
./scripts/weather_service_health_check.py --component api
./scripts/weather_service_health_check.py --component storage
./scripts/weather_service_health_check.py --component accuracy
```

#### Component Testing
```bash
# Test weather API connectivity
python scripts/test_weather_infrastructure.py

# Test forecast accuracy calculation
python scripts/test_forecast_accuracy.py

# Test data analysis features
python scripts/test_weather_analysis.py

# Test complete integration
python scripts/test_orchestrator_integration.py
```

### Advanced Features

Access advanced functionality through the CLI menu:

#### Data Export/Import
- Export sensor data in JSON, CSV, or InfluxDB format
- Import data from backup files
- Automated backup scheduling

#### Sensor Testing & Calibration
- **Signal Strength Test**: Measure BLE signal quality
- **Data Consistency Test**: Validate sensor readings
- **Range Validation Test**: Check measurement ranges
- **Battery Health Test**: Monitor sensor battery levels
- **Response Time Test**: Measure sensor responsiveness

#### Batch Operations
- Update multiple sensors simultaneously
- Export data from multiple sensors
- Run diagnostic tests on sensor groups

#### Real-time Dashboard
- Live sensor data visualization
- Performance metrics monitoring
- System health indicators

#### Historical Data Retrieval ✅ **FULLY IMPLEMENTED**
- **Complete GATT Protocol**: Full implementation of Ruuvi GATT service with UUIDs `6E400001-B5A3-F393-E0A9-E50E24DCCA9E`
- **Advanced Command System**: Support for GET_CAPABILITIES, GET_HISTORICAL_DATA, ACKNOWLEDGE_CHUNK commands
- **Intelligent Capability Detection**: Automatic firmware feature detection and historical data support verification
- **Efficient Chunked Transfer**: Robust handling of large datasets with 16-24 byte records and progress tracking
- **Binary Data Parsing**: Native parsing of compressed historical format with timestamp reconstruction
- **Flexible Time Ranges**: Configurable retrieval periods from hours to weeks with Unix timestamp precision
- **Real-time Progress Monitoring**: Live transfer progress with chunk acknowledgments and timeout handling
- **Production-Ready Error Recovery**: Comprehensive retry logic, connection management, and graceful failure handling
- **Seamless Data Integration**: Direct conversion to RuuviSensorData format for InfluxDB compatibility

### Command Line Interface

The application supports direct command-line operations:

```bash
# Run setup wizard
python main.py --setup-wizard

# Start monitoring (non-interactive)
python main.py --monitor

# Export data
python main.py --export --format json --output backup.json

# Run sensor tests
python main.py --test --sensor AA:BB:CC:DD:EE:FF

# Retrieve historical data
python main.py --historical --sensor AA:BB:CC:DD:EE:FF --hours 24

# Show system status
python main.py --status
```

### Service Management

Control the systemd services:

#### Core Sensor Service
```bash
# Start service
sudo systemctl start ruuvi-sensor

# Stop service
sudo systemctl stop ruuvi-sensor

# Enable auto-start
sudo systemctl enable ruuvi-sensor

# Check status
sudo systemctl status ruuvi-sensor

# View logs
sudo journalctl -u ruuvi-sensor -f
```

#### Phase 2 Weather Service
```bash
# Check service and timer status
sudo systemctl status weather-forecast.service
sudo systemctl status weather-forecast.timer

# View logs
sudo journalctl -u weather-forecast.service -f
sudo journalctl -u weather-forecast.timer -f

# Manual execution
sudo systemctl start weather-forecast.service

# Stop/restart timer
sudo systemctl stop weather-forecast.timer
sudo systemctl restart weather-forecast.timer
```

## 🔧 Configuration

### Environment Variables

#### Core System Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `INFLUXDB_HOST` | InfluxDB server hostname | localhost | Yes |
| `INFLUXDB_PORT` | InfluxDB server port | 8086 | Yes |
| `INFLUXDB_DATABASE` | Database name | ruuvi_sensors | Yes |
| `INFLUXDB_USERNAME` | Database username | | No |
| `INFLUXDB_PASSWORD` | Database password | | No |
| `BLE_SCAN_INTERVAL` | Scan interval in seconds | 10 | No |
| `BLE_SCAN_TIMEOUT` | Scan timeout in seconds | 5 | No |
| `BLE_ADAPTER_ID` | Bluetooth adapter ID | 0 | No |
| `LOG_LEVEL` | Logging level | INFO | No |
| `LOG_FILE` | Log file path | logs/ruuvi_sensor.log | No |

#### Phase 2 Weather Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `WEATHER_ENABLED` | Enable weather functionality | false | Yes |
| `WEATHER_LOCATION_LATITUDE` | Location latitude | 52.5200 | Yes |
| `WEATHER_LOCATION_LONGITUDE` | Location longitude | 13.4050 | Yes |
| `WEATHER_TIMEZONE` | Timezone identifier | Europe/Berlin | Yes |
| `INFLUXDB_URL` | InfluxDB 2.x URL | http://localhost:8086 | Yes |
| `INFLUXDB_TOKEN` | InfluxDB authentication token | | Yes |
| `INFLUXDB_ORG` | InfluxDB organization | | Yes |
| `WEATHER_INFLUXDB_BUCKET` | Weather data bucket | weather_forecasts | Yes |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | | No |

### Sensor Metadata

Sensors are automatically registered in `data/sensor_metadata.json`:

```json
{
  "AA:BB:CC:DD:EE:FF": {
    "name": "Living Room",
    "location": "Indoor",
    "description": "Temperature and humidity sensor",
    "first_seen": "2024-01-01T00:00:00Z",
    "last_seen": "2024-01-01T12:00:00Z",
    "data_format": 5,
    "firmware_version": "3.31.0"
  }
}
```

## 📊 Data Schema

### InfluxDB Measurements

#### Core Sensor Data

**Measurement**: `ruuvi_measurements`

| Field | Type | Description |
|-------|------|-------------|
| `temperature` | float | Temperature in Celsius |
| `humidity` | float | Relative humidity (%) |
| `pressure` | float | Atmospheric pressure (hPa) |
| `acceleration_x` | float | X-axis acceleration (g) |
| `acceleration_y` | float | Y-axis acceleration (g) |
| `acceleration_z` | float | Z-axis acceleration (g) |
| `battery_voltage` | float | Battery voltage (V) |
| `tx_power` | int | Transmission power (dBm) |
| `movement_counter` | int | Movement detection counter |
| `measurement_sequence` | int | Measurement sequence number |

**Tags**:
- `sensor_mac`: Sensor MAC address
- `sensor_name`: Human-readable sensor name
- `location`: Sensor location
- `data_format`: Ruuvi data format version

#### Phase 2 Weather Data

**Measurement**: `weather_forecasts`

| Field | Type | Description |
|-------|------|-------------|
| `temperature` | float | Temperature in Celsius |
| `humidity` | float | Relative humidity (%) |
| `pressure` | float | Atmospheric pressure (hPa) |
| `wind_speed` | float | Wind speed (m/s) |
| `wind_direction` | float | Wind direction (degrees) |
| `precipitation` | float | Precipitation (mm) |
| `cloud_cover` | float | Cloud cover (%) |

**Tags**:
- `location_lat`: Latitude coordinate
- `location_lon`: Longitude coordinate
- `data_type`: Type of data (current, forecast, historical)
- `source`: Data source (openmeteo, openweathermap)
- `forecast_horizon_hours`: Forecast horizon (1, 6, 24, 48)
- `retrieved_at`: Timestamp when data was retrieved

**Measurement**: `weather_forecast_errors`

| Field | Type | Description |
|-------|------|-------------|
| `temp_abs_error` | float | Temperature absolute error (°C) |
| `temp_signed_error` | float | Temperature signed error (°C) |
| `pressure_abs_error` | float | Pressure absolute error (hPa) |
| `pressure_signed_error` | float | Pressure signed error (hPa) |
| `humidity_abs_error` | float | Humidity absolute error (%) |
| `humidity_signed_error` | float | Humidity signed error (%) |

**Tags**:
- `source`: Forecast data source
- `forecast_horizon_hours`: Forecast horizon

## 📈 Grafana Dashboard Configuration

### Phase 2 Dashboard Requirements

The system supports comprehensive Grafana dashboards as specified in Phase 2:

#### Dashboard 1: Live Weather & Forecast Comparison
- **Actual vs. Forecast Temperature**: Time series comparison with multiple horizons
- **Actual vs. Forecast Humidity/Pressure**: Multi-variable analysis
- **Current Forecast Table**: Real-time forecast display with horizon indicators

#### Dashboard 2: Forecast Accuracy Analysis
- **Temperature Absolute Error Over Time**: Error trends by forecast horizon
- **Temperature Signed Error (Bias) Analysis**: Bias detection and trends
- **Error Distribution Histograms**: Statistical distribution analysis
- **MAE/RMSE/Bias Statistics**: Key accuracy metrics
- **Actual vs. Forecast Scatter Plots**: Correlation analysis

### Quick Dashboard Setup

**1. Configure InfluxDB Data Source**:
- **Type**: InfluxDB
- **URL**: http://localhost:8086
- **Organization**: your_org
- **Token**: your_influxdb_token
- **Default Bucket**: weather_forecasts

**2. Import Dashboard Templates**:
```bash
# Available in examples/
examples/weather-forecast-comparison-dashboard.json
examples/weather-accuracy-analysis-dashboard.json
```

**3. Key Flux Query Examples**:

**Temperature Comparison**:
```flux
// Actual temperature
from(bucket: "ruuvi_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "ruuvi_measurements")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)

// Forecast temperature
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecasts")
  |> filter(fn: (r) => r["_field"] == "temperature")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
```

**Forecast Accuracy**:
```flux
// Mean Absolute Error
from(bucket: "weather_forecasts")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors")
  |> filter(fn: (r) => r["_field"] == "temp_abs_error")
  |> filter(fn: (r) => r["forecast_horizon_hours"] == "24")
  |> aggregateWindow(every: 6h, fn: mean, createEmpty: false)
```

For complete dashboard configuration instructions, see: **[Grafana Dashboard Guide](docs/GRAFANA_DASHBOARD_GUIDE.md)**

## 🔍 Troubleshooting

### Common Issues

#### Bluetooth Permission Errors
```bash
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER
# Logout and login again

# Or run with sudo (not recommended for production)
sudo python main.py
```

#### InfluxDB Connection Issues
```bash
# Check InfluxDB status
sudo systemctl status influxdb

# Test connection (InfluxDB 2.x)
influx ping

# Check configuration
influx auth list
```

#### No Sensors Found
```bash
# Check Bluetooth adapter
hciconfig
sudo hciconfig hci0 up

# Scan manually
sudo hcitool lescan

# Check sensor battery and proximity
```

#### Service Won't Start
```bash
# Check service logs
sudo journalctl -u ruuvi-sensor -n 50

# Verify configuration
python main.py --validate-config

# Check file permissions
ls -la /opt/ruuvi-sensor/
```

### Phase 2 Weather Troubleshooting

#### Weather Service Issues
```bash
# Check weather service status
sudo systemctl status weather-forecast.service
sudo systemctl status weather-forecast.timer

# View detailed logs
sudo journalctl -u weather-forecast.service -n 50

# Test weather API connectivity
curl "https://api.open-meteo.com/v1/forecast?latitude=52.5200&longitude=13.4050&current_weather=true"

# Run health check
./scripts/weather_service_health_check.py
```

#### Data Quality Issues
```bash
# Check data availability
influx query 'from(bucket:"weather_forecasts") |> range(start:-24h) |> count()'

# Verify forecast errors
influx query 'from(bucket:"weather_forecasts") |> range(start:-24h) |> filter(fn: (r) => r["_measurement"] == "weather_forecast_errors") |> count()'

# Test accuracy calculation
python scripts/test_forecast_accuracy.py
```

#### Performance Issues
```bash
# Monitor resource usage
htop
iotop

# Check execution times
grep "execution_time" /var/log/weather-forecast/weather-forecast.log

# Database performance
influx query 'from(bucket:"weather_forecasts") |> range(start:-1h) |> count()' --profilers
```

### Historical Data Retrieval Troubleshooting

**Diagnostic Commands:**
```bash
# Check sensor firmware compatibility and capabilities
python main.py --test --sensor AA:BB:CC:DD:EE:FF

# Verify GATT service availability with detailed logging
python main.py --scan --verbose

# Test direct BLE connection to sensor
python main.py --connect --sensor AA:BB:CC:DD:EE:FF

# Check sensor battery level (critical for historical data operations)
python main.py --battery-check --sensor AA:BB:CC:DD:EE:FF

# Enable debug logging for detailed troubleshooting
export LOG_LEVEL=DEBUG
python main.py --historical --sensor AA:BB:CC:DD:EE:FF --hours 1
```

**Common Issues and Solutions:**

| Issue | Cause | Solution |
|-------|-------|----------|
| **"Device does not support historical data"** | Firmware lacks historical storage | Update to firmware 3.31.0+ or use compatible sensor |
| **"GATT service not found"** | Sensor out of range or not advertising | Move within 5-10m, check sensor is active |
| **"Transfer timeout"** | Poor BLE connection or low battery | Improve signal quality, check battery >2.5V |
| **"Chunked transfer failed"** | Connection drops during transfer | Reduce interference, use shorter time ranges |
| **"Invalid historical record"** | Data corruption or parsing error | Check firmware compatibility, retry with shorter range |
| **"Connection failed"** | BLE adapter or permission issues | Check `hciconfig`, verify bluetooth group membership |

### Log Analysis

Logs are stored in `logs/ruuvi_sensor.log` with rotation:

```bash
# View recent logs
tail -f logs/ruuvi_sensor.log

# Search for errors
grep ERROR logs/ruuvi_sensor.log

# View service logs
sudo journalctl -u ruuvi-sensor -f

# Weather service logs
sudo journalctl -u weather-forecast.service -f
```

### Performance Monitoring

The application includes built-in performance monitoring:

```bash
# View performance metrics
python main.py --stats

# Monitor resource usage
htop
iotop

# Weather service health check
./scripts/weather_service_health_check.py
```

## 🛠️ Development

### Project Structure

```
ruuvi-sensor-service/
├── src/
│   ├── ble/                 # Bluetooth Low Energy scanner
│   ├── cli/                 # Command-line interface
│   ├── exceptions/          # Error handling and edge cases
│   ├── influxdb/           # InfluxDB client and operations
│   ├── metadata/           # Sensor metadata management
│   ├── service/            # Service management
│   ├── utils/              # Utilities and configuration
│   └── weather/            # Phase 2 weather analysis system
│       ├── api.py          # Weather API integration
│       ├── storage.py      # Weather data storage
│       ├── accuracy.py     # Forecast accuracy calculation
│       └── analysis.py     # Data analysis and reporting
├── data/                   # Data files and metadata
├── logs/                   # Log files
├── reports/                # Generated analysis reports
├── tests/                  # Unit and integration tests
├── docs/                   # Documentation
│   ├── GRAFANA_DASHBOARD_GUIDE.md    # Complete dashboard setup
│   ├── PHASE2_COMPLETE_SUMMARY.md    # Implementation summary
│   ├── WEATHER_INFRASTRUCTURE.md     # Weather system architecture
│   ├── FORECAST_ACCURACY.md          # Accuracy calculation details
│   └── WEATHER_DATA_ANALYSIS.md      # Data analysis features
├── examples/               # Example configurations and dashboards
├── scripts/                # Utility and test scripts
│   ├── weather_forecast_main.py      # Main orchestrator
│   ├── weather_service_health_check.py  # Health monitoring
│   └── install_weather_service.sh    # Service installation
├── systemd/                # Systemd service files
│   ├── weather-forecast.service      # Weather service
│   └── weather-forecast.timer        # Scheduling timer
├── main.py                 # Main application entry point
├── requirements.txt        # Python dependencies
├── install.sh             # Installation script
├── uninstall.sh           # Uninstallation script
└── ruuvi-sensor.service   # Systemd service file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_ble_scanner.py

# Phase 2 component tests
python scripts/test_weather_infrastructure.py
python scripts/test_forecast_accuracy.py
python scripts/test_weather_analysis.py
python scripts/test_orchestrator_integration.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## 📚 API Reference

### Core Classes

#### RuuviBLEScanner
```python
from src.ble.scanner import RuuviBLEScanner

scanner = RuuviBLEScanner(config, logger, performance_monitor)
await scanner.start_scanning()

# Historical data retrieval
historical_data = await scanner.retrieve_historical_data("AA:BB:CC:DD:EE:FF", hours_back=24)
```

#### RuuviInfluxDBClient
```python
from src.influxdb.client import RuuviInfluxDBClient

client = RuuviInfluxDBClient()
await client.write_sensor_data(sensor_data)
```

### Phase 2 Weather Classes

#### WeatherAPI
```python
from src.weather.api import WeatherAPI

api = WeatherAPI(config, logger)
forecast = await api.fetch_forecast_data(days=7)
current = await api.fetch_current_weather()
```

#### ForecastAccuracyCalculator
```python
from src.weather.accuracy import ForecastAccuracyCalculator

calculator = ForecastAccuracyCalculator(config, logger, performance_monitor)
await calculator.calculate_and_store_forecast_errors(
    bucket_sensor="ruuvi_sensors",
    bucket_forecast="weather_forecasts",
    bucket_errors="weather_forecasts",
    org="your_org",
    lookback_time="48h"
)
```

#### WeatherDataAnalyzer
```python
from src.weather.analysis import WeatherDataAnalyzer

analyzer = WeatherDataAnalyzer(config, logger, performance_monitor)
analyzer.generate_sensor_data_profile_report(sensor_df)
rules_df = analyzer.discover_sensor_association_rules(sensor_df)
```

#### WeatherForecastOrchestrator
```python
from scripts.weather_forecast_main import WeatherForecastOrchestrator

orchestrator = WeatherForecastOrchestrator(config)
await orchestrator.initialize()
success = await orchestrator.run_workflow()
```

### Historical Data Retrieval Classes ✅ **FULLY IMPLEMENTED**

#### RuuviProtocolHandler
**Complete GATT protocol implementation for Ruuvi sensor communication**
```python
from src.ble.scanner import RuuviProtocolHandler
from bleak import BleakClient

# Initialize with connected BLE client
client = BleakClient("AA:BB:CC:DD:EE:FF")
await client.connect()
protocol_handler = RuuviProtocolHandler(client, logger)

# Start GATT notifications for command responses and data
await protocol_handler.start_notifications()

# Query device capabilities and firmware features
capabilities = await protocol_handler.get_device_capabilities()
print(f"Historical data support: {capabilities.supports_historical_data}")
print(f"Firmware version: {capabilities.firmware_version}")

# Retrieve historical data with automatic chunked transfer handling
historical_records = await protocol_handler.retrieve_historical_data(hours_back=24)

# Clean up
await protocol_handler.stop_notifications()
await client.disconnect()
```

## 🔒 Security

### Best Practices

1. **Run as Non-Root User**: Create dedicated service users
2. **Secure Configuration**: Protect `.env` file permissions
3. **Network Security**: Use InfluxDB authentication and TLS
4. **Log Security**: Rotate and secure log files
5. **Update Dependencies**: Regularly update Python packages
6. **API Security**: Secure API key storage and rotation

### Service User Setup

```bash
# Create service users
sudo useradd -r -s /bin/false ruuvi
sudo useradd -r -s /bin/false weather-forecast

# Set file ownership
sudo chown -R ruuvi:ruuvi /opt/ruuvi-sensor/
sudo chown -R weather-forecast:weather-forecast /opt/weather-forecast/

# Secure configuration
sudo chmod 600 /opt/ruuvi-sensor/.env
sudo chmod 600 /opt/weather-forecast/.env.weather
```

### Phase 2 Security Features

- **Systemd Security Hardening**: NoNewPrivileges, ProtectSystem, PrivateTmp
- **Resource Limits**: Memory and CPU constraints
- **Network Restrictions**: Limited network access for API calls only
- **Secure Credential Management**: Environment variable protection
- **Token-based Authentication**: InfluxDB 2.x token security

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for a detailed history of changes and version information.

## 🔗 Related Projects

- **Ruuvi Innovations**: [Official Ruuvi sensor documentation](https://ruuvi.com/)
- **InfluxDB**: [Time-series database documentation](https://docs.influxdata.com/)
- **Grafana**: [Monitoring and visualization platform](https://grafana.com/docs/)
- **BlueZ**: [Linux Bluetooth protocol stack](http://www.bluez.org/)
- **Open-Meteo**: [Free weather API service](https://open-meteo.com/)

## 📊 Project Status

![Project Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)
![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey)
![Historical Data](https://img.shields.io/badge/Historical%20Data-Fully%20Implemented-success)
![Phase 2](https://img.shields.io/badge/Phase%202-Complete-brightgreen)

**Current Version**: 2.0.0 (Phase 2 Complete)
**Development Status**: ✅ Complete and Production-Ready
**Last Updated**: January 2025

### Feature Implementation Status

#### Core Features
- ✅ **Core BLE Scanning**: Fully implemented and tested
- ✅ **InfluxDB Integration**: Production-ready with retention policies
- ✅ **Real-time Monitoring**: Continuous scanning with callbacks
- ✅ **Metadata Management**: Comprehensive sensor tracking
- ✅ **Service Management**: Systemd integration complete
- ✅ **Historical Data Retrieval**: **FULLY IMPLEMENTED** - Complete GATT protocol with chunked transfer
- ✅ **Advanced CLI Features**: Interactive setup wizard and diagnostics
- ✅ **Error Handling**: Comprehensive recovery and retry logic
- ✅ **Performance Monitoring**: Built-in metrics and resource tracking
- ✅ **Security Features**: Permission management and secure credentials
- ✅ **Testing & Validation**: Extensive test suite with integration tests

#### Phase 2 Weather Features
- ✅ **Weather API Integration**: Open-Meteo and OpenWeatherMap support
- ✅ **Forecast Data Storage**: InfluxDB 2.x with proper schema
- ✅ **Accuracy Calculation**: Automated error tracking and analysis
- ✅ **Data Analysis**: Profiling and association rule mining
- ✅ **Automated Orchestration**: Systemd-scheduled workflow execution
- ✅ **Health Monitoring**: Comprehensive component health checks
- ✅ **Grafana Integration**: Complete dashboard configuration guidance
- ✅ **Production Deployment**: Security hardening and monitoring
- ✅ **Documentation**: Comprehensive setup and operation guides

## 🤝 Support

### Getting Help

1. **Documentation**: Check this README and docs/ directory
   - **[Phase 2 Complete Summary](docs/PHASE2_COMPLETE_SUMMARY.md)**: Full implementation overview
   - **[Grafana Dashboard Guide](docs/GRAFANA_DASHBOARD_GUIDE.md)**: Complete visualization setup
   - **[Weather Infrastructure](docs/WEATHER_INFRASTRUCTURE.md)**: System architecture
   - **[Forecast Accuracy](docs/FORECAST_ACCURACY.md)**: Accuracy calculation details
   - **[Weather Data Analysis](docs/WEATHER_DATA_ANALYSIS.md)**: Analysis features
2. **Health Checks**: Run automated diagnostic tools
3. **Issues**: Report bugs and feature requests on GitHub
4. **Discussions**: Join community discussions
5. **Wiki**: Additional guides and examples

### Reporting Issues

When reporting issues, please include:

1. **System Information**: OS, Python version, hardware
2. **Configuration**: Relevant configuration (sanitized)
3. **Logs**: Recent log entries showing the issue
4. **Steps to Reproduce**: Clear reproduction steps
5. **Expected vs Actual Behavior**: What should happen vs what happens
6. **Component**: Specify if issue is with core sensors or Phase 2 weather features

### Phase 2 Specific Support

For Phase 2 weather forecast system issues:

1. **Run Health Check**: `./scripts/weather_service_health_check.py`
2. **Check Service Status**: `sudo systemctl status weather-forecast.service`
3. **Review Logs**: `sudo journalctl -u weather-forecast.service -f`
4. **Test Components**: Use individual test scripts in `scripts/`
5. **Validate Configuration**: Check `.env.weather` settings

## 🎉 Acknowledgments

- **Ruuvi Innovations**: For creating excellent environmental sensors
- **InfluxDB**: For providing robust time-series database
- **Open-Meteo**: For free weather API service
- **Grafana**: For powerful visualization platform
- **Python Community**: For excellent libraries and tools
- **Contributors**: Everyone who has contributed to this project

## 📋 Phase 2 Implementation Summary

### ✅ All Requirements Fulfilled

The Phase 2 Weather Forecast Analysis System has been **completely implemented** according to specifications:

1. **✅ Fetch & Store Weather Forecast Data**: Open-Meteo API integration with InfluxDB storage
2. **✅ Calculate Forecast Accuracy Metrics**: Automated error calculation for multiple horizons
3. **✅ Data Profiling**: HTML report generation using ydata-profiling
4. **✅ Association Rule Mining**: Pattern discovery using mlxtend
5. **✅ Automated Scheduling**: Systemd timer-based execution every 6 hours
6. **✅ Grafana Visualization**: Complete dashboard configuration guidance

### 🚀 Production Ready Features

- **Comprehensive Error Handling**: Graceful recovery from all failure modes
- **Performance Monitoring**: Built-in metrics and health checks
- **Security Hardening**: Systemd security features and credential protection
- **Professional Logging**: Structured logging with rotation and analysis
- **Automated Testing**: Complete test suite for all components
- **Documentation**: Comprehensive guides for setup, operation, and troubleshooting

### 📊 Data Pipeline

```
Ruuvi Sensors → InfluxDB (Sensor Data)
     ↓
Open-Meteo API → Weather Orchestrator → InfluxDB (Forecast Data)
     ↓
Accuracy Calculator → InfluxDB (Error Data)
     ↓
Data Analyzer → HTML Reports
     ↓
Grafana Dashboards ← InfluxDB (All Data)
```

### 🎯 Key Achievements

- **Zero-downtime Operation**: Robust service management with automatic recovery
- **Comprehensive Monitoring**: Health checks, performance metrics, and alerting
- **Professional Documentation**: Complete setup and operation guides
- **Production Security**: Hardened deployment with secure credential management
- **Extensible Architecture**: Designed for future enhancements and integrations

---

**Made with ❤️ for the IoT and environmental monitoring community**

**Phase 2 Status**: ✅ **COMPLETE AND PRODUCTION-READY**