# Ruuvi Sensor Service - Secure Installation Guide

This guide provides step-by-step instructions for securely installing and configuring the Ruuvi Sensor Service with enhanced security measures.

## Prerequisites

### System Requirements
- **Python 3.9+** (required for security features)
- **Linux/macOS** (recommended for BLE support)
- **Bluetooth Low Energy (BLE)** hardware support
- **Root/sudo access** (for BLE operations)

### Security Prerequisites
- Updated operating system with latest security patches
- Secure network environment
- Proper user account management
- Firewall configuration (if applicable)

## Secure Installation Process

### Step 1: Environment Preparation

```bash
# Update system packages (Ubuntu/Debian)
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-dev python3-pip python3-venv bluetooth bluez

# Create dedicated user (recommended)
sudo useradd -m -s /bin/bash ruuvi-service
sudo usermod -a -G bluetooth ruuvi-service

# Switch to service user
sudo su - ruuvi-service
```

### Step 2: Secure Project Setup

```bash
# Clone repository
git clone <repository-url> ruuvi-sensor-service
cd ruuvi-sensor-service

# Set secure file permissions
chmod 755 .
find . -type f -name "*.py" -exec chmod 644 {} \;
chmod +x main.py scripts/security_validation.py

# Create secure virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade pip and security tools
pip install --upgrade pip setuptools wheel
```

### Step 3: Security-Enhanced Dependency Installation

```bash
# Install security scanning tools first
pip install pip-audit safety bandit

# Install dependencies from secure requirements
pip install -r requirements-secure.txt

# Verify installation integrity
pip check
```

### Step 4: Security Validation

```bash
# Run comprehensive security validation
python scripts/security_validation.py

# Expected output should show all checks passing:
# ✓ PASS Python Version     Python 3.9+ - OK
# ✓ PASS SSL Certificates   certifi 2025.6.15 - certificates OK
# ✓ PASS Secure Requirements requirements-secure.txt is newer
# ✓ PASS Environment Security Environment security - OK
# ✓ PASS File Permissions   File permissions - OK
# ✓ PASS pip-audit         No known vulnerabilities detected
# ✓ PASS safety            No known vulnerabilities detected
# ✓ PASS bandit             No security issues found in application code
```

### Step 5: Secure Configuration

```bash
# Create secure configuration directory
mkdir -p ~/.config/ruuvi-service
chmod 700 ~/.config/ruuvi-service

# Create environment file with secure permissions
touch .env
chmod 600 .env

# Add configuration (replace with actual values)
cat >> .env << EOF
# InfluxDB Configuration (if using)
INFLUXDB_URL=https://your-influxdb-instance.com
INFLUXDB_TOKEN=your-secure-token-here
INFLUXDB_ORG=your-organization
INFLUXDB_BUCKET=ruuvi-sensors

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=/var/log/ruuvi-service/ruuvi.log

# Security Settings
ENABLE_SECURITY_LOGGING=true
MAX_DISCOVERY_TIME=300
RATE_LIMIT_ENABLED=true
EOF
```

### Step 6: Application Testing

```bash
# Test basic functionality
python main.py status

# Test sensor discovery (requires BLE hardware)
python main.py discover --duration 10

# Test interactive menu
python main.py menu
```

### Step 7: Security Hardening

#### File System Security
```bash
# Set restrictive permissions on sensitive files
chmod 600 .env
chmod 644 requirements-secure.txt
chmod 755 scripts/security_validation.py

# Create secure log directory
sudo mkdir -p /var/log/ruuvi-service
sudo chown ruuvi-service:ruuvi-service /var/log/ruuvi-service
sudo chmod 750 /var/log/ruuvi-service
```

#### Network Security
```bash
# Configure firewall (if needed for InfluxDB)
sudo ufw allow out 8086/tcp  # InfluxDB
sudo ufw allow out 443/tcp   # HTTPS
sudo ufw deny in 22/tcp      # Disable SSH if not needed
```

