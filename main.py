#!/usr/bin/env python3
"""
Ruuvi Sensor Service - Main Entry Point

This is the main entry point for the Ruuvi Sensor Service application.
It provides a command-line interface for managing Ruuvi sensors, collecting
data via BLE, and storing it in InfluxDB.

Usage:
    python main.py --help                 # Show help
    python main.py menu                   # Launch interactive menu
    python main.py discover               # Discover sensors
    python main.py monitor                # Start monitoring
    python main.py status                 # Show system status

Environment Setup:
    Ensure you have activated the virtual environment:
    source .venv/bin/activate

    Copy and configure the environment file:
    cp .env.sample .env
    # Edit .env with your settings

Requirements:
    - Python 3.8+
    - Virtual environment activated
    - Bluetooth adapter available
    - InfluxDB server accessible
    - Proper permissions for BLE access
"""

import sys
import os
import asyncio
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Import CLI after path setup
from src.cli.menu import cli
from src.service.daemon import run_daemon


def check_environment():
    """Check if the environment is properly set up."""
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 8):
        issues.append(f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        issues.append("Virtual environment not activated. Run: source .venv/bin/activate")
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        issues.append(".env file not found. Copy .env.sample to .env and configure it")
    
    # Check required directories
    required_dirs = ["data", "logs", "backups"]
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {dir_name}: {e}")
    
    return issues


def print_banner():
    """Print application banner."""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                           Ruuvi Sensor Service                              ║
║                    BLE Sensor Monitoring & Data Collection                  ║
║                                                                              ║
║  Features:                                                                   ║
║  • Automatic Ruuvi sensor discovery via Bluetooth Low Energy                ║
║  • Real-time environmental data collection                                   ║
║  • InfluxDB integration for time-series data storage                        ║
║  • Interactive CLI with monitoring dashboard                                 ║
║  • Comprehensive logging and performance monitoring                          ║
║                                                                              ║
║  Version: 1.0.0 - Production Ready                                          ║
║  License: MIT                                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def main():
    """Main entry point with environment validation."""
    # Print banner
    print_banner()
    
    # Check environment
    issues = check_environment()
    if issues:
        print("❌ Environment Issues Found:")
        for issue in issues:
            print(f"   • {issue}")
        print("\nPlease resolve these issues before running the application.")
        print("\nQuick Setup:")
        print("1. Activate virtual environment: source .venv/bin/activate")
        print("2. Install dependencies: pip install -r requirements.txt")
        print("3. Copy environment file: cp .env.sample .env")
        print("4. Edit .env with your InfluxDB settings")
        print("5. Run again: python main.py menu")
        print("\nFor automated installation, run: sudo ./install.sh")
        sys.exit(1)
    
    print("✅ Environment check passed")
    print()
    
    # Check if no arguments provided
    if len(sys.argv) == 1:
        print("Usage: python main.py [COMMAND]")
        print("\nAvailable commands:")
        print("  menu      Launch interactive menu")
        print("  discover  Discover Ruuvi sensors")
        print("  monitor   Start sensor monitoring")
        print("  daemon    Run as background daemon")
        print("  status    Show system status")
        print("  --help    Show detailed help")
        print("\nFor interactive mode, run: python main.py menu")
        print("For background service, run: python main.py daemon")
        sys.exit(0)
    
    # Check for daemon mode
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        try:
            print("🚀 Starting Ruuvi Sensor Daemon...")
            asyncio.run(run_daemon())
        except KeyboardInterrupt:
            print("\n\n👋 Daemon interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Daemon error: {e}")
            sys.exit(1)
    else:
        # Run CLI
        try:
            cli()
        except KeyboardInterrupt:
            print("\n\n👋 Application interrupted by user")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("\nIf this error persists, please check:")
            print("1. Virtual environment is activated")
            print("2. All dependencies are installed")
            print("3. .env file is properly configured")
            print("4. InfluxDB server is accessible")
            print("5. Bluetooth adapter is available")
            sys.exit(1)


if __name__ == "__main__":
    main()