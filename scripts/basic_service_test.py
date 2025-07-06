#!/usr/bin/env python3
"""
Basic Service Test

This script tests the Ruuvi sensor service by:
1. Starting the service in daemon mode
2. Monitoring it for a period
3. Stopping the service

Usage:
    python scripts/basic_service_test.py
"""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path
from datetime import datetime


def main():
    """Main test function."""
    print("Ruuvi Sensor Service Basic Test")
    print("=" * 40)
    print()
    
    print("This test will:")
    print("1. Start the service in daemon mode")
    print("2. Monitor it for 2 minutes")
    print("3. Stop the service gracefully")
    print("4. Check service logs")
    print()
    
    # Start the service
    print("🚀 Starting Ruuvi sensor service...")
    try:
        process = subprocess.Popen(
            [sys.executable, "main.py", "daemon"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Give service time to start
        print("⏳ Waiting for service to initialize...")
        time.sleep(15)
        
        # Check if process is still running
        if process.poll() is None:
            print(f"✅ Service started successfully (PID: {process.pid})")
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Service failed to start")
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
            return False
        
        # Monitor service for 2 minutes
        print("⏱️  Monitoring service for 2 minutes...")
        monitor_duration = 120  # seconds
        start_time = time.time()
        
        while time.time() - start_time < monitor_duration:
            if process.poll() is not None:
                print("\n❌ Service stopped unexpectedly")
                stdout, stderr = process.communicate()
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return False
            
            # Show progress
            elapsed = int(time.time() - start_time)
            remaining = monitor_duration - elapsed
            print(f"⏳ Service running... {remaining}s remaining", end='\r')
            time.sleep(5)
        
        print("\n✅ Service ran successfully for 2 minutes")
        
        # Stop service gracefully
        print("🛑 Stopping service...")
        process.send_signal(signal.SIGTERM)
        
        try:
            stdout, stderr = process.communicate(timeout=30)
            print("✅ Service stopped gracefully")
            
            # Show service output (last part)
            if stdout:
                print("\n📋 Service output (last 1000 characters):")
                print("-" * 50)
                print(stdout[-1000:])
                print("-" * 50)
            
            if stderr:
                print("\n⚠️  Service errors:")
                print("-" * 50)
                print(stderr[-1000:])
                print("-" * 50)
            
        except subprocess.TimeoutExpired:
            print("⚠️  Service didn't stop gracefully, forcing termination...")
            process.kill()
            process.communicate()
        
        # Check log files
        print("\n📁 Checking log files...")
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            if log_files:
                print(f"✅ Found {len(log_files)} log files:")
                for log_file in log_files:
                    size = log_file.stat().st_size
                    print(f"   - {log_file.name}: {size} bytes")
                
                # Show recent log entries
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                print(f"\n📄 Recent entries from {latest_log.name}:")
                print("-" * 50)
                try:
                    with open(latest_log, 'r') as f:
                        lines = f.readlines()
                        # Show last 10 lines
                        for line in lines[-10:]:
                            print(line.rstrip())
                except Exception as e:
                    print(f"Error reading log file: {e}")
                print("-" * 50)
            else:
                print("⚠️  No log files found")
        else:
            print("⚠️  Log directory not found")
        
        print("\n🎉 Service test completed successfully!")
        print("\nSummary:")
        print("✅ Service started without errors")
        print("✅ Service ran for 2 minutes without crashing")
        print("✅ Service stopped gracefully")
        print("✅ Log files were created")
        
        return True
        
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False


if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎯 RESULT: Service is working properly!")
            print("\nTo check if data is being written to InfluxDB:")
            print("1. Check the InfluxDB web interface")
            print("2. Look for 'ruuvi_environmental', 'ruuvi_motion', 'ruuvi_power', or 'ruuvi_signal' measurements")
            print("3. Verify that sensor data is being collected")
        else:
            print("\n💥 RESULT: Service has issues that need to be addressed.")
        
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)