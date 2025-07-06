#!/bin/bash

# Ruuvi Sensor Service Installation Script
# This script installs the Ruuvi Sensor Service as a systemd service

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="ruuvi-sensor"
SERVICE_USER="ruuvi"
INSTALL_DIR="/opt/ruuvi-sensor-service"
PYTHON_MIN_VERSION="3.8"

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                    Ruuvi Sensor Service Installer                           ║"
    echo "║                                                                              ║"
    echo "║  This script will install the Ruuvi Sensor Service as a systemd service    ║"
    echo "║  for continuous background monitoring of Ruuvi sensors.                     ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

check_system_requirements() {
    print_step "Checking system requirements..."
    
    # Check OS
    if [[ ! -f /etc/os-release ]]; then
        print_error "Cannot determine OS version"
        exit 1
    fi
    
    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]] && [[ "$ID" != "debian" ]]; then
        print_warning "This script is designed for Ubuntu/Debian. Other distributions may work but are not tested."
    fi
    
    # Check systemd
    if ! command -v systemctl &> /dev/null; then
        print_error "systemd is required but not found"
        exit 1
    fi
    
    # Check Python version
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python 3.8+ is required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 is required but not found"
        exit 1
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is required but not found. Install with: apt install python3-pip"
        exit 1
    fi
    
    # Check Bluetooth
    if ! command -v bluetoothctl &> /dev/null; then
        print_warning "Bluetooth tools not found. Install with: apt install bluetooth bluez"
    fi
    
    print_success "System requirements check passed"
}

install_system_dependencies() {
    print_step "Installing system dependencies..."
    
    apt update
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        bluetooth \
        bluez \
        git \
        curl \
        systemd
    
    print_success "System dependencies installed"
}

create_service_user() {
    print_step "Creating service user..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        print_warning "User $SERVICE_USER already exists"
    else
        useradd --system --shell /bin/false --home-dir "$INSTALL_DIR" --create-home "$SERVICE_USER"
        print_success "Created user $SERVICE_USER"
    fi
    
    # Add user to bluetooth group for BLE access
    usermod -a -G bluetooth "$SERVICE_USER"
    print_success "Added $SERVICE_USER to bluetooth group"
}

install_application() {
    print_step "Installing application files..."
    
    # Create installation directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    cp -r . "$INSTALL_DIR/"
    
    # Remove installation scripts from target
    rm -f "$INSTALL_DIR/install.sh" "$INSTALL_DIR/uninstall.sh"
    
    # Set ownership
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"
    
    # Set permissions
    chmod +x "$INSTALL_DIR/main.py"
    
    print_success "Application files installed to $INSTALL_DIR"
}

setup_python_environment() {
    print_step "Setting up Python virtual environment..."
    
    # Create virtual environment as service user
    sudo -u "$SERVICE_USER" python3 -m venv "$INSTALL_DIR/.venv"
    
    # Install dependencies
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install --upgrade pip
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    # Add additional dependencies for service mode
    sudo -u "$SERVICE_USER" "$INSTALL_DIR/.venv/bin/pip" install \
        watchdog \
        psutil
    
    print_success "Python environment configured"
}

configure_environment() {
    print_step "Configuring environment..."
    
    # Copy environment template if .env doesn't exist
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        if [[ -f "$INSTALL_DIR/.env.sample" ]]; then
            cp "$INSTALL_DIR/.env.sample" "$INSTALL_DIR/.env"
            chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/.env"
            print_warning "Created .env from template. Please edit $INSTALL_DIR/.env with your settings."
        else
            print_warning "No .env.sample found. You'll need to create $INSTALL_DIR/.env manually."
        fi
    fi
    
    # Create required directories
    for dir in data logs backups; do
        mkdir -p "$INSTALL_DIR/$dir"
        chown "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR/$dir"
    done
    
    print_success "Environment configured"
}

