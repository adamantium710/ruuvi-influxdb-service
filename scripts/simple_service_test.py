#!/usr/bin/env python3
"""
Simple Service Test

This script tests the Ruuvi sensor service by:
1. Starting the service in daemon mode
2. Monitoring it for a period
3. Checking InfluxDB for data
4. Stopping the service

Usage:
    python scripts/simple_service_test.py
"""

import subprocess
import time
import signal
import sys
import os
from pathlib import Path
from datetime import datetime
import requests
import json


def test_influxdb_connection():
    """Test InfluxDB connection and query for recent data."""
    print("Testing InfluxDB connection...")
    
    # Read configuration from .env
    env_vars = {}
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    influxdb_host = env_vars.get('INFLUXDB_HOST', 'localhost')
    influxdb_port = env_vars.get('INFLUXDB_PORT', '8086')
    influxdb_token = env_vars.get('INFLUXDB_TOKEN', '')
    influxdb_org = env_vars.get('INFLUXDB_ORG', '')
    influxdb_bucket = env_vars.get('INFLUXDB_BUCKET', 'ruuvi_sensors')
    
    if not influxdb_token:
        print("❌ No InfluxDB token found in .env file")
        return False
    
    # Test connection
    url = f"http://{influxdb_host}:{influxdb_port}/api/v2/buckets"
    headers = {
        'Authorization': f'Token {influxdb_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            print("✅ InfluxDB connection successful")
            
            # Query for recent data
            query_url = f"http://{influxdb_host}:{influxdb_port}/api/v2/query"
            flux_query = f'''
            from(bucket: "{influxdb_bucket}")
              |> range(start: -1h)
              |> filter(fn: (r) => r["_measurement"] =~ /^ruuvi_/)
              |> count()
            '''
            
            query_data = {
                'query': flux_query,
                'org': influxdb_org
            }
            
            query_response = requests.post(query_url, headers=headers, json=query_data, timeout=30)
            if query_response.status_code == 200:
                print("✅ InfluxDB query successful")
                # Parse CSV response to count data points
                csv_data = query_response.text
                lines = csv_data.strip().split('\n')
                data_points = 0
                for line in lines[1:]:  # Skip header
                    if line and not line.startswith('#'):
                        parts = line.split(',')
                        if len(parts) > 5 and parts[5].isdigit():
                            data_points += int(parts[5])
                
                print(f"📊 Found {data_points} data points in the last hour")
                return True
            else:
                print(f"❌ InfluxDB query failed: {query_response.status_code}")
                return False
        else:
            print(f"❌ InfluxDB connection failed: {response.status_code}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"❌ InfluxDB connection error: {e}")
        return False


def main():
    """Main test function."""
    print("Ruuvi Sensor Service Test")
    print("=" * 40)
    print()
    
    # Test InfluxDB connection first
    if not test_influxdb_connection():
        print("❌ InfluxDB test failed. Please check your configuration.")
        return False
    
    print()
    print("Starting service test...")
    
    # Start the service
    print("🚀 Starting Ruuvi sensor service...")
    try:
        process = subprocess.Popen(
            [sys.executable, "main.py", "daemon"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give service time to start
        time.sleep(10)
        
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
                print("❌ Service stopped unexpectedly")
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
            
            # Show service output
            if stdout:
                print("\n📋 Service output:")
                print(stdout[-1000:])  # Last 1000 characters
            
        except subprocess.TimeoutExpired:
            print("⚠️  Service didn't stop gracefully, forcing termination...")
            process.kill()
            process.communicate()
        
        # Test InfluxDB again to see if new data was written
        print("\n🔍 Checking for new data in InfluxDB...")
        if test_influxdb_connection():
            print("✅ InfluxDB test passed after service run")
        else:
            print("⚠️  InfluxDB test failed after service run")
        
        print("\n🎉 Service test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)