# Troubleshooting Guide

This guide covers common issues and their solutions for the Ruuvi Sensor Service.

## 🔍 Quick Diagnostics

### System Health Check

Run the built-in diagnostic tool:

```bash
python main.py --diagnose
```

This will check:
- Bluetooth adapter status
- InfluxDB connectivity
- Configuration validity
- File permissions
- Service status

### Log Analysis

Check recent logs for errors:

```bash
# Application logs
tail -f logs/ruuvi_sensor.log | grep ERROR

# Service logs
sudo journalctl -u ruuvi-sensor -f --since "1 hour ago"

# System Bluetooth logs
sudo journalctl -u bluetooth -f --since "1 hour ago"
```

## 🔧 Common Issues

### 1. Bluetooth Issues

#### Problem: "No Bluetooth adapter found"

**Symptoms:**
- Error: `BluetoothError: No Bluetooth adapter found`
- BLE scanning fails to start

**Solutions:**

1. **Check Bluetooth Hardware:**
   ```bash
   # List Bluetooth adapters
   hciconfig
   
   # If no adapters shown, check USB devices
   lsusb | grep -i bluetooth
   
   # Check kernel modules
   lsmod | grep bluetooth
   ```

2. **Enable Bluetooth Service:**
   ```bash
   sudo systemctl enable bluetooth
   sudo systemctl start bluetooth
   sudo systemctl status bluetooth
   ```

3. **Reset Bluetooth Adapter:**
   ```bash
   sudo hciconfig hci0 down
   sudo hciconfig hci0 up
   
   # Or reset USB Bluetooth adapter
   sudo usb_modeswitch -R -v 0a12 -p 0001
   ```

4. **Install Missing Drivers:**
   ```bash
   # Ubuntu/Debian
   sudo apt install bluetooth bluez bluez-tools
   
   # CentOS/RHEL
   sudo yum install bluez bluez-utils
   ```

#### Problem: "Permission denied" for Bluetooth operations

**Symptoms:**
- Error: `PermissionError: [Errno 13] Permission denied`
- Bluetooth operations require sudo

**Solutions:**

1. **Add User to Bluetooth Group:**
   ```bash
   sudo usermod -a -G bluetooth $USER
   # Logout and login again
   ```

2. **Set Bluetooth Capabilities:**
   ```bash
   # For Python executable
   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
   
   # Or for specific script
   sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/local/bin/ruuvi-sensor
   ```