install_systemd_service() {
    print_step "Installing systemd service..."
    
    # Update service file with correct paths
    sed -e "s|/usr/bin/python3|$INSTALL_DIR/.venv/bin/python|g" \
        -e "s|/opt/ruuvi-sensor-service|$INSTALL_DIR|g" \
        -e "s|User=ruuvi|User=$SERVICE_USER|g" \
        -e "s|Group=ruuvi|Group=$SERVICE_USER|g" \
        "$INSTALL_DIR/ruuvi-sensor.service" > "/etc/systemd/system/$SERVICE_NAME.service"
    
    # Set permissions
    chmod 644 "/etc/systemd/system/$SERVICE_NAME.service"
    
    # Reload systemd
    systemctl daemon-reload
    
    print_success "Systemd service installed"
}

configure_log_rotation() {
    print_step "Configuring log rotation..."
    
    # Create logrotate configuration
    cat > "/etc/logrotate.d/$SERVICE_NAME" << EOF
$INSTALL_DIR/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
    su $SERVICE_USER $SERVICE_USER
}
EOF
    
    # Configure systemd journal retention
    mkdir -p /etc/systemd/journald.conf.d
    cat > "/etc/systemd/journald.conf.d/$SERVICE_NAME.conf" << EOF
[Journal]
# Ruuvi Sensor Service log retention
SystemMaxUse=100M
SystemMaxFileSize=10M
SystemMaxFiles=10
MaxRetentionSec=7day
EOF
    
    print_success "Log rotation configured"
}

setup_bluetooth_permissions() {
    print_step "Setting up Bluetooth permissions..."
    
    # Create udev rule for Bluetooth access
    cat > "/etc/udev/rules.d/99-ruuvi-bluetooth.rules" << EOF
# Allow ruuvi user to access Bluetooth devices
SUBSYSTEM=="bluetooth", GROUP="bluetooth", MODE="0664"
KERNEL=="hci[0-9]*", GROUP="bluetooth", MODE="0664"
EOF
    
    # Reload udev rules
    udevadm control --reload-rules
    udevadm trigger
    
    print_success "Bluetooth permissions configured"
}

final_setup() {
    print_step "Performing final setup..."
    
    # Enable service (but don't start yet)
    systemctl enable "$SERVICE_NAME.service"
    
    print_success "Service enabled for automatic startup"
    
    # Restart systemd-journald to apply log configuration
    systemctl restart systemd-journald
    
    print_success "System configuration updated"
}

print_completion_message() {
    echo
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                          Installation Complete!                             ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  • Service installed to: $INSTALL_DIR"
    echo "  • Service user: $SERVICE_USER"
    echo "  • Service name: $SERVICE_NAME"
    echo "  • Configuration file: $INSTALL_DIR/.env"
    echo
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Edit configuration: sudo nano $INSTALL_DIR/.env"
    echo "  2. Configure your InfluxDB settings in the .env file"
    echo "  3. Start the service: sudo systemctl start $SERVICE_NAME"
    echo "  4. Check service status: sudo systemctl status $SERVICE_NAME"
    echo "  5. View logs: sudo journalctl -u $SERVICE_NAME -f"
    echo
    echo -e "${BLUE}Management Commands:${NC}"
    echo "  • Start service:    sudo systemctl start $SERVICE_NAME"
    echo "  • Stop service:     sudo systemctl stop $SERVICE_NAME"
    echo "  • Restart service:  sudo systemctl restart $SERVICE_NAME"
    echo "  • View status:      sudo systemctl status $SERVICE_NAME"
    echo "  • View logs:        sudo journalctl -u $SERVICE_NAME"
    echo "  • Interactive CLI:  sudo -u $SERVICE_USER $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/main.py menu"
    echo
    echo -e "${GREEN}Installation completed successfully!${NC}"
}

# Main installation process
main() {
    print_header
    
    check_root
    check_system_requirements
    
    echo
    echo -e "${YELLOW}This will install the Ruuvi Sensor Service with the following configuration:${NC}"
    echo "  • Installation directory: $INSTALL_DIR"
    echo "  • Service user: $SERVICE_USER"
    echo "  • Service name: $SERVICE_NAME"
    echo
    
    read -p "Do you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    
    echo
    install_system_dependencies
    create_service_user
    install_application
    setup_python_environment
    configure_environment
    install_systemd_service
    configure_log_rotation
    setup_bluetooth_permissions
    final_setup
    
    print_completion_message
}

# Run main function
main "$@"