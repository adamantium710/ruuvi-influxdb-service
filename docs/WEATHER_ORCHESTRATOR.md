# Weather Forecast Orchestrator System

## Overview

The Weather Forecast Orchestrator is a production-ready system that coordinates all Phase 2 weather forecast components into a unified workflow. It provides automated scheduling, comprehensive error handling, health monitoring, and performance tracking for the complete weather forecast pipeline.

## Architecture

### Core Components

1. **Main Orchestrator** (`scripts/weather_forecast_main.py`)
   - Coordinates all weather modules (API, storage, accuracy analysis, data analysis)
   - Implements the complete Phase 2 workflow
   - Provides async operation management and error recovery
   - Supports both single-run and continuous operation modes

2. **Systemd Integration**
   - Service file (`systemd/weather-forecast.service`) for process management
   - Timer file (`systemd/weather-forecast.timer`) for 6-hour scheduling
   - Security hardening and resource management

3. **Health Monitoring** (`scripts/weather_service_health_check.py`)
   - Component-level health checks
   - JSON and human-readable output formats
   - Integration testing capabilities

4. **Installation Automation** (`scripts/install_weather_service.sh`)
   - Automated deployment with configuration
   - User/group setup and permissions
   - Service management integration

## Workflow Implementation

### Phase 2 Workflow Steps

1. **Forecast Fetching**
   - Retrieves current weather forecast from OpenWeatherMap API
   - Stores forecast data in InfluxDB `weather_forecasts` measurement
   - Handles API rate limiting and error conditions

2. **Historical Data Processing**
   - Fetches historical sensor data from InfluxDB
   - Retrieves corresponding forecast data for accuracy analysis
   - Calculates forecast errors and stores in `weather_forecast_errors` measurement

3. **Data Analysis**
   - Runs data profiling on sensor data
   - Generates HTML reports in `reports/` directory
   - Performs association rule mining on sensor data
   - Logs analysis results and insights

### Scheduling

The system runs every 6 hours at:
- 00:00 (midnight)
- 06:00 (morning)
- 12:00 (noon)
- 18:00 (evening)

This schedule provides:
- Regular forecast updates
- Sufficient data accumulation for accuracy analysis
- Balanced system resource usage
- Alignment with weather forecast update cycles

## Installation and Deployment

### Prerequisites

1. **System Requirements**
   - Linux system with systemd
   - Python 3.8+ with required packages
   - InfluxDB 2.x running and accessible
   - OpenWeatherMap API key

2. **Configuration**
   - Copy `.env.weather.sample` to `.env.weather`
   - Configure InfluxDB connection parameters
   - Set OpenWeatherMap API key
   - Adjust location coordinates if needed

### Installation Steps

1. **Automated Installation**
   ```bash
   # Install and enable the service
   sudo ./scripts/install_weather_service.sh --enable
   
   # Install without enabling (for testing)
   sudo ./scripts/install_weather_service.sh
   ```

2. **Manual Installation**
   ```bash
   # Create service user
   sudo useradd -r -s /bin/false weather-forecast
   
   # Create directories
   sudo mkdir -p /opt/weather-forecast
   sudo mkdir -p /var/log/weather-forecast
   
   # Copy files and set permissions
   sudo cp -r . /opt/weather-forecast/
   sudo chown -R weather-forecast:weather-forecast /opt/weather-forecast
   sudo chown -R weather-forecast:weather-forecast /var/log/weather-forecast
   
   # Install systemd files
   sudo cp systemd/weather-forecast.service /etc/systemd/system/
   sudo cp systemd/weather-forecast.timer /etc/systemd/system/
   sudo systemctl daemon-reload
   
   # Enable and start
   sudo systemctl enable weather-forecast.timer
   sudo systemctl start weather-forecast.timer
   ```

## Operation and Monitoring

### Service Management

```bash
# Check service status
sudo systemctl status weather-forecast.service
sudo systemctl status weather-forecast.timer

# View logs
sudo journalctl -u weather-forecast.service -f
sudo journalctl -u weather-forecast.timer -f

# Manual execution
sudo systemctl start weather-forecast.service

# Stop/disable
sudo systemctl stop weather-forecast.timer
sudo systemctl disable weather-forecast.timer
```

### Health Monitoring

```bash
# Run health check
./scripts/weather_service_health_check.py

# JSON output for monitoring systems
./scripts/weather_service_health_check.py --json

# Check specific component
./scripts/weather_service_health_check.py --component influxdb
```

### Manual Execution

```bash
# Single run (development/testing)
python scripts/weather_forecast_main.py --once

# Continuous mode (not recommended for production)
python scripts/weather_forecast_main.py

# Debug mode with verbose logging
python scripts/weather_forecast_main.py --once --debug
```

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INFLUXDB_URL` | InfluxDB server URL | `http://localhost:8086` |
| `INFLUXDB_TOKEN` | InfluxDB authentication token | Required |
| `INFLUXDB_ORG` | InfluxDB organization | `ruuvi` |
| `INFLUXDB_BUCKET` | InfluxDB bucket name | `ruuvi` |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | Required |
| `LOCATION_LAT` | Location latitude | `60.1699` (Helsinki) |
| `LOCATION_LON` | Location longitude | `24.9384` (Helsinki) |
| `LOG_LEVEL` | Logging level | `INFO` |

