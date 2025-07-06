# Deployment Guide

This guide covers various deployment options for the Ruuvi Sensor Service, from simple local installations to production-ready containerized deployments.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Local Installation](#local-installation)
- [Systemd Service Deployment](#systemd-service-deployment)
- [Docker Deployment](#docker-deployment)
- [Production Deployment](#production-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Monitoring and Maintenance](#monitoring-and-maintenance)

## 🔧 Prerequisites

### Hardware Requirements

**Minimum Requirements:**
- **CPU**: ARM64 or x86_64 processor
- **RAM**: 512MB available memory
- **Storage**: 1GB free disk space
- **Bluetooth**: Bluetooth 4.0+ adapter with BLE support
- **Network**: Internet connection for InfluxDB (if remote)

**Recommended Requirements:**
- **CPU**: Multi-core ARM64 or x86_64 processor
- **RAM**: 1GB+ available memory
- **Storage**: 5GB+ free disk space (for logs and data retention)
- **Bluetooth**: Built-in or high-quality USB Bluetooth 5.0+ adapter
- **Network**: Stable broadband connection

### Software Requirements

**Operating System:**
- Ubuntu 18.04+ / Debian 10+
- CentOS 7+ / RHEL 7+
- Raspberry Pi OS (Raspbian)
- Docker-compatible Linux distribution

**Dependencies:**
- Python 3.8+
- InfluxDB 1.8+ or 2.0+
- Bluetooth stack (BlueZ)
- systemd (for service management)

## 🏠 Local Installation

### Quick Installation

```bash
# Clone repository
git clone <repository-url>
cd ruuvi-sensor-service

# Run automated installation
sudo ./install.sh

# Configure the service
python main.py --setup-wizard
```

### Manual Installation

1. **Install System Dependencies:**

   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip python3-venv bluetooth bluez python3-dev build-essential

   # CentOS/RHEL
   sudo yum install python3 python3-pip bluetooth bluez python3-devel gcc
   ```

2. **Create Virtual Environment:**

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Install InfluxDB:**

   ```bash
   # Ubuntu/Debian
   wget -qO- https://repos.influxdata.com/influxdb.key | sudo apt-key add -
   echo "deb https://repos.influxdata.com/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/influxdb.list
   sudo apt update && sudo apt install influxdb
   
   # Start InfluxDB
   sudo systemctl enable influxdb
   sudo systemctl start influxdb
   ```

4. **Configure Application:**

   ```bash
   cp .env.sample .env
   nano .env  # Edit configuration
   
   # Or use setup wizard
   python main.py --setup-wizard
   ```

5. **Test Installation:**

   ```bash
   python main.py --test
   ```

## ⚙️ Systemd Service Deployment

### Service Installation

The installation script automatically sets up the systemd service, but you can also do it manually:

```bash
# Copy service file
sudo cp ruuvi-sensor.service /etc/systemd/system/

# Create service user
sudo useradd -r -s /bin/false ruuvi

# Set up application directory
sudo mkdir -p /opt/ruuvi-sensor
sudo cp -r . /opt/ruuvi-sensor/
sudo chown -R ruuvi:ruuvi /opt/ruuvi-sensor/

# Install Python dependencies
sudo -u ruuvi python3 -m pip install -r /opt/ruuvi-sensor/requirements.txt

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ruuvi-sensor
sudo systemctl start ruuvi-sensor
```

### Service Management

```bash
# Check service status
sudo systemctl status ruuvi-sensor

# Start/stop/restart service
sudo systemctl start ruuvi-sensor
sudo systemctl stop ruuvi-sensor
sudo systemctl restart ruuvi-sensor

# View logs
sudo journalctl -u ruuvi-sensor -f

# Enable/disable auto-start
sudo systemctl enable ruuvi-sensor
sudo systemctl disable ruuvi-sensor
```

### Service Configuration

Edit the service file for custom configurations:

```bash
sudo systemctl edit ruuvi-sensor
```

Add custom settings:

```ini
[Service]
# Increase memory limit
MemoryMax=1G

# Set CPU limit
CPUQuota=50%

# Custom environment variables
Environment="LOG_LEVEL=DEBUG"
Environment="BLE_SCAN_INTERVAL=5"

# Restart policy
Restart=always
RestartSec=10
```

## 🐳 Docker Deployment

### Single Container Deployment

1. **Build Docker Image:**

   ```bash
   docker build -f examples/Dockerfile -t ruuvi-sensor:latest .
   ```

2. **Run Container:**

   ```bash
   docker run -d \
     --name ruuvi-sensor \
     --privileged \
     --network host \
     -v $(pwd)/data:/app/data \
     -v $(pwd)/logs:/app/logs \
     -v /var/run/dbus:/var/run/dbus:ro \
     --device /dev/bus/usb:/dev/bus/usb \
     -e INFLUXDB_HOST=localhost \
     -e INFLUXDB_DATABASE=ruuvi_sensors \
     ruuvi-sensor:latest
   ```

### Docker Compose Deployment

1. **Use Provided Docker Compose:**

   ```bash
   cd examples
   docker-compose up -d
   ```

2. **Access Services:**
   - **Grafana**: http://localhost:3000 (admin/admin)
   - **InfluxDB**: http://localhost:8086

3. **Import Grafana Dashboard:**

   ```bash
   # Copy dashboard JSON
   cp grafana-dashboard.json /var/lib/docker/volumes/examples_grafana_data/_data/dashboards/
   
   # Or import via Grafana UI
   # Go to Grafana -> Dashboards -> Import -> Upload JSON
   ```

### Docker Configuration

**Environment Variables:**

```yaml
environment:
  - INFLUXDB_HOST=influxdb
  - INFLUXDB_PORT=8086
  - INFLUXDB_DATABASE=ruuvi_sensors
  - INFLUXDB_USERNAME=ruuvi_user
  - INFLUXDB_PASSWORD=ruuvi_password
  - BLE_SCAN_INTERVAL=10
  - BLE_SCAN_TIMEOUT=5
  - LOG_LEVEL=INFO
```

**Volume Mounts:**

```yaml
volumes:
  - ./data:/app/data          # Sensor metadata
  - ./logs:/app/logs          # Application logs
  - /var/run/dbus:/var/run/dbus:ro  # D-Bus for Bluetooth
```

**Device Access:**

```yaml
devices:
  - /dev/bus/usb:/dev/bus/usb  # USB Bluetooth adapter
```

## 🏭 Production Deployment

### High Availability Setup

1. **Load Balancer Configuration:**

   ```nginx
   upstream ruuvi_sensors {
       server sensor-node-1:8080;
       server sensor-node-2:8080;
       server sensor-node-3:8080;
   }
   
   server {
       listen 80;
       server_name ruuvi.example.com;
       
       location / {
           proxy_pass http://ruuvi_sensors;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

2. **InfluxDB Clustering:**

   ```yaml
   # docker-compose.yml for InfluxDB cluster
   version: '3.8'
   services:
     influxdb-1:
       image: influxdb:1.8
       environment:
         - INFLUXDB_HOSTNAME=influxdb-1
       volumes:
         - influxdb1_data:/var/lib/influxdb
     
     influxdb-2:
       image: influxdb:1.8
       environment:
         - INFLUXDB_HOSTNAME=influxdb-2
       volumes:
         - influxdb2_data:/var/lib/influxdb
   ```

### Security Hardening

1. **SSL/TLS Configuration:**

   ```bash
   # Generate SSL certificates
   sudo certbot --nginx -d ruuvi.example.com
   
   # Configure InfluxDB HTTPS
   sudo nano /etc/influxdb/influxdb.conf
   ```

   ```toml
   [http]
   https-enabled = true
   https-certificate = "/etc/ssl/certs/influxdb.pem"
   https-private-key = "/etc/ssl/private/influxdb.key"
   ```

2. **Firewall Configuration:**

   ```bash
   # UFW configuration
   sudo ufw allow ssh
   sudo ufw allow 8086/tcp  # InfluxDB
   sudo ufw allow 3000/tcp  # Grafana
   sudo ufw enable
   ```

3. **User Security:**

   ```bash
   # Create dedicated user with minimal privileges
   sudo useradd -r -s /bin/false -d /opt/ruuvi-sensor ruuvi
   sudo usermod -a -G bluetooth ruuvi
   
   # Set file permissions
   sudo chmod 600 /opt/ruuvi-sensor/.env
   sudo chown -R ruuvi:ruuvi /opt/ruuvi-sensor/
   ```

### Backup Strategy

1. **Automated Backup Script:**

   ```bash
   #!/bin/bash
   # backup.sh
   
   BACKUP_DIR="/backup/ruuvi-$(date +%Y%m%d)"
   mkdir -p "$BACKUP_DIR"
   
   # Backup InfluxDB
   influxd backup -portable "$BACKUP_DIR/influxdb"
   
   # Backup configuration and metadata
   cp -r /opt/ruuvi-sensor/data "$BACKUP_DIR/"
   cp /opt/ruuvi-sensor/.env "$BACKUP_DIR/"
   
   # Compress backup
   tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
   rm -rf "$BACKUP_DIR"
   
   # Upload to cloud storage (optional)
   aws s3 cp "$BACKUP_DIR.tar.gz" s3://ruuvi-backups/
   ```

2. **Cron Job Setup:**

   ```bash
   # Add to crontab
   0 2 * * * /opt/ruuvi-sensor/backup.sh
   ```

## ☁️ Cloud Deployment

### AWS Deployment

1. **EC2 Instance Setup:**

   ```bash
   # Launch EC2 instance with Ubuntu 20.04
   # Security group: SSH (22), HTTP (80), HTTPS (443), InfluxDB (8086)
   
   # Install Docker
   sudo apt update
   sudo apt install docker.io docker-compose
   sudo usermod -a -G docker ubuntu
   ```

2. **ECS Deployment:**

   ```json
   {
     "family": "ruuvi-sensor",
     "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
     "containerDefinitions": [
       {
         "name": "ruuvi-sensor",
         "image": "your-account.dkr.ecr.region.amazonaws.com/ruuvi-sensor:latest",
         "memory": 512,
         "essential": true,
         "environment": [
           {"name": "INFLUXDB_HOST", "value": "your-influxdb-endpoint"}
         ]
       }
     ]
   }
   ```

### Google Cloud Platform

1. **Cloud Run Deployment:**

   ```bash
   # Build and push to Container Registry
   gcloud builds submit --tag gcr.io/PROJECT-ID/ruuvi-sensor
   
   # Deploy to Cloud Run
   gcloud run deploy ruuvi-sensor \
     --image gcr.io/PROJECT-ID/ruuvi-sensor \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated
   ```

### Azure Deployment

1. **Container Instances:**

   ```bash
   # Create resource group
   az group create --name ruuvi-rg --location eastus
   
   # Deploy container
   az container create \
     --resource-group ruuvi-rg \
     --name ruuvi-sensor \
     --image ruuvi-sensor:latest \
     --cpu 1 --memory 1
   ```

## 📊 Monitoring and Maintenance

### Health Monitoring

1. **Health Check Endpoint:**

   ```bash
   # Manual health check
   python examples/healthcheck.py
   
   # Automated monitoring with cron
   */5 * * * * /opt/ruuvi-sensor/examples/healthcheck.py || echo "Health check failed" | mail -s "Ruuvi Alert" admin@example.com
   ```

2. **Prometheus Metrics:**

   ```yaml
   # prometheus.yml
   scrape_configs:
     - job_name: 'ruuvi-sensor'
       static_configs:
         - targets: ['localhost:8080']
   ```

### Log Management

1. **Centralized Logging:**

   ```yaml
   # docker-compose.yml addition
   logging:
     driver: "fluentd"
     options:
       fluentd-address: localhost:24224
       tag: ruuvi.sensor
   ```

2. **Log Rotation:**

   ```bash
   # /etc/logrotate.d/ruuvi-sensor
   /opt/ruuvi-sensor/logs/*.log {
       daily
       missingok
       rotate 30
       compress
       delaycompress
       notifempty
       create 644 ruuvi ruuvi
       postrotate
           systemctl reload ruuvi-sensor
       endscript
   }
   ```

### Performance Tuning

1. **System Optimization:**

   ```bash
   # Increase file descriptor limits
   echo "ruuvi soft nofile 65536" >> /etc/security/limits.conf
   echo "ruuvi hard nofile 65536" >> /etc/security/limits.conf
   
   # Optimize Bluetooth settings
   echo "net.core.rmem_max = 134217728" >> /etc/sysctl.conf
   echo "net.core.wmem_max = 134217728" >> /etc/sysctl.conf
   ```

2. **InfluxDB Optimization:**

   ```toml
   # /etc/influxdb/influxdb.conf
   [data]
   cache-max-memory-size = "1g"
   cache-snapshot-memory-size = "25m"
   
   [coordinator]
   write-timeout = "10s"
   max-concurrent-queries = 0
   ```

### Maintenance Tasks

1. **Regular Maintenance Script:**

   ```bash
   #!/bin/bash
   # maintenance.sh
   
   # Clean old logs
   find /opt/ruuvi-sensor/logs -name "*.log.*" -mtime +30 -delete
   
   # Vacuum InfluxDB
   influx -execute "DROP SERIES WHERE time < now() - 90d"
   
   # Update system packages
   apt update && apt upgrade -y
   
   # Restart service if needed
   systemctl restart ruuvi-sensor
   ```

2. **Monitoring Dashboard:**

   Import the provided Grafana dashboard and set up alerts:

   ```json
   {
     "alert": {
       "conditions": [
         {
           "query": {"queryType": "", "refId": "A"},
           "reducer": {"type": "last", "params": []},
           "evaluator": {"params": [0], "type": "lt"}
         }
       ],
       "executionErrorState": "alerting",
       "for": "5m",
       "frequency": "10s",
       "handler": 1,
       "name": "No Recent Sensor Data",
       "noDataState": "no_data"
     }
   }
   ```

## 🔧 Troubleshooting Deployment

### Common Issues

1. **Bluetooth Permission Issues:**
   ```bash
   # Add user to bluetooth group
   sudo usermod -a -G bluetooth ruuvi
   
   # Set capabilities
   sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
   ```

2. **InfluxDB Connection Issues:**
   ```bash
   # Check InfluxDB status
   sudo systemctl status influxdb
   
   # Test connection
   curl -i http://localhost:8086/ping
   ```

3. **Docker Bluetooth Issues:**
   ```bash
   # Ensure privileged mode and host network
   docker run --privileged --network host ...
   
   # Mount D-Bus socket
   -v /var/run/dbus:/var/run/dbus:ro
   ```

### Performance Issues

1. **High CPU Usage:**
   - Increase scan intervals
   - Limit concurrent operations
   - Use CPU limits in Docker/systemd

2. **Memory Leaks:**
   - Monitor with `htop` or `ps`
   - Set memory limits
   - Restart service periodically

3. **Network Issues:**
   - Check firewall rules
   - Verify DNS resolution
   - Test network connectivity

---

This deployment guide covers all major deployment scenarios. Choose the method that best fits your infrastructure and requirements.