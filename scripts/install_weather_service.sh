#!/bin/bash
"""
Weather Forecast Service Installation Script

This script installs and configures the systemd service and timer
for the weather forecast orchestrator system.

Usage:
    sudo ./scripts/install_weather_service.sh [OPTIONS]

Options:
    --user USER         Set the service user (default: ruuvi)
    --install-dir DIR   Set installation directory (default: /opt/ruuvi)
    --enable            Enable and start the service after installation
    --dry-run           Show what would be done without making changes

Author: Weather Service Installer
Created: 2025-01-07
"""

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables from .env.weather - REQUIRED
if [[ -f "$PROJECT_ROOT/.env.weather" ]]; then
    source "$PROJECT_ROOT/.env.weather"
else
    log_error ".env.weather file not found at $PROJECT_ROOT/.env.weather"
    log_error "Please create .env.weather file with RUUVI_SERVICE_USER and RUUVI_INSTALL_DIR variables"
    exit 1
fi

# Validate required environment variables
if [[ -z "${RUUVI_SERVICE_USER:-}" ]]; then
    log_error "RUUVI_SERVICE_USER environment variable is required in .env.weather"
    exit 1
fi

if [[ -z "${RUUVI_INSTALL_DIR:-}" ]]; then
    log_error "RUUVI_INSTALL_DIR environment variable is required in .env.weather"
    exit 1
fi

# Configuration from environment variables
DEFAULT_USER="$RUUVI_SERVICE_USER"
DEFAULT_INSTALL_DIR="$RUUVI_INSTALL_DIR"
ENABLE_SERVICE=false
DRY_RUN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Usage function
usage() {
    cat << EOF
Weather Forecast Service Installation Script

Usage: $0 [OPTIONS]

Options:
    --user USER         Set the service user (overrides RUUVI_SERVICE_USER from .env.weather)
    --install-dir DIR   Set installation directory (overrides RUUVI_INSTALL_DIR from .env.weather)
    --enable            Enable and start the service after installation
    --dry-run           Show what would be done without making changes
    --help              Show this help message

Prerequisites:
    - .env.weather file must exist with RUUVI_SERVICE_USER and RUUVI_INSTALL_DIR variables

Examples:
    # Install with settings from .env.weather
    sudo $0

    # Install and enable service
    sudo $0 --enable

    # Override user and directory from command line
    sudo $0 --user weather --install-dir /home/weather/ruuvi

    # Dry run to see what would be done
    sudo $0 --dry-run
EOF
}

# Parse command line arguments
SERVICE_USER="$DEFAULT_USER"
INSTALL_DIR="$DEFAULT_INSTALL_DIR"

while [[ $# -gt 0 ]]; do
    case $1 in
        --user)
            SERVICE_USER="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --enable)
            ENABLE_SERVICE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]] && [[ "$DRY_RUN" == false ]]; then
    log_error "This script must be run as root (use sudo)"
    exit 1
fi

# Validate systemd files exist
SYSTEMD_SERVICE_FILE="$PROJECT_ROOT/systemd/weather-forecast.service"
SYSTEMD_TIMER_FILE="$PROJECT_ROOT/systemd/weather-forecast.timer"

if [[ ! -f "$SYSTEMD_SERVICE_FILE" ]]; then
    log_error "Systemd service file not found: $SYSTEMD_SERVICE_FILE"
    exit 1
fi

if [[ ! -f "$SYSTEMD_TIMER_FILE" ]]; then
    log_error "Systemd timer file not found: $SYSTEMD_TIMER_FILE"
    exit 1
fi

# Function to execute or show command
execute_or_show() {
    local cmd="$1"
    if [[ "$DRY_RUN" == true ]]; then
        echo "Would execute: $cmd"
    else
        log_info "Executing: $cmd"
        eval "$cmd"
    fi
}

