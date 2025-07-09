# Troubleshooting Guide

This comprehensive troubleshooting guide covers common issues and solutions for both the core Ruuvi sensor system and the Phase 2 weather forecast analysis system.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Core System Issues](#core-system-issues)
3. [Phase 2 Weather System Issues](#phase-2-weather-system-issues)
4. [Database Issues](#database-issues)
5. [Grafana Dashboard Issues](#grafana-dashboard-issues)
6. [Network and API Issues](#network-and-api-issues)
7. [Performance Issues](#performance-issues)
8. [Service Management Issues](#service-management-issues)
9. [Configuration Issues](#configuration-issues)
10. [Advanced Debugging](#advanced-debugging)

## Quick Diagnostics

### Health Check Commands

```bash
# Core system health check
python scripts/health_check.py

# Weather system health check
python scripts/weather_service_health_check.py

# Service status
sudo systemctl status ruuvi-monitor.service
sudo systemctl status weather-forecast.service

# Recent logs
sudo journalctl -u ruuvi-monitor.service -n 50
sudo journalctl -u weather-forecast.service -n 50
```

### System Information

```bash
# Check Python environment
python --version
pip list | grep -E "(influxdb|requests|bluepy|pandas)"

# Check Bluetooth
sudo systemctl status bluetooth
hciconfig

# Check InfluxDB
influx ping
influx bucket list

# Check disk space
df -h
du -sh /var/log/
```

## Core System Issues

### Bluetooth Scanning Problems

#### Issue: No sensors detected
```
ERROR: No Ruuvi sensors found during scan
```

**Solutions:**
1. **Check Bluetooth adapter:**
   ```bash
   sudo systemctl status bluetooth
   hciconfig
   sudo hciconfig hci0 up
   ```

2. **Verify sensor proximity:**
   - Ensure sensors are within 10-30 meters
   - Check sensor battery levels
   - Try manual scan: `sudo hcitool lescan`

3. **Permission issues:**
   ```bash
   sudo usermod -a -G bluetooth $USER
   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
   ```

4. **Reset Bluetooth:**
   ```bash
   sudo systemctl restart bluetooth
   sudo rfkill unblock bluetooth
   ```

#### Issue: Intermittent sensor readings
```
WARNING: Sensor XX:XX:XX:XX:XX:XX timeout
```

**Solutions:**
1. **Increase scan timeout:**
   ```python
   # In config
   SCAN_TIMEOUT = 30  # Increase from default 10
   ```

2. **Check interference:**
   - Move away from WiFi routers
   - Check for other BLE devices
   - Try different times of day

3. **Sensor maintenance:**
   - Replace batteries
   - Clean sensor contacts
   - Reset sensor (button press)

### Historical Data Retrieval Issues

#### Issue: GATT connection failures
```
ERROR: Failed to connect to sensor for historical data
```

**Solutions:**
1. **Connection retry logic:**
   ```bash
   # Check current retry settings
   grep -r "MAX_RETRIES" src/
   
   # Increase retries in config
   GATT_MAX_RETRIES = 5
   GATT_RETRY_DELAY = 2.0
   ```

2. **Bluetooth stack reset:**
   ```bash
   sudo systemctl restart bluetooth
   sudo rmmod btusb && sudo modprobe btusb
   ```

3. **Sensor-specific issues:**
   - Some sensors require longer connection time
   - Try connecting manually: `gatttool -b XX:XX:XX:XX:XX:XX -I`

## Phase 2 Weather System Issues

### Weather API Problems

#### Issue: API key authentication failures
```
ERROR: Weather API authentication failed (401)
```

**Solutions:**
1. **Verify API keys:**
   ```bash
   # Check environment variables
   echo $OPENWEATHER_API_KEY
   echo $OPEN_METEO_API_KEY
   
   # Test API directly
   curl "https://api.openweathermap.org/data/2.5/weather?q=London&appid=YOUR_KEY"
   ```

2. **Key configuration:**
   ```bash
   # Update .env.weather
   OPENWEATHER_API_KEY=your_actual_key_here
   OPEN_METEO_API_KEY=not_required_but_can_be_set
   
   # Reload environment
   source .env.weather
   ```

3. **API limits:**
   - Check usage limits on provider dashboard
   - Implement rate limiting in code
   - Consider upgrading API plan

#### Issue: Weather data not being stored
```
ERROR: Failed to store weather forecast data
```

**Solutions:**
1. **Database connection:**
   ```bash
   # Test InfluxDB connection
   python -c "
   from src.weather.storage import WeatherStorage
   storage = WeatherStorage()
   print('Connection successful')
   "
   ```

2. **Schema validation:**
   ```bash
   # Check bucket exists
   influx bucket list | grep ruuvi
   
   # Verify write permissions
   influx auth list
   ```

3. **Data format issues:**
   ```python
   # Debug data structure
   import json
   from src.weather.api import WeatherAPI
   
   api = WeatherAPI()
   data = api.get_current_weather(lat=60.1699, lon=24.9384)
   print(json.dumps(data, indent=2))
   ```

### Forecast Accuracy Calculation Issues

#### Issue: No accuracy data generated
```
WARNING: No matching sensor data for accuracy calculation
```

**Solutions:**
1. **Time synchronization:**
   ```bash
   # Check system time
   timedatectl status
   
   # Sync if needed
   sudo timedatectl set-ntp true
   ```

2. **Data availability:**
   ```bash
   # Check sensor data exists
   influx query 'from(bucket:"ruuvi") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "weather_sensors") |> count()'
   
   # Check forecast data exists
   influx query 'from(bucket:"ruuvi") |> range(start: -24h) |> filter(fn: (r) => r._measurement == "weather_forecasts") |> count()'
   ```

3. **Matching logic:**
   ```python
   # Debug matching in accuracy calculator
   from src.weather.accuracy import ForecastAccuracyCalculator
   
   calc = ForecastAccuracyCalculator()
   calc.debug_mode = True  # Enable debug output
   calc.calculate_accuracy()
   ```

### Service Scheduling Issues

#### Issue: Weather service not running automatically
```
ERROR: weather-forecast.service failed to start
```

**Solutions:**
1. **Service status:**
   ```bash
   sudo systemctl status weather-forecast.service
   sudo systemctl status weather-forecast.timer
   
   # Check service logs
   sudo journalctl -u weather-forecast.service -f
   ```

2. **Timer configuration:**
   ```bash
   # Verify timer is enabled
   sudo systemctl is-enabled weather-forecast.timer
   
   # Check timer schedule
   sudo systemctl list-timers | grep weather
   ```

3. **Manual execution:**
   ```bash
   # Test manual run
   cd /home/paul/ruuvi
   python scripts/weather_forecast_main.py
   
   # Check exit code
   echo $?
   ```

## Database Issues

### InfluxDB Connection Problems

#### Issue: Connection refused
```
ERROR: Failed to connect to InfluxDB: Connection refused
```

**Solutions:**
1. **Service status:**
   ```bash
   sudo systemctl status influxdb
   sudo systemctl start influxdb
   sudo systemctl enable influxdb
   ```

2. **Network configuration:**
   ```bash
   # Check listening ports
   sudo netstat -tlnp | grep 8086
   
   # Test connection
   curl -I http://localhost:8086/ping
   ```

3. **Configuration file:**
   ```bash
   # Check InfluxDB config
   sudo cat /etc/influxdb/influxdb.conf | grep -A5 "\[http\]"
   
   # Verify bind address
   grep "bind-address" /etc/influxdb/influxdb.conf
   ```

### Data Retention Issues

#### Issue: Old data not being deleted
```
WARNING: Database size growing unexpectedly
```

**Solutions:**
1. **Check retention policies:**
   ```bash
   influx bucket list
   influx bucket update --name ruuvi --retention 30d
   ```

2. **Manual cleanup:**
   ```bash
   # Delete old data
   influx delete --bucket ruuvi --start 2023-01-01T00:00:00Z --stop 2023-06-01T00:00:00Z
   ```

3. **Monitor disk usage:**
   ```bash
   du -sh /var/lib/influxdb/
   df -h /var/lib/influxdb/
   ```

## Grafana Dashboard Issues

### Dashboard Import Problems

#### Issue: Dashboard import fails
```
ERROR: Dashboard validation failed
```

**Solutions:**
1. **JSON validation:**
   ```bash
   # Validate JSON syntax
   python -m json.tool grafana/dashboard-live-weather-comparison.json > /dev/null
   ```

2. **Datasource configuration:**
   ```bash
   # Check InfluxDB datasource in Grafana
   curl -u admin:admin http://localhost:3000/api/datasources
   ```

3. **Version compatibility:**
   - Ensure Grafana version supports dashboard format
   - Update dashboard schema version if needed

#### Issue: No data in panels
```
WARNING: Panel shows "No data"
```

**Solutions:**
1. **Query testing:**
   ```bash
   # Test Flux query directly
   influx query 'from(bucket:"ruuvi") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "weather_sensors") |> limit(n:10)'
   ```

2. **Time range:**
   - Check dashboard time range settings
   - Verify data exists for selected period
   - Adjust time range to match data availability

3. **Field mapping:**
   ```bash
   # Check field names
   influx query 'from(bucket:"ruuvi") |> range(start: -1h) |> filter(fn: (r) => r._measurement == "weather_sensors") |> keys()'
   ```

## Network and API Issues

### Internet Connectivity

#### Issue: API calls timing out
```
ERROR: Request timeout to weather API
```

**Solutions:**
1. **Network connectivity:**
   ```bash
   ping -c 4 api.openweathermap.org
   curl -I https://api.open-meteo.com/v1/forecast
   ```

2. **DNS resolution:**
   ```bash
   nslookup api.openweathermap.org
   dig api.open-meteo.com
   ```

3. **Firewall settings:**
   ```bash
   sudo ufw status
   sudo iptables -L OUTPUT
   ```

### Proxy Configuration

#### Issue: Requests blocked by proxy
```
ERROR: ProxyError: Cannot connect to proxy
```

**Solutions:**
1. **Environment variables:**
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   export NO_PROXY=localhost,127.0.0.1
   ```

2. **Python requests configuration:**
   ```python
   # In weather API code
   proxies = {
       'http': 'http://proxy.company.com:8080',
       'https': 'http://proxy.company.com:8080'
   }
   response = requests.get(url, proxies=proxies)
   ```

## Performance Issues

### High CPU Usage

#### Issue: Python process consuming high CPU
```
WARNING: High CPU usage detected
```

**Solutions:**
1. **Process monitoring:**
   ```bash
   top -p $(pgrep -f "python.*ruuvi")
   htop
   ```

2. **Scan frequency optimization:**
   ```python
   # Reduce scan frequency
   SCAN_INTERVAL = 60  # Increase from 30 seconds
   SCAN_DURATION = 10  # Reduce from 30 seconds
   ```

3. **Profiling:**
   ```python
   # Add profiling to identify bottlenecks
   import cProfile
   cProfile.run('main_function()', 'profile_output.prof')
   ```

### Memory Issues

#### Issue: Memory usage growing over time
```
ERROR: MemoryError: Unable to allocate memory
```

**Solutions:**
1. **Memory monitoring:**
   ```bash
   free -h
   ps aux | grep python | sort -k4 -nr
   ```

2. **Memory leaks:**
   ```python
   # Use memory profiler
   pip install memory-profiler
   python -m memory_profiler scripts/weather_forecast_main.py
   ```

3. **Garbage collection:**
   ```python
   import gc
   gc.collect()  # Force garbage collection
   ```

## Service Management Issues

### Systemd Service Problems

#### Issue: Service fails to start
```
ERROR: Job for ruuvi-monitor.service failed
```

**Solutions:**
1. **Service file validation:**
   ```bash
   sudo systemd-analyze verify /etc/systemd/system/ruuvi-monitor.service
   ```

2. **Permissions:**
   ```bash
   # Check file permissions
   ls -la /etc/systemd/system/ruuvi-monitor.service
   
   # Fix if needed
   sudo chmod 644 /etc/systemd/system/ruuvi-monitor.service
   ```

3. **Reload systemd:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl reset-failed ruuvi-monitor.service
   ```

### Log Rotation Issues

#### Issue: Log files growing too large
```
WARNING: Log file size exceeding limits
```

**Solutions:**
1. **Configure logrotate:**
   ```bash
   sudo cat > /etc/logrotate.d/ruuvi << EOF
   /var/log/ruuvi/*.log {
       daily
       rotate 7
       compress
       delaycompress
       missingok
       notifempty
       create 644 ruuvi ruuvi
   }
   EOF
   ```

2. **Manual rotation:**
   ```bash
   sudo logrotate -f /etc/logrotate.d/ruuvi
   ```

## Configuration Issues

### Environment Variables

#### Issue: Configuration not loading
```
ERROR: Required configuration missing
```

**Solutions:**
1. **Environment file location:**
   ```bash
   # Check file exists and is readable
   ls -la .env .env.weather
   
   # Source manually
   source .env.weather
   env | grep -E "(INFLUX|WEATHER|OPENWEATHER)"
   ```

2. **Service environment:**
   ```bash
   # Check systemd service environment
   sudo systemctl show ruuvi-monitor.service | grep Environment
   ```

3. **Configuration validation:**
   ```python
   from src.utils.config import Config
   config = Config()
   config.validate()  # Check all required settings
   ```

## Advanced Debugging

### Debug Mode

Enable debug logging for detailed troubleshooting:

```python
# In main scripts
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export LOG_LEVEL=DEBUG
```

### Database Debugging

```bash
# Enable InfluxDB debug logging
influx config set --host http://localhost:8086 --token YOUR_TOKEN --org YOUR_ORG --active

# Query debugging
influx query --debug 'from(bucket:"ruuvi") |> range(start: -1h) |> limit(n:1)'
```

### Network Debugging

```bash
# Monitor network traffic
sudo tcpdump -i any host api.openweathermap.org
sudo netstat -tulpn | grep python

# SSL/TLS debugging
openssl s_client -connect api.openweathermap.org:443 -servername api.openweathermap.org
```

### Python Debugging

```python
# Interactive debugging
import pdb; pdb.set_trace()

# Remote debugging
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

## Getting Help

### Log Collection

When reporting issues, collect these logs:

```bash
#!/bin/bash
# Log collection script
mkdir -p debug_logs
sudo journalctl -u ruuvi-monitor.service -n 100 > debug_logs/ruuvi-service.log
sudo journalctl -u weather-forecast.service -n 100 > debug_logs/weather-service.log
cp /var/log/ruuvi/*.log debug_logs/ 2>/dev/null || true
dmesg | tail -50 > debug_logs/dmesg.log
systemctl status ruuvi-monitor.service > debug_logs/service-status.log
tar -czf debug_logs_$(date +%Y%m%d_%H%M%S).tar.gz debug_logs/
```

### System Information

```bash
# System info for support
uname -a
lsb_release -a
python3 --version
pip3 list | grep -E "(influx|requests|bluepy)"
hciconfig
sudo systemctl status bluetooth influxdb grafana-server
```

### Community Support

1. **GitHub Issues**: Report bugs with full logs and system info
2. **Documentation**: Check docs/ directory for detailed guides
3. **Health Checks**: Run diagnostic scripts before reporting
4. **Search**: Check existing issues for similar problems

## Prevention

### Regular Maintenance

```bash
# Weekly maintenance script
#!/bin/bash
# Check service health
python scripts/health_check.py
python scripts/weather_service_health_check.py

# Clean old logs
sudo journalctl --vacuum-time=7d

# Update system
sudo apt update && sudo apt upgrade

# Check disk space
df -h | grep -E "(/$|/var)"

# Restart services if needed
sudo systemctl restart ruuvi-monitor.service
sudo systemctl restart weather-forecast.service
```

### Monitoring Setup

```bash
# Set up basic monitoring
crontab -e
# Add: 0 */6 * * * /path/to/health_check.py | mail -s "Ruuvi Health" admin@example.com
```

---

**Remember**: Always check the basic diagnostics first, then work through specific issue categories. Most problems can be resolved by checking service status, logs, and configuration files.

For complex issues, enable debug logging and collect comprehensive system information before seeking help.