3. **Configure udev Rules:**
   ```bash
   # Create udev rule
   sudo tee /etc/udev/rules.d/99-bluetooth.rules << EOF
   KERNEL=="hci[0-9]*", GROUP="bluetooth", MODE="0664"
   SUBSYSTEM=="bluetooth", GROUP="bluetooth", MODE="0664"
   EOF
   
   # Reload udev rules
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

#### Problem: "No sensors found" during scanning

**Symptoms:**
- BLE scanning completes but finds no Ruuvi sensors
- Sensors are nearby and powered on

**Solutions:**

1. **Manual BLE Scan:**
   ```bash
   # Test BLE scanning
   sudo hcitool lescan
   
   # Advanced scan with timeout
   timeout 30 sudo hcitool lescan | grep -i ruuvi
   ```

2. **Check Sensor Status:**
   - Ensure sensors have fresh batteries
   - Verify sensors are in advertising mode
   - Check sensor proximity (within 10 meters)
   - Look for sensor LED indicators

3. **Adjust Scan Parameters:**
   ```bash
   # In .env file, increase scan duration
   BLE_SCAN_TIMEOUT=30
   BLE_SCAN_INTERVAL=5
   ```

4. **Reset Bluetooth Stack:**
   ```bash
   sudo systemctl restart bluetooth
   sudo hciconfig hci0 reset
   ```

### 2. InfluxDB Issues

#### Problem: "Connection refused" to InfluxDB

**Symptoms:**
- Error: `ConnectionError: HTTPConnectionPool(host='localhost', port=8086)`
- Cannot connect to InfluxDB server

**Solutions:**

1. **Check InfluxDB Service:**
   ```bash
   sudo systemctl status influxdb
   sudo systemctl start influxdb
   sudo systemctl enable influxdb
   ```

2. **Test InfluxDB Connection:**
   ```bash
   # Test HTTP endpoint
   curl -i http://localhost:8086/ping
   
   # Test with authentication
   curl -i -u username:password http://localhost:8086/ping
   ```

3. **Check InfluxDB Configuration:**
   ```bash
   # View InfluxDB config
   sudo cat /etc/influxdb/influxdb.conf
   
   # Check HTTP section
   grep -A 10 "\[http\]" /etc/influxdb/influxdb.conf
   ```

4. **Verify Network Connectivity:**
   ```bash
   # Check if port is open
   netstat -tlnp | grep 8086
   
   # Test from remote host
   telnet your-influxdb-host 8086
   ```

#### Problem: "Database does not exist"

**Symptoms:**
- Error: `InfluxDBError: database not found: ruuvi_sensors`
- Data writes fail

**Solutions:**

1. **Create Database:**
   ```bash
   # Using InfluxDB CLI
   influx -execute "CREATE DATABASE ruuvi_sensors"
   
   # With authentication
   influx -username admin -password password -execute "CREATE DATABASE ruuvi_sensors"
   ```

2. **Verify Database Creation:**
   ```bash
   influx -execute "SHOW DATABASES"
   ```

3. **Set Retention Policy:**
   ```bash
   influx -execute "CREATE RETENTION POLICY \"default\" ON \"ruuvi_sensors\" DURATION 30d REPLICATION 1 DEFAULT"
   ```

#### Problem: Authentication failures

**Symptoms:**
- Error: `InfluxDBError: authorization failed`
- Cannot authenticate with InfluxDB

**Solutions:**

1. **Check Credentials:**
   ```bash
   # Test authentication
   influx -username your_username -password your_password
   ```

2. **Create InfluxDB User:**
   ```bash
   # Connect as admin
   influx
   
   # Create user
   CREATE USER "ruuvi_user" WITH PASSWORD 'secure_password'
   GRANT ALL ON "ruuvi_sensors" TO "ruuvi_user"
   ```

3. **Update Configuration:**
   ```bash
   # In .env file
   INFLUXDB_USERNAME=ruuvi_user
   INFLUXDB_PASSWORD=secure_password
   ```

### 3. Configuration Issues

#### Problem: "Configuration file not found"

**Symptoms:**
- Error: `ConfigurationError: .env file not found`
- Application fails to start

**Solutions:**

1. **Create Configuration File:**
   ```bash
   cp .env.sample .env
   nano .env
   ```

2. **Run Setup Wizard:**
   ```bash
   python main.py --setup-wizard
   ```

3. **Verify File Permissions:**
   ```bash
   ls -la .env
   chmod 600 .env
   ```

#### Problem: "Invalid configuration values"

**Symptoms:**
- Error: `ConfigurationError: Invalid value for BLE_SCAN_INTERVAL`
- Configuration validation fails

**Solutions:**

1. **Validate Configuration:**
   ```bash
   python main.py --validate-config
   ```

2. **Check Data Types:**
   ```bash
   # Numeric values should not have quotes
   BLE_SCAN_INTERVAL=10  # Correct
   BLE_SCAN_INTERVAL="10"  # Incorrect
   ```

3. **Review Sample Configuration:**
   ```bash
   cat .env.sample
   ```

### 4. Service Issues

#### Problem: Service fails to start

**Symptoms:**
- `sudo systemctl start ruuvi-sensor` fails
- Service status shows "failed"

**Solutions:**

1. **Check Service Logs:**
   ```bash
   sudo journalctl -u ruuvi-sensor -n 50
   sudo systemctl status ruuvi-sensor -l
   ```

2. **Verify Service File:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable ruuvi-sensor
   ```

3. **Check File Permissions:**
   ```bash
   ls -la /opt/ruuvi-sensor/
   sudo chown -R ruuvi:ruuvi /opt/ruuvi-sensor/
   ```

4. **Test Manual Execution:**
   ```bash
   # Run as service user
   sudo -u ruuvi python3 /opt/ruuvi-sensor/main.py --test
   ```

#### Problem: Service stops unexpectedly

**Symptoms:**
- Service runs briefly then stops
- No obvious error messages

**Solutions:**

1. **Check Resource Usage:**
   ```bash
   # Monitor memory usage
   free -h
   
   # Check disk space
   df -h
   
   # Monitor CPU usage
   top
   ```

2. **Increase Service Limits:**
   ```bash
   # Edit service file
   sudo systemctl edit ruuvi-sensor
   
   # Add limits
   [Service]
   LimitNOFILE=65536
   LimitNPROC=4096
   ```

3. **Enable Core Dumps:**
   ```bash
   # In service file
   [Service]
   LimitCORE=infinity
   ```

### 5. Performance Issues

#### Problem: High CPU usage

**Symptoms:**
- System becomes slow
- High CPU usage by Python process

**Solutions:**

1. **Adjust Scan Intervals:**
   ```bash
   # In .env file, increase intervals
   BLE_SCAN_INTERVAL=30
   BLE_SCAN_TIMEOUT=10
   ```

2. **Monitor Performance:**
   ```bash
   python main.py --stats
   htop -p $(pgrep -f ruuvi)
   ```

