#!/usr/bin/env python3
"""
Debug InfluxDB Data Script

This script shows the raw data in InfluxDB to debug any issues.
"""

import requests
import json
import sys
from pathlib import Path


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


def query_influxdb_raw(config, query):
    """Execute a Flux query against InfluxDB and return raw response."""
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
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        return response.text if response.status_code == 200 else None
    except Exception as e:
        print(f"❌ Query error: {e}")
        return None


def main():
    """Main debug function."""
    print("InfluxDB Data Debug")
    print("=" * 40)
    
    config = load_config()
    if not config:
        return False
    
    bucket = config.get('INFLUXDB_BUCKET', 'ruuvi_sensors')
    
    # Simple query to list all measurements
    print("\n1. Listing all measurements in bucket...")
    query1 = f'''
import "influxdata/influxdb/schema"
schema.measurements(bucket: "{bucket}")
'''
    
    result1 = query_influxdb_raw(config, query1)
    if result1:
        print("Raw response:")
        print(result1)
    
    # Query for recent data with all fields
    print("\n2. Querying recent data with all fields...")
    query2 = f'''
from(bucket: "{bucket}")
  |> range(start: -1h)
  |> limit(n: 10)
'''
    
    result2 = query_influxdb_raw(config, query2)
    if result2:
        print("Raw response:")
        print(result2)
    
    # Query for tag values
    print("\n3. Querying tag values...")
    query3 = f'''
import "influxdata/influxdb/schema"
schema.tagValues(bucket: "{bucket}", tag: "sensor_mac")
'''
    
    result3 = query_influxdb_raw(config, query3)
    if result3:
        print("Raw response:")
        print(result3)
    
    return True


if __name__ == "__main__":
    main()