# Weather Forecast Orchestrator

A production-ready orchestration system for automated weather forecast processing and analysis.

## Quick Start

### Prerequisites
- Linux system with systemd
- Python 3.8+
- InfluxDB 2.x
- OpenWeatherMap API key

### Installation

1. **Configure Environment**
   ```bash
   cp .env.weather.sample .env.weather
   # Edit .env.weather with your settings
   ```

2. **Install Service**
   ```bash
   sudo ./scripts/install_weather_service.sh --enable
   ```

3. **Verify Installation**
   ```bash
   ./scripts/weather_service_health_check.py
   sudo systemctl status weather-forecast.timer
   ```

## What It Does

The orchestrator runs every 6 hours and:

1. **Fetches Weather Forecasts** - Gets current forecasts from OpenWeatherMap API
2. **Stores Data** - Saves forecasts to InfluxDB `weather_forecasts` measurement
3. **Analyzes Accuracy** - Compares historical forecasts with actual sensor data
4. **Generates Reports** - Creates data profiling reports and runs association rule mining
5. **Monitors Health** - Tracks performance and errors across all components

## Key Features

- ✅ **Production Ready** - Systemd integration with security hardening
- ✅ **Automated Scheduling** - Runs every 6 hours (00:00, 06:00, 12:00, 18:00)
- ✅ **Comprehensive Monitoring** - Health checks and performance tracking
- ✅ **Error Recovery** - Robust error handling and automatic retries
- ✅ **Easy Deployment** - One-command installation and setup
- ✅ **Detailed Logging** - Structured logs with component-level details

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Systemd       │    │   Orchestrator   │    │   Components    │
│   Timer         │───▶│   Main Script    │───▶│   - Weather API │
│   (6h interval) │    │                  │    │   - Storage     │
└─────────────────┘    └──────────────────┘    │   - Accuracy    │
                                               │   - Analysis    │
                                               └─────────────────┘
```

## Usage

### Service Management
```bash
# Check status
sudo systemctl status weather-forecast.timer
sudo systemctl status weather-forecast.service

# View logs
sudo journalctl -u weather-forecast.service -f

# Manual run
sudo systemctl start weather-forecast.service
```

### Health Monitoring
```bash
# Full health check
./scripts/weather_service_health_check.py

# JSON output for monitoring
./scripts/weather_service_health_check.py --json

# Check specific component
./scripts/weather_service_health_check.py --component influxdb
```

### Development/Testing
```bash
# Single run
python scripts/weather_forecast_main.py --once

# Debug mode
python scripts/weather_forecast_main.py --once --debug
```

## Configuration

Key environment variables in `.env.weather`:

```bash
# InfluxDB Configuration
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your_token_here
INFLUXDB_ORG=ruuvi
INFLUXDB_BUCKET=ruuvi

# OpenWeatherMap API
OPENWEATHER_API_KEY=your_api_key_here

# Location (Helsinki by default)
LOCATION_LAT=60.1699
LOCATION_LON=24.9384

# Logging
LOG_LEVEL=INFO
```

## Monitoring and Alerts

### Key Metrics to Monitor
- Service uptime and execution success
- API response times and error rates
- Database connectivity and query performance
- Data quality and forecast accuracy
- System resource usage

### Log Locations
- **Service Logs**: `journalctl -u weather-forecast.service`
- **Application Logs**: `/var/log/weather-forecast/`
- **Reports**: `reports/` directory

## Troubleshooting

### Common Issues

1. **Service Won't Start**
   ```bash
   # Check configuration
   ./scripts/weather_service_health_check.py --component config
   
   # Check logs
   sudo journalctl -u weather-forecast.service --no-pager
   ```

2. **API Errors**
   ```bash
   # Test API connectivity
   ./scripts/weather_service_health_check.py --component api
   ```

3. **Database Issues**
   ```bash
   # Test InfluxDB connection
   ./scripts/weather_service_health_check.py --component influxdb
   ```

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python scripts/weather_forecast_main.py --once
```

## Security Features

- **Dedicated Service User** - Runs as `weather-forecast` user with minimal privileges
- **Filesystem Restrictions** - Limited access to necessary directories only
- **Network Security** - HTTPS-only API connections
- **Resource Limits** - Memory and CPU constraints via systemd
- **Secure Configuration** - Environment variables protected from other users

## Performance

- **Memory Usage**: ~50-100MB typical
- **CPU Usage**: Low baseline, spikes during analysis
- **Network**: Minimal (API calls only)
- **Execution Time**: ~2-5 minutes per run (depends on data volume)

## File Structure

```
├── scripts/
│   ├── weather_forecast_main.py          # Main orchestrator
│   ├── install_weather_service.sh        # Installation script
│   └── weather_service_health_check.py   # Health monitoring
├── systemd/
│   ├── weather-forecast.service           # Systemd service
│   └── weather-forecast.timer            # Systemd timer
├── src/weather/                           # Weather modules
├── docs/WEATHER_ORCHESTRATOR.md          # Detailed documentation
└── README_ORCHESTRATOR.md                # This file
```

## Documentation

- **[Complete Documentation](docs/WEATHER_ORCHESTRATOR.md)** - Comprehensive guide
- **[Weather Infrastructure](docs/WEATHER_INFRASTRUCTURE.md)** - API and storage
- **[Forecast Accuracy](docs/FORECAST_ACCURACY.md)** - Accuracy analysis
- **[Data Analysis](docs/WEATHER_DATA_ANALYSIS.md)** - Data profiling and mining

## Support

For detailed troubleshooting, configuration options, and advanced usage, see the [complete documentation](docs/WEATHER_ORCHESTRATOR.md).

---

**Status**: Production Ready ✅  
**Last Updated**: January 2025  
**Version**: 1.0.0