3. **Optimize Database Writes:**
   ```bash
   # Batch writes in configuration
   INFLUXDB_BATCH_SIZE=100
   INFLUXDB_FLUSH_INTERVAL=10
   ```

#### Problem: High memory usage

**Symptoms:**
- Memory usage grows over time
- System runs out of memory

**Solutions:**

1. **Check for Memory Leaks:**
   ```bash
   # Monitor memory usage
   watch -n 5 'ps aux | grep python'
   
   # Use memory profiler
   pip install memory-profiler
   python -m memory_profiler main.py
   ```

2. **Limit Data Retention:**
   ```bash
   # Set shorter retention in InfluxDB
   influx -execute "ALTER RETENTION POLICY \"default\" ON \"ruuvi_sensors\" DURATION 7d"
   ```

3. **Restart Service Periodically:**
   ```bash
   # Add to crontab
   0 3 * * * /bin/systemctl restart ruuvi-sensor
   ```

## 🔧 Advanced Diagnostics

### Network Diagnostics

```bash
# Check network connectivity
ping -c 4 your-influxdb-host

# Check DNS resolution
nslookup your-influxdb-host

# Check firewall rules
sudo iptables -L
sudo ufw status
```

### Bluetooth Diagnostics

```bash
# Detailed Bluetooth information
sudo hciconfig -a

# Bluetooth device information
sudo hcitool dev

# Scan for all BLE devices
sudo hcitool lescan --duplicates

# Monitor Bluetooth HCI traffic
sudo hcidump -i hci0
```

### System Diagnostics

```bash
# Check system resources
free -h
df -h
uptime
iostat

# Check system logs
sudo dmesg | tail -50
sudo journalctl --since "1 hour ago" | grep -i error
```

## 📊 Monitoring and Alerting

### Log Monitoring

Set up log monitoring with tools like:

1. **Logwatch:**
   ```bash
   sudo apt install logwatch
   sudo logwatch --detail Med --mailto admin@example.com --service ruuvi-sensor
   ```

2. **Fail2ban for Error Patterns:**
   ```bash
   # Create fail2ban filter for repeated errors
   sudo tee /etc/fail2ban/filter.d/ruuvi-sensor.conf << EOF
   [Definition]
   failregex = ERROR.*Connection failed
   ignoreregex =
   EOF
   ```

### Health Checks

Create monitoring scripts:

```bash
#!/bin/bash
# health_check.sh

# Check service status
if ! systemctl is-active --quiet ruuvi-sensor; then
    echo "CRITICAL: Ruuvi sensor service is not running"
    exit 2
fi

# Check InfluxDB connectivity
if ! curl -s http://localhost:8086/ping > /dev/null; then
    echo "CRITICAL: InfluxDB is not responding"
    exit 2
fi

# Check recent data
RECENT_DATA=$(influx -execute "SELECT COUNT(*) FROM ruuvi_measurements WHERE time > now() - 5m" -database ruuvi_sensors -format json)
if [[ "$RECENT_DATA" == *'"values":[[0,0]]'* ]]; then
    echo "WARNING: No recent sensor data"
    exit 1
fi

echo "OK: All systems operational"
exit 0
```

## 🆘 Getting Help

### Before Asking for Help

1. **Check Logs:** Review application and system logs
2. **Run Diagnostics:** Use built-in diagnostic tools
3. **Search Documentation:** Check README and troubleshooting guide
4. **Test Components:** Isolate the problem to specific components

### Information to Include

When reporting issues, provide:

1. **System Information:**
   ```bash
   uname -a
   python3 --version
   pip3 list | grep -E "(bleak|influxdb|rich)"
   ```

2. **Configuration (sanitized):**
   ```bash
   cat .env | sed 's/PASSWORD=.*/PASSWORD=***/'
   ```

3. **Recent Logs:**
   ```bash
   tail -50 logs/ruuvi_sensor.log
   sudo journalctl -u ruuvi-sensor -n 50
   ```

4. **Service Status:**
   ```bash
   sudo systemctl status ruuvi-sensor
   ```

### Emergency Recovery

If the system is completely broken:

1. **Stop All Services:**
   ```bash
   sudo systemctl stop ruuvi-sensor
   ```

2. **Reset Configuration:**
   ```bash
   cp .env.sample .env
   python main.py --setup-wizard
   ```

3. **Reinstall:**
   ```bash
   sudo ./uninstall.sh
   sudo ./install.sh
   ```

4. **Restore from Backup:**
   ```bash
   # If you have backups
   python main.py --import backup.json
   ```

---

**Remember:** Most issues can be resolved by checking logs, verifying configuration, and ensuring all dependencies are properly installed and running.