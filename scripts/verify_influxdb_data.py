#!/usr/bin/env python3
"""
InfluxDB Data Verification Script

This script verifies that data was successfully written to InfluxDB by the service.
It queries the database and shows recent sensor data.

Usage:
    python scripts/verify_influxdb_data.py
"""

import requests
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta


def load_config():
    """Load configuration from .env file."""
    config = {}
    env_file = Path(".env")
    
    if not env_file.exists():
        print("❌ .env file not found")
        return None
    
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                config[key] = value
    
    return config


def query_influxdb(config, query):
    """Execute a Flux query against InfluxDB."""
    url = f"http://{config['INFLUXDB_HOST']}:{config['INFLUXDB_PORT']}/api/v2/query"
    headers = {
        'Authorization': f"Token {config['INFLUXDB_TOKEN']}",
        'Content-Type': 'application/vnd.flux',
        'Accept': 'application/csv'
    }
    
    params = {
        'org': config['INFLUXDB_ORG']
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, data=query, timeout=30)
        if response.status_code == 200:
            return response.text
        else:
            print(f"❌ Query failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Query error: {e}")
        return None


def parse_csv_response(csv_data):
    """Parse CSV response from InfluxDB."""
    lines = csv_data.strip().split('\n')
    if len(lines) < 2:
        return []
    
    # Debug: print raw CSV data
    print("🔍 Raw CSV response:")
    print("-" * 50)
    for i, line in enumerate(lines[:10]):  # Show first 10 lines
        print(f"{i}: {line}")
    print("-" * 50)
    
    # Find header line (starts with table,result,_start,...)
    header_idx = -1
    for i, line in enumerate(lines):
        if 'table' in line and 'result' in line and '_start' in line:
            header_idx = i
            break
    
    if header_idx == -1:
        print("❌ Could not find header line in CSV response")
        return []
    
    headers = lines[header_idx].split(',')
    print(f"📋 Headers found: {headers}")
    
    data = []
    for line in lines[header_idx + 1:]:
        if line and not line.startswith('#') and not line.startswith(','):
            values = line.split(',')
            if len(values) == len(headers):
                record = dict(zip(headers, values))
                data.append(record)
    
    print(f"📊 Parsed {len(data)} records")
    return data


def main():
    """Main verification function."""
    print("InfluxDB Data Verification")
    print("=" * 40)
    print()
    
    # Load configuration
    config = load_config()
    if not config:
        return False
    
    bucket = config.get('INFLUXDB_BUCKET', 'ruuvi_sensors')
    
    # Query for recent data (last hour)
    print("🔍 Querying recent sensor data...")
    
    query = f'''
from(bucket: "{bucket}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] =~ /^ruuvi_/)
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 50)
'''
    
    csv_data = query_influxdb(config, query)
    if not csv_data:
        print("❌ Failed to query data")
        return False
    
    records = parse_csv_response(csv_data)
    
    if not records:
        print("⚠️  No recent data found in InfluxDB")
        print("\nThis could mean:")
        print("1. No Ruuvi sensors were detected during the test")
        print("2. Data is being written to a different bucket")
        print("3. There's an issue with the data writing process")
        return False
    
    print(f"✅ Found {len(records)} recent data points!")
    print()
    
    # Analyze the data
    measurements = {}
    sensors = set()
    latest_time = None
    
    for record in records:
        measurement = record.get('_measurement', 'unknown')
        sensor_mac = record.get('sensor_mac', 'unknown')
        timestamp = record.get('_time', '')
        field = record.get('_field', '')
        value = record.get('_value', '')
        
        if measurement not in measurements:
            measurements[measurement] = {}
        
        if field not in measurements[measurement]:
            measurements[measurement][field] = 0
        measurements[measurement][field] += 1
        
        sensors.add(sensor_mac)
        
        if not latest_time or timestamp > latest_time:
            latest_time = timestamp
    
    # Display summary
    print("📊 Data Summary:")
    print(f"   Unique sensors: {len(sensors)}")
    print(f"   Latest data: {latest_time}")
    print()
    
    print("📈 Measurements found:")
    for measurement, fields in measurements.items():
        print(f"   {measurement}:")
        for field, count in fields.items():
            print(f"     - {field}: {count} points")
    print()
    
    print("🏷️  Sensors detected:")
    for sensor in sorted(sensors):
        print(f"   - {sensor}")
    print()
    
    # Show some sample data
    print("📋 Sample data points (most recent):")
    print("-" * 80)
    
    sample_count = 0
    for record in records[:10]:  # Show first 10 records
        measurement = record.get('_measurement', 'unknown')
        sensor_mac = record.get('sensor_mac', 'unknown')
        timestamp = record.get('_time', '')
        field = record.get('_field', '')
        value = record.get('_value', '')
        
        print(f"{timestamp} | {sensor_mac} | {measurement}.{field} = {value}")
        sample_count += 1
    
    print("-" * 80)
    
    # Query for data counts by measurement
    print("\n📊 Data point counts by measurement:")
    
    count_query = f'''
from(bucket: "{bucket}")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] =~ /^ruuvi_/)
  |> group(columns: ["_measurement"])
  |> count()
'''
    
    csv_data = query_influxdb(config, count_query)
    if csv_data:
        count_records = parse_csv_response(csv_data)
        for record in count_records:
            measurement = record.get('_measurement', 'unknown')
            count = record.get('_value', '0')
            print(f"   {measurement}: {count} points")
    
    print("\n🎉 InfluxDB verification completed successfully!")
    print("\n✅ RESULT: Data is being written to InfluxDB correctly!")
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)