### Systemd Configuration

The service includes security hardening:
- Runs as dedicated `weather-forecast` user
- Restricted filesystem access
- No network access except for API calls
- Resource limits (memory, CPU)
- Automatic restart on failure

## Monitoring and Alerting

### Log Analysis

The orchestrator provides structured logging with:
- Component-specific log entries
- Performance metrics and timing
- Error details with context
- Statistics summaries

### Key Metrics

- **Execution Time**: Total workflow duration
- **Component Performance**: Individual module execution times
- **Error Rates**: Failed operations by component
- **Data Quality**: Forecast accuracy metrics
- **System Health**: Resource usage and availability

### Alert Conditions

Monitor for:
- Service failures or crashes
- API connectivity issues
- Database connection problems
- Excessive execution times
- High error rates
- Missing or stale data

## Troubleshooting

### Common Issues

1. **Service Won't Start**
   - Check configuration file permissions
   - Verify InfluxDB connectivity
   - Validate API key configuration
   - Review systemd logs

2. **API Errors**
   - Verify OpenWeatherMap API key
   - Check rate limiting status
   - Confirm network connectivity
   - Review API quota usage

3. **Database Issues**
   - Test InfluxDB connection
   - Verify bucket and organization settings
   - Check authentication token
   - Review database logs

4. **Permission Problems**
   - Ensure proper file ownership
   - Check directory permissions
   - Verify service user configuration
   - Review SELinux/AppArmor policies

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or modify systemd service
sudo systemctl edit weather-forecast.service
```

Add:
```ini
[Service]
Environment=LOG_LEVEL=DEBUG
```

## Performance Optimization

### Resource Usage

- **Memory**: ~50-100MB typical usage
- **CPU**: Low usage, spikes during analysis
- **Network**: Minimal (API calls only)
- **Storage**: Log files and reports

### Optimization Tips

1. **Database Performance**
   - Use appropriate retention policies
   - Index frequently queried fields
   - Monitor query performance

2. **Analysis Efficiency**
   - Adjust data profiling sample sizes
   - Optimize association rule parameters
   - Consider parallel processing for large datasets

3. **System Resources**
   - Monitor memory usage during analysis
   - Adjust systemd resource limits as needed
   - Consider SSD storage for better I/O performance

## Security Considerations

### Service Security

- Dedicated service user with minimal privileges
- Restricted filesystem access
- No shell access for service user
- Environment variable protection

### API Security

- Secure API key storage
- Rate limiting compliance
- HTTPS-only connections
- Error message sanitization

### Database Security

- Token-based authentication
- Encrypted connections
- Principle of least privilege
- Regular token rotation

## Maintenance

### Regular Tasks

1. **Log Rotation**
   - Configure logrotate for service logs
   - Monitor log file sizes
   - Archive old reports

2. **Health Monitoring**
   - Regular health check execution
   - Performance metric review
   - Error rate analysis

3. **Updates**
   - Keep dependencies updated
   - Monitor security advisories
   - Test updates in staging environment

### Backup Considerations

- Configuration files and environment variables
- Generated reports and analysis results
- Service logs for troubleshooting history
- Database backup coordination

## Development and Testing

### Local Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Test individual components
python scripts/test_weather_infrastructure.py
python scripts/test_forecast_accuracy.py
python scripts/test_weather_analysis.py

# Manual orchestrator testing
python scripts/weather_forecast_main.py --once
```

### Integration Testing

```bash
# Full health check
./scripts/weather_service_health_check.py

# Component-specific testing
./scripts/weather_service_health_check.py --component api
./scripts/weather_service_health_check.py --component storage
./scripts/weather_service_health_check.py --component accuracy
```

## Future Enhancements

### Planned Features

1. **Enhanced Monitoring**
   - Prometheus metrics export
   - Grafana dashboard integration
   - Custom alerting rules

2. **Scalability Improvements**
   - Multi-location support
   - Distributed processing
   - Load balancing capabilities

3. **Advanced Analytics**
   - Machine learning integration
   - Predictive accuracy modeling
   - Anomaly detection

4. **Operational Features**
   - Web-based management interface
   - Configuration hot-reloading
   - Dynamic scheduling adjustment

## Support and Documentation

### Additional Resources

- [Weather Infrastructure Documentation](WEATHER_INFRASTRUCTURE.md)
- [Forecast Accuracy Documentation](FORECAST_ACCURACY.md)
- [Weather Data Analysis Documentation](WEATHER_DATA_ANALYSIS.md)
- [Phase 2 Specification](../phase%202.md)

### Getting Help

For issues and questions:
1. Check the troubleshooting section
2. Review service logs
3. Run health checks
4. Consult component-specific documentation
5. Test individual components in isolation

The Weather Forecast Orchestrator provides a robust, production-ready solution for automated weather forecast processing and analysis, designed for reliability, maintainability, and operational excellence.