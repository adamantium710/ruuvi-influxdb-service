#!/bin/bash
#
# Automated Bluetooth VM Fix Script for Proxmox VM 115 (ruuvi2)
# This script applies USB passthrough configuration to enable Bluetooth functionality
#

set -e  # Exit on any error

VM_ID=115
CONFIG_FILE="/etc/pve/qemu-server/${VM_ID}.conf"
BACKUP_FILE="/etc/pve/qemu-server/${VM_ID}.conf.backup.$(date +%Y%m%d_%H%M%S)"

echo "🔧 Automated Bluetooth VM Fix for VM ${VM_ID} (ruuvi2)"
echo "====================================================="
echo

# Check if we're on Proxmox host
if ! command -v qm &> /dev/null; then
    echo "❌ Error: This script must be run on the Proxmox host"
    echo "Please copy this script to the Proxmox host and run it there."
    exit 1
fi

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ Error: This script must be run as root on the Proxmox host"
   exit 1
fi

echo "✅ Running on Proxmox host as root"

# Check if VM exists
if ! qm status ${VM_ID} &> /dev/null; then
    echo "❌ Error: VM ${VM_ID} does not exist"
    exit 1
fi

echo "✅ VM ${VM_ID} found"

# Get current VM status
VM_STATUS=$(qm status ${VM_ID} | awk '{print $2}')
echo "📊 VM status: ${VM_STATUS}"

# Find USB Bluetooth device
echo "🔍 Searching for USB Bluetooth devices..."
USB_DEVICE=""
if lsusb | grep -q "0b05:190e"; then
    # ASUS USB-BT500
    USB_DEVICE=$(lsusb | grep "0b05:190e" | awk '{print $2":"$4}' | sed 's/://' | sed 's/0*//')
    echo "✅ Found ASUS USB-BT500 Bluetooth adapter: ${USB_DEVICE}"
elif lsusb | grep -qi bluetooth; then
    # Generic Bluetooth device
    BLUETOOTH_LINE=$(lsusb | grep -i bluetooth | head -1)
    USB_DEVICE=$(echo "$BLUETOOTH_LINE" | awk '{print $2":"$4}' | sed 's/://' | sed 's/0*//')
    echo "✅ Found Bluetooth device: ${USB_DEVICE}"
    echo "   Device info: $BLUETOOTH_LINE"
else
    echo "❌ Error: No USB Bluetooth devices found"
    echo "   Please ensure the Bluetooth adapter is connected"
    exit 1
fi

# Stop VM if running
if [[ "${VM_STATUS}" == "running" ]]; then
    echo "🛑 Stopping VM ${VM_ID}..."
    qm stop ${VM_ID}
    
    # Wait for VM to stop
    echo "⏳ Waiting for VM to stop..."
    while [[ $(qm status ${VM_ID} | awk '{print $2}') == "running" ]]; do
        sleep 2
    done
    echo "✅ VM stopped"
fi

# Backup current configuration
echo "💾 Creating backup of VM configuration..."
cp "${CONFIG_FILE}" "${BACKUP_FILE}"
echo "✅ Backup created: ${BACKUP_FILE}"

# Check if USB passthrough already exists
if grep -q "usb.*host=${USB_DEVICE}" "${CONFIG_FILE}"; then
    echo "⚠️  USB Bluetooth passthrough already configured"
    echo "   Current configuration:"
    grep "usb.*host=${USB_DEVICE}" "${CONFIG_FILE}"
else
    echo "📝 Adding USB Bluetooth passthrough to VM configuration..."
    
    # Find next available USB slot
    USB_SLOT=0
    while grep -q "^usb${USB_SLOT}:" "${CONFIG_FILE}"; do
        ((USB_SLOT++))
    done
    
    # Add USB passthrough configuration
    echo "usb${USB_SLOT}: host=${USB_DEVICE},usb3=1" >> "${CONFIG_FILE}"
    echo "✅ Added USB passthrough: usb${USB_SLOT}: host=${USB_DEVICE},usb3=1"
fi

# Load Bluetooth modules on Proxmox host
echo "🔌 Loading Bluetooth kernel modules on host..."
modprobe btusb || echo "⚠️  btusb module may already be loaded"
modprobe bluetooth || echo "⚠️  bluetooth module may already be loaded"
modprobe hci_uart || echo "⚠️  hci_uart module may already be loaded"
echo "✅ Bluetooth modules loaded on host"

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

# Start VM
echo "🚀 Starting VM ${VM_ID}..."
qm start ${VM_ID}

# Wait for VM to fully start
echo "⏳ Waiting for VM to fully start..."
sleep 15

# Verify VM is running
VM_STATUS=$(qm status ${VM_ID} | awk '{print $2}')
if [[ "${VM_STATUS}" == "running" ]]; then
    echo "✅ VM ${VM_ID} is running"
else
    echo "❌ Error: VM failed to start properly"
    exit 1
fi

echo
echo "🎉 Bluetooth USB passthrough configured successfully!"
echo "=================================================="
echo
echo "Configuration applied:"
echo "- USB Bluetooth device: ${USB_DEVICE}"
echo "- VM configuration updated: ${CONFIG_FILE}"
echo "- Backup saved: ${BACKUP_FILE}"
echo
echo "NEXT STEPS:"
echo "1. Connect to the VM via SSH or console"
echo "2. Check if USB device is visible: lsusb"
echo "3. Load Bluetooth modules in VM: sudo modprobe btusb bluetooth"
echo "4. Check HCI adapter: hciconfig -a"
echo "5. Test Bleak scanner functionality"
echo
echo "If issues persist, check the backup file: ${BACKUP_FILE}"
echo "To restore: cp ${BACKUP_FILE} ${CONFIG_FILE} && qm restart ${VM_ID}"