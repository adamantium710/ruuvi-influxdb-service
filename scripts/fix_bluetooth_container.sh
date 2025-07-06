#!/bin/bash
"""
Bluetooth Container Fix Script for Proxmox LXC
This script provides the necessary configuration changes for the Proxmox host
"""

echo "🔧 Bluetooth Container Fix for Proxmox LXC"
echo "=========================================="
echo
echo "This script provides the configuration needed to fix Bluetooth in your LXC container."
echo "These commands must be run on the PROXMOX HOST, not inside the container."
echo
echo "STEP 1: Stop the container"
echo "pct stop <CONTAINER_ID>"
echo
echo "STEP 2: Edit the container configuration"
echo "nano /etc/pve/lxc/<CONTAINER_ID>.conf"
echo
echo "STEP 3: Add these lines to the container config:"
echo "# Bluetooth USB passthrough"
echo "lxc.cgroup2.devices.allow: c 189:* rwm"
echo "lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir"
echo "lxc.mount.entry: /sys/kernel/debug sys/kernel/debug none bind,optional,create=dir"
echo
echo "# Container privileges for Bluetooth"
echo "lxc.apparmor.profile: unconfined"
echo "lxc.cap.keep: sys_admin sys_rawio"
echo
echo "# Enable nesting if not already enabled"
echo "features: nesting=1"
echo
echo "STEP 4: Load Bluetooth modules on Proxmox host"
echo "modprobe btusb"
echo "modprobe bluetooth"
echo "modprobe hci_uart"
echo
echo "STEP 5: Make module loading persistent on host"
echo "echo 'btusb' >> /etc/modules"
echo "echo 'bluetooth' >> /etc/modules"
echo "echo 'hci_uart' >> /etc/modules"
echo
echo "STEP 6: Start the container"
echo "pct start <CONTAINER_ID>"
echo
echo "ALTERNATIVE SOLUTION: Privileged Container"
echo "=========================================="
echo "If the above doesn't work, convert to privileged container:"
echo "1. Stop container: pct stop <CONTAINER_ID>"
echo "2. Edit config: nano /etc/pve/lxc/<CONTAINER_ID>.conf"
echo "3. Add: unprivileged: 0"
echo "4. Start container: pct start <CONTAINER_ID>"
echo
echo "VERIFICATION:"
echo "============"
echo "After applying fixes, run inside container:"
echo "python scripts/bluetooth_diagnostic.py"
echo
echo "Expected results after fix:"
echo "✅ USB Bluetooth device detected"
echo "✅ Bluetooth kernel modules loaded"
echo "✅ Bluetooth service running"
echo "✅ HCI tools working"
echo "✅ Python BLE scanner functional"