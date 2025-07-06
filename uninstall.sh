#!/bin/bash

# Ruuvi Sensor Service Uninstallation Script
# This script removes the Ruuvi Sensor Service and cleans up system configuration

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

# Functions
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                   Ruuvi Sensor Service Uninstaller                          ║"
    echo "║                                                                              ║"
    echo "║  This script will remove the Ruuvi Sensor Service and clean up all         ║"
    echo "║  associated system configuration.                                           ║"
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

stop_and_disable_service() {
    print_step "Stopping and disabling service..."
    
    # Check if service exists
    if systemctl list-unit-files | grep -q "$SERVICE_NAME.service"; then
        # Stop service if running
        if systemctl is-active --quiet "$SERVICE_NAME.service"; then
            systemctl stop "$SERVICE_NAME.service"
            print_success "Service stopped"
        fi
        
        # Disable service
        if systemctl is-enabled --quiet "$SERVICE_NAME.service"; then
            systemctl disable "$SERVICE_NAME.service"
            print_success "Service disabled"
        fi
    else
        print_warning "Service not found in systemd"
    fi
}

remove_systemd_service() {
    print_step "Removing systemd service..."
    
    # Remove service file
    if [[ -f "/etc/systemd/system/$SERVICE_NAME.service" ]]; then
        rm -f "/etc/systemd/system/$SERVICE_NAME.service"
        print_success "Service file removed"
    fi
    
    # Reload systemd
    systemctl daemon-reload
    systemctl reset-failed
    
    print_success "Systemd configuration updated"
}

remove_log_configuration() {
    print_step "Removing log configuration..."
    
    # Remove logrotate configuration
    if [[ -f "/etc/logrotate.d/$SERVICE_NAME" ]]; then
        rm -f "/etc/logrotate.d/$SERVICE_NAME"
        print_success "Logrotate configuration removed"
    fi
    
    # Remove systemd journal configuration
    if [[ -f "/etc/systemd/journald.conf.d/$SERVICE_NAME.conf" ]]; then
        rm -f "/etc/systemd/journald.conf.d/$SERVICE_NAME.conf"
        print_success "Journal configuration removed"
    fi
}

remove_bluetooth_permissions() {
    print_step "Removing Bluetooth permissions..."
    
    # Remove udev rule
    if [[ -f "/etc/udev/rules.d/99-ruuvi-bluetooth.rules" ]]; then
        rm -f "/etc/udev/rules.d/99-ruuvi-bluetooth.rules"
        
        # Reload udev rules
        udevadm control --reload-rules
        udevadm trigger
        
        print_success "Bluetooth permissions removed"
    fi
}

backup_user_data() {
    print_step "Creating backup of user data..."
    
    if [[ -d "$INSTALL_DIR" ]]; then
        BACKUP_DIR="/tmp/ruuvi-sensor-backup-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        # Backup configuration and data
        if [[ -f "$INSTALL_DIR/.env" ]]; then
            cp "$INSTALL_DIR/.env" "$BACKUP_DIR/"
        fi
        
        if [[ -d "$INSTALL_DIR/data" ]]; then
            cp -r "$INSTALL_DIR/data" "$BACKUP_DIR/"
        fi
        
        if [[ -d "$INSTALL_DIR/logs" ]]; then
            cp -r "$INSTALL_DIR/logs" "$BACKUP_DIR/"
        fi
        
        if [[ -d "$INSTALL_DIR/backups" ]]; then
            cp -r "$INSTALL_DIR/backups" "$BACKUP_DIR/"
        fi
        
        chown -R "$USER:$USER" "$BACKUP_DIR" 2>/dev/null || true
        
        print_success "User data backed up to: $BACKUP_DIR"
        echo -e "${YELLOW}Note: Your configuration and data have been backed up to $BACKUP_DIR${NC}"
    fi
}

remove_application_files() {
    print_step "Removing application files..."
    
    if [[ -d "$INSTALL_DIR" ]]; then
        rm -rf "$INSTALL_DIR"
        print_success "Application files removed"
    else
        print_warning "Installation directory not found"
    fi
}

remove_service_user() {
    print_step "Removing service user..."
    
    if id "$SERVICE_USER" &>/dev/null; then
        # Kill any remaining processes owned by the user
        pkill -u "$SERVICE_USER" || true
        sleep 2
        
        # Remove user
        userdel "$SERVICE_USER" 2>/dev/null || print_warning "Could not remove user $SERVICE_USER"
        
        print_success "Service user removed"
    else
        print_warning "Service user not found"
    fi
}

clean_system_logs() {
    print_step "Cleaning system logs..."
    
    # Clean systemd journal logs for the service
    journalctl --vacuum-time=1s --identifier="$SERVICE_NAME" 2>/dev/null || true
    
    print_success "System logs cleaned"
}

restart_system_services() {
    print_step "Restarting system services..."
    
    # Restart systemd-journald to apply configuration changes
    systemctl restart systemd-journald
    
    print_success "System services restarted"
}

print_completion_message() {
    echo
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                         Uninstallation Complete!                            ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo
    echo -e "${BLUE}Uninstallation Summary:${NC}"
    echo "  • Service stopped and disabled"
    echo "  • Systemd service file removed"
    echo "  • Application files removed from: $INSTALL_DIR"
    echo "  • Service user removed: $SERVICE_USER"
    echo "  • Log configuration cleaned up"
    echo "  • Bluetooth permissions removed"
    echo
    if [[ -n "$BACKUP_DIR" ]]; then
        echo -e "${YELLOW}Your data has been backed up to: $BACKUP_DIR${NC}"
        echo "You can safely delete this backup if you don't need it."
        echo
    fi
    echo -e "${GREEN}Ruuvi Sensor Service has been completely removed from your system.${NC}"
}

# Main uninstallation process
main() {
    print_header
    
    check_root
    
    echo
    echo -e "${YELLOW}This will completely remove the Ruuvi Sensor Service from your system:${NC}"
    echo "  • Stop and disable the service"
    echo "  • Remove all application files from: $INSTALL_DIR"
    echo "  • Remove service user: $SERVICE_USER"
    echo "  • Clean up system configuration"
    echo "  • Create backup of user data"
    echo
    echo -e "${RED}WARNING: This action cannot be undone!${NC}"
    echo
    
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
    
    echo
    
    # Ask about data backup
    read -p "Do you want to backup your configuration and data? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        SKIP_BACKUP=true
    else
        SKIP_BACKUP=false
    fi
    
    echo
    
    stop_and_disable_service
    remove_systemd_service
    remove_log_configuration
    remove_bluetooth_permissions
    
    if [[ "$SKIP_BACKUP" != "true" ]]; then
        backup_user_data
    fi
    
    remove_application_files
    remove_service_user
    clean_system_logs
    restart_system_services
    
    print_completion_message
}

# Run main function
main "$@"