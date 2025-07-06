# Ruuvi Sensor Service

A comprehensive Python application for monitoring Ruuvi environmental sensors via Bluetooth Low Energy (BLE) and storing data in InfluxDB. This production-ready service provides real-time sensor monitoring, advanced data management, and professional-grade reliability features.

## 🌟 Features

### Core Functionality
- **Bluetooth Low Energy (BLE) Scanning**: Automatic discovery and monitoring of Ruuvi sensors
- **InfluxDB Integration**: High-performance time-series data storage with automatic retention policies
- **Real-time Monitoring**: Live sensor data collection with configurable intervals
- **Metadata Management**: Comprehensive sensor information tracking and validation
- **Service Management**: Systemd integration for production deployment

### Advanced Features
- **Interactive Setup Wizard**: Guided configuration for new installations
- **Data Export/Import**: Multiple format support (JSON, CSV, InfluxDB)
- **Sensor Testing & Calibration**: Comprehensive diagnostic tools
- **Batch Operations**: Multi-sensor management capabilities
- **Real-time Dashboard**: Live monitoring interface
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
- **Python**: 3.8 or higher
- **Bluetooth**: Bluetooth 4.0+ adapter with BLE support
- **Memory**: Minimum 512MB RAM (1GB+ recommended)
- **Storage**: 100MB+ free space for application and logs

### Dependencies
- **InfluxDB**: 1.8+ or 2.0+ (local or remote)
- **Python Packages**: See `requirements.txt`
- **System Packages**: `bluetooth`, `bluez`, `python3-dev`

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd ruuvi-sensor-service

# Run the installation script
sudo ./install.sh
```

### 2. Configuration

```bash
# Run the interactive setup wizard
python main.py --setup-wizard

# Or manually edit the configuration
cp .env.sample .env
nano .env
```

### 3. Start Monitoring

```bash
# Start the service
sudo systemctl start ruuvi-sensor
sudo systemctl enable ruuvi-sensor

# Or run interactively
python main.py
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

4. **Install InfluxDB** (if not already installed):
   ```bash
   # Ubuntu/Debian
   wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
   echo "deb https://repos.influxdata.com/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
   sudo apt update
   sudo apt install influxdb
   sudo systemctl enable influxdb
   sudo systemctl start influxdb
   ```

### Configuration Options

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

# Show system status
python main.py --status
```

### Service Management

Control the systemd service:

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

## 🔧 Configuration

### Environment Variables

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

# Test connection
curl -i http://localhost:8086/ping

# Check configuration
influx -execute "SHOW DATABASES"
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

### Log Analysis

Logs are stored in `logs/ruuvi_sensor.log` with rotation:

```bash
# View recent logs
tail -f logs/ruuvi_sensor.log

# Search for errors
grep ERROR logs/ruuvi_sensor.log

# View service logs
sudo journalctl -u ruuvi-sensor -f
```

### Performance Monitoring

The application includes built-in performance monitoring:

```bash
# View performance metrics
python main.py --stats

# Monitor resource usage
htop
iotop
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
│   └── utils/              # Utilities and configuration
├── data/                   # Data files and metadata
├── logs/                   # Log files
├── tests/                  # Unit and integration tests
├── docs/                   # Documentation
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

scanner = RuuviBLEScanner()
await scanner.start_scanning()
```

#### RuuviInfluxDBClient
```python
from src.influxdb.client import RuuviInfluxDBClient

client = RuuviInfluxDBClient()
await client.write_sensor_data(sensor_data)
```

#### MetadataManager
```python
from src.metadata.manager import MetadataManager

manager = MetadataManager()
await manager.register_sensor(mac_address, metadata)
```

## 🔒 Security

### Best Practices

1. **Run as Non-Root User**: Create dedicated service user
2. **Secure Configuration**: Protect `.env` file permissions
3. **Network Security**: Use InfluxDB authentication
4. **Log Security**: Rotate and secure log files
5. **Update Dependencies**: Regularly update Python packages

### Service User Setup

```bash
# Create service user
sudo useradd -r -s /bin/false ruuvi

# Set file ownership
sudo chown -R ruuvi:ruuvi /opt/ruuvi-sensor/

# Secure configuration
sudo chmod 600 /opt/ruuvi-sensor/.env
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Support

### Getting Help

1. **Documentation**: Check this README and docs/ directory
2. **Issues**: Report bugs and feature requests on GitHub
3. **Discussions**: Join community discussions
4. **Wiki**: Additional guides and examples

### Reporting Issues

When reporting issues, please include:

1. **System Information**: OS, Python version, hardware
2. **Configuration**: Relevant configuration (sanitized)
3. **Logs**: Recent log entries showing the issue
4. **Steps to Reproduce**: Clear reproduction steps
5. **Expected vs Actual Behavior**: What should happen vs what happens

## 🎉 Acknowledgments

- **Ruuvi Innovations**: For creating excellent environmental sensors
- **InfluxDB**: For providing robust time-series database
- **Python Community**: For excellent libraries and tools
- **Contributors**: Everyone who has contributed to this project

---

**Made with ❤️ for the IoT and environmental monitoring community**