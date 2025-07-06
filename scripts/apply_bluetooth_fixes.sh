#!/bin/bash
"""
Automated Bluetooth Container Fix Script for Proxmox LXC Container 115
This script applies all necessary configuration changes to enable Bluetooth functionality
"""

set -e  # Exit on any error

CONTAINER_ID=115
CONFIG_FILE="/etc/pve/lxc/${CONTAINER_ID}.conf"
BACKUP_FILE="/etc/pve/lxc/${CONTAINER_ID}.conf.backup.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Automated Bluetooth Container Fix for LXC Container ${CONTAINER_ID}"
echo "=================================================================="
echo

# Check if we're on Proxmox host
if ! command -v pct &> /dev/null; then
    echo "❌ Error: This script must be run on the Proxmox host, not inside a container"
    echo "Please copy this script to the Proxmox host and run it there."
    exit 1
fi

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Error: This script must be run as root on the Proxmox host"
   exit 1
fi

echo "✅ Running on Proxmox host as root"

# Check if container exists
if ! pct status ${CONTAINER_ID} &> /dev/null; then
    echo "❌ Error: Container ${CONTAINER_ID} does not exist"
    exit 1
fi

echo "✅ Container ${CONTAINER_ID} found"

# Get current container status
CONTAINER_STATUS=$(pct status ${CONTAINER_ID} | awk '{print $2}')
echo "📊 Container status: ${CONTAINER_STATUS}"

# Stop container if running
if [[ "${CONTAINER_STATUS}" == "running" ]]; then
    echo "🛑 Stopping container ${CONTAINER_ID}..."
    pct stop ${CONTAINER_ID}
    sleep 3
    echo "✅ Container stopped"
fi

# Backup current configuration
echo "💾 Creating backup of container configuration..."
cp "${CONFIG_FILE}" "${BACKUP_FILE}"
echo "✅ Backup created: ${BACKUP_FILE}"

# Check if Bluetooth configuration already exists
if grep -q "# Bluetooth USB passthrough" "${CONFIG_FILE}"; then
    echo "⚠️  Bluetooth configuration already exists in container config"
    echo "   Removing existing configuration before applying new one..."
    
    # Remove existing Bluetooth configuration
    sed -i '/# Bluetooth USB passthrough/,/^$/d' "${CONFIG_FILE}"
fi

echo "📝 Adding Bluetooth configuration to container config..."

# Add Bluetooth configuration to container config
cat >> "${CONFIG_FILE}" << 'EOF'

# Bluetooth USB passthrough
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.cgroup2.devices.allow: c 254:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir
lxc.mount.entry: /sys/kernel/debug sys/kernel/debug none bind,optional,create=dir

# Container privileges for Bluetooth
lxc.apparmor.profile: unconfined
lxc.cap.keep: sys_admin sys_rawio

# Enable nesting if not already enabled
features: nesting=1
EOF

echo "✅ Bluetooth configuration added to container config"

# Load Bluetooth modules on Proxmox host
echo "🔌 Loading Bluetooth kernel modules on host..."
modprobe btusb || echo "⚠️  btusb module may already be loaded"
modprobe bluetooth || echo "⚠️  bluetooth module may already be loaded"
modprobe hci_uart || echo "⚠️  hci_uart module may already be loaded"
echo "✅ Bluetooth modules loaded"

# Make module loading persistent
echo "💾 Making Bluetooth module loading persistent..."
if ! grep -q "^btusb$" /etc/modules; then
    echo "btusb" >> /etc/modules
fi
if ! grep -q "^bluetooth$" /etc/modules; then
    echo "bluetooth" >> /etc/modules
fi
if ! grep -q "^hci_uart$" /etc/modules; then
    echo "hci_uart" >> /etc/modules
fi
echo "✅ Module loading made persistent"

# Check USB Bluetooth device
echo "🔍 Checking for USB Bluetooth devices..."
if lsusb | grep -i bluetooth; then
    echo "✅ USB Bluetooth device found"
elif lsusb | grep "0b05:190e"; then
    echo "✅ ASUS USB-BT500 Bluetooth adapter found"
else
    echo "⚠️  No Bluetooth USB devices detected"
    echo "   Please ensure the Bluetooth adapter is connected"
fi

# Start container
echo "🚀 Starting container ${CONTAINER_ID}..."
pct start ${CONTAINER_ID}

# Wait for container to fully start
echo "⏳ Waiting for container to fully start..."
sleep 10

# Verify container is running
CONTAINER_STATUS=$(pct status ${CONTAINER_ID} | awk '{print $2}')
if [[ "${CONTAINER_STATUS}" == "running" ]]; then
    echo "✅ Container ${CONTAINER_ID} is running"
else
    echo "❌ Error: Container failed to start properly"
    exit 1
fi

echo
echo "🎉 Bluetooth configuration applied successfully!"
echo "=================================================================="
echo
echo "NEXT STEPS:"
echo "1. Connect to the container: pct enter ${CONTAINER_ID}"
echo "2. Run the diagnostic script: python3 /path/to/bluetooth_diagnostic.py"
echo "3. Test HCI adapter: hciconfig hci0 up"
echo "4. Test Bleak scanner functionality"
echo
echo "If issues persist, check the backup file: ${BACKUP_FILE}"
echo "To restore: cp ${BACKUP_FILE} ${CONFIG_FILE} && pct restart ${CONTAINER_ID}"