# Main installation function
install_weather_service() {
    log_info "Installing Weather Forecast Service..."
    log_info "Service user: $SERVICE_USER"
    log_info "Install directory: $INSTALL_DIR"
    log_info "Enable service: $ENABLE_SERVICE"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi
    
    # Create service user if it doesn't exist
    if ! id "$SERVICE_USER" &>/dev/null; then
        log_info "Creating service user: $SERVICE_USER"
        execute_or_show "useradd --system --home-dir $INSTALL_DIR --shell /bin/bash --comment 'Ruuvi Weather Service' $SERVICE_USER"
    else
        log_info "Service user $SERVICE_USER already exists"
    fi
    
    # Create installation directory
    if [[ ! -d "$INSTALL_DIR" ]]; then
        log_info "Creating installation directory: $INSTALL_DIR"
        execute_or_show "mkdir -p $INSTALL_DIR"
    fi
    
    # Create required subdirectories
    for dir in logs reports data config; do
        execute_or_show "mkdir -p $INSTALL_DIR/$dir"
    done
    
    # Set ownership
    execute_or_show "chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR"
    
    # Copy systemd files with proper substitutions
    log_info "Installing systemd service file..."
    
    # Create temporary service file with substitutions
    TEMP_SERVICE_FILE="/tmp/weather-forecast.service.$$"
    sed -e "s|\${RUUVI_SERVICE_USER}|$SERVICE_USER|g" \
        -e "s|\${RUUVI_INSTALL_DIR}|$INSTALL_DIR|g" \
        -e "s|EnvironmentFile=.*\.env\.weather|EnvironmentFile=$INSTALL_DIR/.env.weather|g" \
        "$SYSTEMD_SERVICE_FILE" > "$TEMP_SERVICE_FILE"
    
    execute_or_show "cp $TEMP_SERVICE_FILE /etc/systemd/system/weather-forecast.service"
    execute_or_show "rm -f $TEMP_SERVICE_FILE"
    
    log_info "Installing systemd timer file..."
    execute_or_show "cp $SYSTEMD_TIMER_FILE /etc/systemd/system/weather-forecast.timer"
    
    # Set proper permissions
    execute_or_show "chmod 644 /etc/systemd/system/weather-forecast.service"
    execute_or_show "chmod 644 /etc/systemd/system/weather-forecast.timer"
    
    # Reload systemd
    log_info "Reloading systemd daemon..."
    execute_or_show "systemctl daemon-reload"
    
    # Enable and start service if requested
    if [[ "$ENABLE_SERVICE" == true ]]; then
        log_info "Enabling weather forecast timer..."
        execute_or_show "systemctl enable weather-forecast.timer"
        
        log_info "Starting weather forecast timer..."
        execute_or_show "systemctl start weather-forecast.timer"
        
        # Show status
        if [[ "$DRY_RUN" == false ]]; then
            log_info "Timer status:"
            systemctl status weather-forecast.timer --no-pager -l
        fi
    fi
    
    log_success "Weather forecast service installation completed!"
    
    # Show next steps
    cat << EOF

Next Steps:
1. Ensure the project code is installed in: $INSTALL_DIR
2. Create and configure the virtual environment: $INSTALL_DIR/.venv
3. Configure environment variables in: $INSTALL_DIR/.env.weather
4. Configure InfluxDB connection settings for your remote InfluxDB server:
   - Set INFLUXDB_HOST to your InfluxDB server hostname/IP (e.g., 192.168.1.100)
   - Set INFLUXDB_PORT to your InfluxDB server port (default: 8086)
   - Set INFLUXDB_TOKEN, INFLUXDB_ORG, and INFLUXDB_BUCKET appropriately
   - Set RUUVI_INSTALL_DIR=$INSTALL_DIR
   - Set RUUVI_SERVICE_USER=$SERVICE_USER
5. Test the service manually:
   sudo -u $SERVICE_USER $INSTALL_DIR/.venv/bin/python $INSTALL_DIR/scripts/weather_forecast_main.py --once

6. Enable and start the timer (if not done already):
   sudo systemctl enable weather-forecast.timer
   sudo systemctl start weather-forecast.timer

7. Monitor the service:
   sudo systemctl status weather-forecast.timer
   sudo journalctl -u weather-forecast.service -f

Service Management Commands:
- Start timer:    sudo systemctl start weather-forecast.timer
- Stop timer:     sudo systemctl stop weather-forecast.timer
- Enable timer:   sudo systemctl enable weather-forecast.timer
- Disable timer:  sudo systemctl disable weather-forecast.timer
- View status:    sudo systemctl status weather-forecast.timer
- View logs:      sudo journalctl -u weather-forecast.service
- List timers:    sudo systemctl list-timers weather-forecast.timer

EOF
}

# Uninstall function
uninstall_weather_service() {
    log_info "Uninstalling Weather Forecast Service..."
    
    # Stop and disable service
    execute_or_show "systemctl stop weather-forecast.timer || true"
    execute_or_show "systemctl disable weather-forecast.timer || true"
    execute_or_show "systemctl stop weather-forecast.service || true"
    execute_or_show "systemctl disable weather-forecast.service || true"
    
    # Remove systemd files
    execute_or_show "rm -f /etc/systemd/system/weather-forecast.service"
    execute_or_show "rm -f /etc/systemd/system/weather-forecast.timer"
    
    # Reload systemd
    execute_or_show "systemctl daemon-reload"
    execute_or_show "systemctl reset-failed"
    
    log_success "Weather forecast service uninstalled!"
    log_warning "Note: User $SERVICE_USER and directory $INSTALL_DIR were not removed"
}

# Check for uninstall flag
if [[ "${1:-}" == "--uninstall" ]]; then
    uninstall_weather_service
    exit 0
fi

# Run installation
install_weather_service