#!/usr/bin/env python3
"""
Health check script for Docker container.
Verifies that the Ruuvi Sensor Service is running properly.
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.utils.config import Config
    from src.influxdb.client import RuuviInfluxDBClient
    from src.ble.scanner import RuuviBLEScanner
except ImportError as e:
    print(f"CRITICAL: Failed to import modules: {e}")
    sys.exit(2)


async def check_configuration():
    """Check if configuration is valid."""
    try:
        config = Config()
        if not config.load():
            print("CRITICAL: Configuration file not found or invalid")
            return False
        
        if not config.validate():
            print("CRITICAL: Configuration validation failed")
            return False
        
        print("OK: Configuration is valid")
        return True
    except Exception as e:
        print(f"CRITICAL: Configuration check failed: {e}")
        return False


async def check_influxdb_connection():
    """Check InfluxDB connectivity."""
    try:
        config = Config()
        config.load()
        
        client = RuuviInfluxDBClient(**config.influxdb_config)
        
        if await client.connect():
            health_ok = await client.health_check()
            await client.disconnect()
            
            if health_ok:
                print("OK: InfluxDB connection successful")
                return True
            else:
                print("WARNING: InfluxDB connection established but health check failed")
                return False
        else:
            print("CRITICAL: Cannot connect to InfluxDB")
            return False
    except Exception as e:
        print(f"CRITICAL: InfluxDB check failed: {e}")
        return False


async def check_bluetooth_adapter():
    """Check Bluetooth adapter availability."""
    try:
        scanner = RuuviBLEScanner()
        # Just check if we can initialize the scanner
        # Don't actually start scanning as it might interfere with the main service
        print("OK: Bluetooth adapter accessible")
        return True
    except Exception as e:
        print(f"WARNING: Bluetooth adapter check failed: {e}")
        # Bluetooth issues are warnings, not critical failures
        return True


async def check_recent_activity():
    """Check if there has been recent sensor activity."""
    try:
        config = Config()
        config.load()
        
        client = RuuviInfluxDBClient(**config.influxdb_config)
        
        if await client.connect():
            # Check for data in the last 10 minutes
            cutoff_time = datetime.now() - timedelta(minutes=10)
            
            # Simple query to check recent data
            query = f"""
            SELECT COUNT(*) FROM ruuvi_measurements 
            WHERE time > '{cutoff_time.isoformat()}Z'
            """
            
            try:
                result = await client.query(query)
                await client.disconnect()
                
                if result and len(result) > 0:
                    count = result[0].get('count', 0)
                    if count > 0:
                        print(f"OK: Recent sensor activity detected ({count} measurements)")
                        return True
                    else:
                        print("WARNING: No recent sensor activity (this may be normal)")
                        return True  # Not critical - sensors might be out of range
                else:
                    print("WARNING: Could not check recent activity")
                    return True
            except Exception as query_error:
                print(f"WARNING: Activity check query failed: {query_error}")
                await client.disconnect()
                return True  # Not critical
        else:
            print("WARNING: Cannot connect to InfluxDB for activity check")
            return True  # Already checked connection above
    except Exception as e:
        print(f"WARNING: Recent activity check failed: {e}")
        return True  # Not critical


async def check_log_files():
    """Check if log files are being written."""
    try:
        log_dir = Path("logs")
        if not log_dir.exists():
            print("WARNING: Log directory does not exist")
            return True  # Not critical
        
        log_file = log_dir / "ruuvi_sensor.log"
        if not log_file.exists():
            print("WARNING: Log file does not exist")
            return True  # Not critical
        
        # Check if log file has been modified recently (within last hour)
        mod_time = datetime.fromtimestamp(log_file.stat().st_mtime)
        if datetime.now() - mod_time < timedelta(hours=1):
            print("OK: Log file is being updated")
            return True
        else:
            print("WARNING: Log file has not been updated recently")
            return True  # Not critical
    except Exception as e:
        print(f"WARNING: Log file check failed: {e}")
        return True  # Not critical


async def main():
    """Run all health checks."""
    print(f"=== Ruuvi Sensor Service Health Check - {datetime.now().isoformat()} ===")
    
    checks = [
        ("Configuration", check_configuration()),
        ("InfluxDB Connection", check_influxdb_connection()),
        ("Bluetooth Adapter", check_bluetooth_adapter()),
        ("Recent Activity", check_recent_activity()),
        ("Log Files", check_log_files()),
    ]
    
    results = []
    for name, check_coro in checks:
        print(f"\nChecking {name}...")
        try:
            result = await check_coro
            results.append(result)
        except Exception as e:
            print(f"CRITICAL: {name} check crashed: {e}")
            results.append(False)
    
    # Determine overall health
    critical_checks = results[:2]  # Configuration and InfluxDB are critical
    warning_checks = results[2:]   # Others are warnings
    
    critical_passed = all(critical_checks)
    warnings_count = sum(1 for r in warning_checks if not r)
    
    print(f"\n=== Health Check Summary ===")
    print(f"Critical checks passed: {sum(critical_checks)}/{len(critical_checks)}")
    print(f"Warning checks failed: {warnings_count}/{len(warning_checks)}")
    
    if critical_passed:
        if warnings_count == 0:
            print("RESULT: HEALTHY - All checks passed")
            return 0
        else:
            print("RESULT: HEALTHY WITH WARNINGS - Critical systems operational")
            return 0
    else:
        print("RESULT: UNHEALTHY - Critical systems failing")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nHealth check interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"CRITICAL: Health check failed with exception: {e}")
        sys.exit(2)