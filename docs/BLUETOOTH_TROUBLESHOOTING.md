# Bluetooth Troubleshooting Guide for Proxmox LXC Container

## Problem Summary

The Ruuvi sensor monitoring system cannot detect Bluetooth devices because the LXC container lacks proper Bluetooth kernel module support. While the USB Bluetooth adapter is visible and some Bluetooth kernel modules are loaded, the critical `btusb` module is missing, preventing the Bluetooth management interface from functioning.

## Root Cause Analysis

### ✅ Working Components
- **USB Passthrough**: ASUS USB-BT500 adapter is visible (`lsusb` shows Bus 001 Device 002)
- **Software Stack**: BlueZ daemon and Python `bleak` library are properly installed
- **Basic Modules**: Some Bluetooth kernel modules (`bluetooth`, `ecdh_generic`) are loaded
- **D-Bus Service**: D-Bus is running and can communicate with BlueZ

### ❌ Failing Components
- **Critical Module Missing**: `btusb` kernel module cannot be loaded in container
- **Management Interface**: `bluetoothd` fails with "Failed to access management interface"
- **HCI Socket**: Cannot open HCI socket ("Address family not supported by protocol")
- **No Adapters**: `/sys/class/bluetooth` exists but contains no adapter devices
- **BLE Scanning**: Python `bleak` fails with D-Bus communication errors

## Technical Details

### Error Messages Observed
```
bluetoothd: src/adapter.c:adapter_init() Failed to access management interface
hciconfig: Can't open HCI socket.: Address family not supported by protocol
bleak: [org.freedesktop.DBus.Error.NoReply] Message recipient disconnected from message bus without replying
modprobe: FATAL: Module btusb not found in directory /lib/modules/6.8.12-11-pve
```

### Container Limitations
LXC containers share the host kernel but have restricted access to:
- Kernel module loading (`modprobe` operations)
- Hardware management interfaces
- Raw device access without proper passthrough configuration

## Solution Options

### Option 1: Enhanced Container Configuration (Recommended)

**Step 1: Stop the container on Proxmox host**
```bash
pct stop <CONTAINER_ID>
```

**Step 2: Edit container configuration**
```bash
nano /etc/pve/lxc/<CONTAINER_ID>.conf
```

**Step 3: Add these configuration lines**
```
# Bluetooth USB and device access
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir
lxc.mount.entry: /sys/kernel/debug sys/kernel/debug none bind,optional,create=dir

# Container privileges for hardware access
lxc.apparmor.profile: unconfined
lxc.cap.keep: sys_admin sys_rawio

# Enable container nesting
features: nesting=1
```

**Step 4: Load Bluetooth modules on Proxmox host**
```bash
# Load modules immediately
modprobe btusb
modprobe bluetooth
modprobe hci_uart

# Make persistent across reboots
echo 'btusb' >> /etc/modules
echo 'bluetooth' >> /etc/modules
echo 'hci_uart' >> /etc/modules
```

**Step 5: Start container and verify**
```bash
pct start <CONTAINER_ID>
```

### Option 2: Privileged Container (Alternative)

If Option 1 doesn't work, convert to privileged container:

```bash
# Stop container
pct stop <CONTAINER_ID>

# Edit configuration
nano /etc/pve/lxc/<CONTAINER_ID>.conf

# Add this line
unprivileged: 0

# Start container
pct start <CONTAINER_ID>
```

### Option 3: Host Network Mode (Last Resort)

Use host networking to share the host's Bluetooth stack:

```bash
# Add to container config
lxc.net.0.type: none
```

## Verification Steps

After applying the fix, run the diagnostic script inside the container:

```bash
cd /root/ruuvi
source .venv/bin/activate
python scripts/bluetooth_diagnostic.py
```

### Expected Results After Fix
- ✅ USB Bluetooth device detected
- ✅ `btusb` kernel module loaded
- ✅ Bluetooth service running
- ✅ HCI tools working (`hciconfig` shows adapter)
- ✅ `/sys/class/bluetooth/hci0` exists
- ✅ Python BLE scanner functional

## Testing Bluetooth Functionality

### Quick BLE Scan Test
```bash
source .venv/bin/activate
python -c "
import asyncio
import bleak

async def test():
    devices = await bleak.BleakScanner.discover(timeout=5.0)
    print(f'Found {len(devices)} BLE devices')
    for d in devices[:3]:
        print(f'  {d.address} - {d.name}')

asyncio.run(test())
"
```

### Ruuvi Sensor Test
```bash
python main.py discover --duration 10
```

## Container Configuration Template

Here's a complete LXC configuration template for Bluetooth support:

```
# /etc/pve/lxc/<CONTAINER_ID>.conf
arch: amd64
cores: 2
hostname: ruuvi
memory: 2048
net0: name=eth0,bridge=vmbr0,firewall=1,hwaddr=XX:XX:XX:XX:XX:XX,ip=dhcp,type=veth
ostype: ubuntu
rootfs: local-lvm:vm-<ID>-disk-0,size=8G
swap: 512
unprivileged: 1

# Bluetooth Configuration
lxc.cgroup2.devices.allow: c 189:* rwm
lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir
lxc.mount.entry: /sys/kernel/debug sys/kernel/debug none bind,optional,create=dir
lxc.apparmor.profile: unconfined
lxc.cap.keep: sys_admin sys_rawio

# Features
features: nesting=1
```

## Troubleshooting Common Issues

### Issue: "Module btusb not found"
**Solution**: Load the module on the Proxmox host, not inside the container.

### Issue: "Permission denied" errors
**Solution**: Ensure the container has `sys_admin` and `sys_rawio` capabilities.

### Issue: "Address family not supported"
**Solution**: Verify that Bluetooth kernel modules are loaded on the host.

### Issue: D-Bus connection failures
**Solution**: Restart the container after applying configuration changes.

## Security Considerations

The recommended configuration reduces container isolation by:
- Granting additional capabilities (`sys_admin`, `sys_rawio`)
- Disabling AppArmor profile
- Allowing raw device access

For production environments, consider:
- Using a dedicated Bluetooth container
- Implementing additional network security
- Regular security updates

## Support Scripts

Two diagnostic scripts have been created:

1. **`scripts/bluetooth_diagnostic.py`** - Comprehensive Bluetooth system analysis
2. **`scripts/fix_bluetooth_container.sh`** - Step-by-step fix instructions

Run the diagnostic script before and after applying fixes to verify the solution.