#!/usr/bin/env python3
"""
Bluetooth Diagnostic Script for Proxmox LXC Container
Comprehensive testing of Bluetooth functionality and container configuration
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path

def run_command(cmd, capture_output=True):
    """Run a command and return result."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=capture_output, text=True)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def check_usb_devices():
    """Check USB Bluetooth devices."""
    print("=== USB Bluetooth Device Check ===")
    
    code, stdout, stderr = run_command("lsusb")
    if code == 0:
        bluetooth_devices = [line for line in stdout.split('\n') if 'bluetooth' in line.lower() or 'bt' in line.lower() or '0b05:190e' in line]
        if bluetooth_devices:
            print("✅ Bluetooth USB devices found:")
            for device in bluetooth_devices:
                print(f"   {device}")
        else:
            print("❌ No Bluetooth USB devices found")
            print("All USB devices:")
            print(stdout)
    else:
        print(f"❌ Failed to list USB devices: {stderr}")
    print()

def check_kernel_modules():
    """Check Bluetooth kernel modules."""
    print("=== Kernel Module Check ===")
    
    # Check if modules are loaded
    code, stdout, stderr = run_command("lsmod | grep -i blue")
    if code == 0 and stdout.strip():
        print("✅ Bluetooth kernel modules loaded:")
        print(stdout)
    else:
        print("❌ No Bluetooth kernel modules loaded")
    
    # Try to load btusb module
    print("\nTrying to load btusb module...")
    code, stdout, stderr = run_command("modprobe btusb")
    if code == 0:
        print("✅ btusb module loaded successfully")
    else:
        print(f"❌ Failed to load btusb module: {stderr}")
    
    print()

def check_bluetooth_service():
    """Check Bluetooth service status."""
    print("=== Bluetooth Service Check ===")
    
    code, stdout, stderr = run_command("systemctl status bluetooth --no-pager")
    if "active (running)" in stdout:
        print("✅ Bluetooth service is running")
    else:
        print("❌ Bluetooth service is not running")
        print("Service status:")
        print(stdout)
    
    # Check for management interface
    if "Failed to access management interface" in stdout:
        print("❌ Critical: Management interface access failed")
        print("   This indicates missing Bluetooth kernel modules")
    
    print()

def check_sys_bluetooth():
    """Check /sys/class/bluetooth directory."""
    print("=== Bluetooth Sysfs Check ===")
    
    bluetooth_path = Path("/sys/class/bluetooth")
    if bluetooth_path.exists():
        print("✅ /sys/class/bluetooth exists")
        devices = list(bluetooth_path.glob("hci*"))
        if devices:
            print(f"✅ Found {len(devices)} Bluetooth adapters:")
            for device in devices:
                print(f"   {device.name}")
        else:
            print("❌ No Bluetooth adapters found in /sys/class/bluetooth")
    else:
        print("❌ /sys/class/bluetooth does not exist")
        print("   This confirms Bluetooth kernel modules are not loaded")
    
    print()

def check_hci_tools():
    """Check HCI tools functionality."""
    print("=== HCI Tools Check ===")
    
    code, stdout, stderr = run_command("hciconfig -a")
    if code == 0:
        print("✅ hciconfig successful:")
        print(stdout)
    else:
        print(f"❌ hciconfig failed: {stderr}")
        if "Address family not supported" in stderr:
            print("   This confirms Bluetooth protocol stack is not available")
    
    print()

async def check_bleak_scanner():
    """Check Python bleak scanner."""
    print("=== Python Bleak Scanner Check ===")
    
    try:
        import bleak
        print("✅ Bleak library imported successfully")
        
        # Try to create scanner
        scanner = bleak.BleakScanner()
        print("✅ BleakScanner created successfully")
        
        # Try a quick scan
        print("Attempting 2-second BLE scan...")
        devices = await scanner.discover(timeout=2.0)
        print(f"✅ Scan completed. Found {len(devices)} devices")
        
        if devices:
            print("Discovered devices:")
            for device in devices[:5]:  # Show first 5 devices
                print(f"   {device.address} - {device.name or 'Unknown'}")
        
    except ImportError:
        print("❌ Bleak library not available")
    except Exception as e:
        print(f"❌ Bleak scanner failed: {e}")
        if "DBus" in str(e):
            print("   This confirms D-Bus/BlueZ communication issues")
    
    print()

def check_container_config():
    """Check container configuration recommendations."""
    print("=== Container Configuration Analysis ===")
    
    print("Current container appears to be missing Bluetooth kernel support.")
    print("\nRecommended LXC container configuration:")
    print("1. Add to container config file:")
    print("   lxc.cgroup2.devices.allow: c 189:* rwm")
    print("   lxc.mount.entry: /dev/bus/usb dev/bus/usb none bind,optional,create=dir")
    print("   lxc.mount.entry: /sys/kernel/debug sys/kernel/debug none bind,optional,create=dir")
    print("   lxc.apparmor.profile: unconfined")
    print()
    print("2. Enable privileged container or add capabilities:")
    print("   lxc.cap.keep: sys_admin sys_rawio")
    print()
    print("3. Host kernel modules must be loaded:")
    print("   On Proxmox host: modprobe btusb bluetooth")
    print()
    print("4. Alternative: Use host networking mode")
    print("   This allows direct access to host Bluetooth stack")
    print()

def main():
    """Main diagnostic function."""
    print("🔍 Bluetooth Diagnostic Tool for Proxmox LXC Container")
    print("=" * 60)
    print()
    
    # Check if running as root
    if os.geteuid() != 0:
        print("⚠️  Warning: Running as non-root user. Some checks may fail.")
        print()
    
    # Run all checks
    check_usb_devices()
    check_kernel_modules()
    check_bluetooth_service()
    check_sys_bluetooth()
    check_hci_tools()
    
    # Run async bleak check
    asyncio.run(check_bleak_scanner())
    
    check_container_config()
    
    print("🏁 Diagnostic Complete")
    print("=" * 60)

if __name__ == "__main__":
    main()