#### Process Security
```bash
# Create systemd service with security restrictions
sudo tee /etc/systemd/system/ruuvi-service.service << EOF
[Unit]
Description=Ruuvi Sensor Service
After=network.target bluetooth.target

[Service]
Type=simple
User=ruuvi-service
Group=ruuvi-service
WorkingDirectory=/home/ruuvi-service/ruuvi-sensor-service
Environment=PATH=/home/ruuvi-service/ruuvi-sensor-service/.venv/bin
ExecStart=/home/ruuvi-service/ruuvi-sensor-service/.venv/bin/python main.py daemon
Restart=always
RestartSec=10

# Security restrictions
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/ruuvi-service
PrivateTmp=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
MemoryDenyWriteExecute=true

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable ruuvi-service
sudo systemctl start ruuvi-service
```

## Security Maintenance

### Regular Security Updates

```bash
# Weekly security update routine
cd /home/ruuvi-service/ruuvi-sensor-service
source .venv/bin/activate

# Update security tools
pip install --upgrade pip-audit safety bandit

# Run security scans
python scripts/security_validation.py

# Update dependencies if needed
pip install --upgrade -r requirements-secure.txt

# Verify no new vulnerabilities
pip-audit --format=json
safety check --json
```

### Monitoring and Alerting

```bash
# Set up log monitoring (example with logrotate)
sudo tee /etc/logrotate.d/ruuvi-service << EOF
/var/log/ruuvi-service/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 ruuvi-service ruuvi-service
    postrotate
        systemctl reload ruuvi-service
    endscript
}
EOF
```

### Security Incident Response

1. **Vulnerability Detection**
   - Run `python scripts/security_validation.py` daily
   - Monitor security advisories for dependencies
   - Subscribe to security mailing lists

2. **Incident Response**
   - Stop service: `sudo systemctl stop ruuvi-service`
   - Isolate system if needed
   - Update vulnerable dependencies
   - Re-run security validation
   - Restart service: `sudo systemctl start ruuvi-service`

3. **Recovery Verification**
   - Verify all security checks pass
   - Monitor logs for unusual activity
   - Test functionality after updates

## Security Best Practices

### Development Security
- Always use `requirements-secure.txt` for production
- Run security validation before deployment
- Keep dependencies updated regularly
- Use virtual environments exclusively

### Operational Security
- Monitor system logs regularly
- Implement log rotation and retention
- Use secure communication channels (HTTPS/TLS)
- Regular security assessments

### Access Control
- Use dedicated service accounts
- Implement principle of least privilege
- Secure configuration files (600 permissions)
- Regular access reviews

## Troubleshooting Security Issues

### Common Security Validation Failures

1. **pip-audit failures**
   ```bash
   # Update specific vulnerable package
   pip install --upgrade package-name
   
   # Or update all packages
   pip install --upgrade -r requirements-secure.txt
   ```

2. **File permission issues**
   ```bash
   # Fix common permission problems
   chmod 600 .env
   chmod 644 *.py
   chmod 755 scripts/
   ```

3. **SSL certificate issues**
   ```bash
   # Update certificates
   pip install --upgrade certifi
   ```

### Security Support

For security-related issues:
1. Check the security validation output
2. Review the SECURITY_REMEDIATION.md document
3. Update dependencies using requirements-secure.txt
4. Contact security team if issues persist

## Compliance and Auditing

### Security Documentation
- Maintain security validation logs
- Document all security updates
- Keep audit trail of configuration changes
- Regular security assessments

### Compliance Checklist
- [ ] All dependencies scanned for vulnerabilities
- [ ] Secure file permissions implemented
- [ ] Environment variables properly secured
- [ ] Network security configured
- [ ] Logging and monitoring enabled
- [ ] Regular update schedule established
- [ ] Incident response plan documented

This secure installation guide ensures that the Ruuvi Sensor Service is deployed with comprehensive security measures, addressing the 107 identified vulnerabilities and implementing defense-in-depth security practices.