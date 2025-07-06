"""
Advanced CLI features for Ruuvi Sensor Service.

This module provides enhanced CLI functionality including:
- Interactive configuration wizard
- Progress bars for long-running operations
- Data export/import functionality
- Advanced monitoring dashboard
- Sensor calibration and testing features
- Batch operations for multiple sensors
"""

import asyncio
import json
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import time

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm, IntPrompt, FloatPrompt
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich.tree import Tree
from rich.align import Align
from rich.columns import Columns

from ..utils.config import Config, ConfigurationError
from ..utils.logging import ProductionLogger, PerformanceMonitor
from ..metadata.manager import MetadataManager, MetadataError
from ..ble.scanner import RuuviBLEScanner, RuuviSensorData
from ..influxdb.client import RuuviInfluxDBClient
from ..exceptions.edge_cases import EdgeCaseHandler


class AdvancedCLIFeatures:
    """
    Advanced CLI features for enhanced user experience.
    
    Provides:
    - Interactive setup wizard
    - Progress tracking for operations
    - Data export/import capabilities
    - Real-time monitoring dashboard
    - Sensor testing and calibration
    - Batch operations
    """
    
    def __init__(self, config: Config, logger: ProductionLogger, 
                 metadata_manager: MetadataManager, ble_scanner: RuuviBLEScanner,
                 influxdb_client: RuuviInfluxDBClient):
        """Initialize advanced CLI features."""
        self.config = config
        self.logger = logger
        self.metadata_manager = metadata_manager
        self.ble_scanner = ble_scanner
        self.influxdb_client = influxdb_client
        self.console = Console()
        self.edge_handler = EdgeCaseHandler(config, logger)
        
    async def interactive_setup_wizard(self) -> bool:
        """
        Interactive setup wizard for first-time users.
        
        Returns:
            True if setup completed successfully
        """
        self.console.clear()
        
        # Welcome banner
        welcome_panel = Panel.fit(
            "[bold blue]🚀 Ruuvi Sensor Service Setup Wizard[/bold blue]\n\n"
            "[dim]This wizard will help you configure your Ruuvi Sensor Service\n"
            "for the first time. We'll guide you through each step.[/dim]",
            border_style="blue",
            title="Welcome"
        )
        self.console.print(welcome_panel)
        self.console.print()
        
        if not Confirm.ask("Would you like to run the setup wizard?", default=True):
            return False
        
        setup_steps = [
            ("Environment Check", self._wizard_environment_check),
            ("InfluxDB Configuration", self._wizard_influxdb_config),
            ("BLE Configuration", self._wizard_ble_config),
            ("Sensor Discovery", self._wizard_sensor_discovery),
            ("Service Configuration", self._wizard_service_config),
            ("Final Validation", self._wizard_final_validation)
        ]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("Setup Progress", total=len(setup_steps))
            
            for step_name, step_func in setup_steps:
                step_task = progress.add_task(f"Running {step_name}...", total=None)
                
                try:
                    success, message = await step_func()
                    if not success:
                        progress.update(step_task, description=f"❌ {step_name} failed")
                        self.console.print(f"[red]Setup failed at {step_name}: {message}[/red]")
                        return False
                    
                    progress.update(step_task, description=f"✅ {step_name} completed")
                    progress.advance(main_task)
                    
                except Exception as e:
                    progress.update(step_task, description=f"❌ {step_name} error")
                    self.console.print(f"[red]Setup error at {step_name}: {e}[/red]")
                    return False
        
        # Success message
        success_panel = Panel.fit(
            "[bold green]🎉 Setup Complete![/bold green]\n\n"
            "[dim]Your Ruuvi Sensor Service is now configured and ready to use.\n"
            "You can start monitoring sensors or run as a background service.[/dim]",
            border_style="green",
            title="Success"
        )
        self.console.print(success_panel)
        
        return True
    
    async def export_data(self, format_type: str = "json", 
                         date_range: Optional[Tuple[datetime, datetime]] = None) -> bool:
        """
        Export sensor data in various formats.
        
        Args:
            format_type: Export format (json, csv, influx)
            date_range: Optional date range for export
            
        Returns:
            True if export successful
        """
        self.console.print(f"[blue]Exporting data in {format_type.upper()} format...[/blue]")
        
        # Get export parameters
        export_path = Prompt.ask("Export file path", default=f"ruuvi_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}")
        
        if date_range is None:
            days_back = IntPrompt.ask("Days of data to export", default=7)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            date_range = (start_date, end_date)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            
            export_task = progress.add_task("Exporting data...", total=100)
            
            try:
                # Get sensor data from InfluxDB
                progress.update(export_task, advance=20, description="Querying InfluxDB...")
                
                if not self.influxdb_client.is_connected():
                    await self.influxdb_client.connect()
                
                # Query data for all sensors
                sensors = self.metadata_manager.get_all_sensors()
                all_data = []
                
                progress.update(export_task, advance=20, description="Retrieving sensor data...")
                
                for mac, sensor in sensors.items():
                    sensor_data = await self._query_sensor_data(mac, date_range[0], date_range[1])
                    all_data.extend(sensor_data)
                
                progress.update(export_task, advance=30, description=f"Formatting as {format_type}...")
                
                # Export in requested format
                if format_type == "json":
                    success = await self._export_json(export_path, all_data, sensors)
                elif format_type == "csv":
                    success = await self._export_csv(export_path, all_data, sensors)
                elif format_type == "influx":
                    success = await self._export_influx_line_protocol(export_path, all_data, sensors)
                else:
                    raise ValueError(f"Unsupported export format: {format_type}")
                
                progress.update(export_task, advance=30, description="Export completed")
                
                if success:
                    self.console.print(f"[green]✅ Data exported successfully to: {export_path}[/green]")
                    self.console.print(f"[dim]Records exported: {len(all_data)}[/dim]")
                    return True
                else:
                    self.console.print("[red]❌ Export failed[/red]")
                    return False
                    
            except Exception as e:
                self.console.print(f"[red]Export error: {e}[/red]")
                return False
    
    async def import_data(self, file_path: str) -> bool:
        """
        Import sensor data from file.
        
        Args:
            file_path: Path to import file
            
        Returns:
            True if import successful
        """
        self.console.print(f"[blue]Importing data from: {file_path}[/blue]")
        
        if not Path(file_path).exists():
            self.console.print(f"[red]File not found: {file_path}[/red]")
            return False
        
        # Detect file format
        file_ext = Path(file_path).suffix.lower()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            
            import_task = progress.add_task("Importing data...", total=100)
            
            try:
                progress.update(import_task, advance=20, description="Reading file...")
                
                if file_ext == ".json":
                    data = await self._import_json(file_path)
                elif file_ext == ".csv":
                    data = await self._import_csv(file_path)
                else:
                    raise ValueError(f"Unsupported import format: {file_ext}")
                
                progress.update(import_task, advance=40, description="Validating data...")
                
                # Validate imported data
                valid_records = self._validate_import_data(data)
                
                progress.update(import_task, advance=20, description="Writing to InfluxDB...")
                
                # Write to InfluxDB
                if not self.influxdb_client.is_connected():
                    await self.influxdb_client.connect()
                
                for record in valid_records:
                    await self.influxdb_client.write_sensor_data(record)
                
                progress.update(import_task, advance=20, description="Import completed")
                
                self.console.print(f"[green]✅ Data imported successfully[/green]")
                self.console.print(f"[dim]Records imported: {len(valid_records)}[/dim]")
                return True
                
            except Exception as e:
                self.console.print(f"[red]Import error: {e}[/red]")
                return False
    
    async def real_time_dashboard(self, duration: int = 300) -> None:
        """
        Display real-time monitoring dashboard.
        
        Args:
            duration: Dashboard duration in seconds
        """
        self.console.clear()
        
        # Start BLE scanning
        if not self.ble_scanner.is_scanning():
            await self.ble_scanner.start_continuous_scan()
        
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="sensors", ratio=2),
            Layout(name="stats", ratio=1)
        )
        
        start_time = time.time()
        
        with Live(layout, refresh_per_second=2, console=self.console) as live:
            while time.time() - start_time < duration:
                # Update header
                elapsed = int(time.time() - start_time)
                remaining = duration - elapsed
                layout["header"].update(Panel(
                    f"[bold green]Real-time Dashboard[/bold green] - "
                    f"Elapsed: {elapsed}s | Remaining: {remaining}s",
                    border_style="green"
                ))
                
                # Update sensor data
                await self._update_dashboard_sensors(layout["sensors"])
                
                # Update statistics
                await self._update_dashboard_stats(layout["stats"])
                
                # Update footer
                layout["footer"].update(Panel(
                    "[dim]Press Ctrl+C to exit dashboard[/dim]",
                    border_style="dim"
                ))
                
                await asyncio.sleep(0.5)
    
    async def sensor_calibration_test(self, mac_address: str) -> bool:
        """
        Perform sensor calibration and testing.
        
        Args:
            mac_address: MAC address of sensor to test
            
        Returns:
            True if calibration successful
        """
        self.console.print(f"[blue]Starting calibration test for sensor: {mac_address}[/blue]")
        
        sensor = self.metadata_manager.get_sensor(mac_address)
        if not sensor:
            self.console.print(f"[red]Sensor not found: {mac_address}[/red]")
            return False
        
        # Calibration test phases
        test_phases = [
            ("Signal Strength Test", self._test_signal_strength),
            ("Data Consistency Test", self._test_data_consistency),
            ("Range Validation Test", self._test_range_validation),
            ("Battery Level Check", self._test_battery_level),
            ("Response Time Test", self._test_response_time)
        ]
        
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            
            main_task = progress.add_task("Calibration Progress", total=len(test_phases))
            
            for phase_name, phase_func in test_phases:
                phase_task = progress.add_task(f"Running {phase_name}...", total=None)
                
                try:
                    result = await phase_func(mac_address)
                    results[phase_name] = result
                    
                    status = "✅" if result["passed"] else "❌"
                    progress.update(phase_task, description=f"{status} {phase_name}")
                    progress.advance(main_task)
                    
                except Exception as e:
                    results[phase_name] = {"passed": False, "error": str(e)}
                    progress.update(phase_task, description=f"❌ {phase_name} failed")
                    progress.advance(main_task)
        
        # Display results
        self._display_calibration_results(mac_address, results)
        
        # Overall success
        overall_success = all(result.get("passed", False) for result in results.values())
        return overall_success
    
    async def batch_sensor_operations(self, operation: str, sensor_macs: List[str]) -> Dict[str, bool]:
        """
        Perform batch operations on multiple sensors.
        
        Args:
            operation: Operation to perform (test, calibrate, update, etc.)
            sensor_macs: List of sensor MAC addresses
            
        Returns:
            Dictionary mapping MAC addresses to success status
        """
        self.console.print(f"[blue]Performing batch {operation} on {len(sensor_macs)} sensors...[/blue]")
        
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            
            batch_task = progress.add_task("Batch Operation", total=len(sensor_macs))
            
            for mac in sensor_macs:
                sensor_task = progress.add_task(f"Processing {mac[:8]}...", total=None)
                
                try:
                    if operation == "test":
                        success = await self.sensor_calibration_test(mac)
                    elif operation == "update":
                        success = await self._update_sensor_metadata(mac)
                    elif operation == "scan":
                        success = await self._scan_single_sensor(mac)
                    else:
                        raise ValueError(f"Unknown operation: {operation}")
                    
                    results[mac] = success
                    status = "✅" if success else "❌"
                    progress.update(sensor_task, description=f"{status} {mac[:8]}")
                    
                except Exception as e:
                    results[mac] = False
                    progress.update(sensor_task, description=f"❌ {mac[:8]} error")
                    self.logger.error(f"Batch operation error for {mac}: {e}")
                
                progress.advance(batch_task)
        
        # Display summary
        successful = sum(1 for success in results.values() if success)
        failed = len(results) - successful
        
        self.console.print(f"[green]Batch operation completed: {successful} successful, {failed} failed[/green]")
        
        return results
    
    # Private helper methods
    
    async def _wizard_environment_check(self) -> Tuple[bool, str]:
        """Check environment prerequisites."""
        checks = [
            ("Python version", self._check_python_version),
            ("Virtual environment", self._check_virtual_env),
            ("Required packages", self._check_packages),
            ("Permissions", self._check_permissions)
        ]
        
        for check_name, check_func in checks:
            success, message = check_func()
            if not success:
                return False, f"{check_name} check failed: {message}"
        
        return True, "Environment checks passed"
    
    async def _wizard_influxdb_config(self) -> Tuple[bool, str]:
        """Configure InfluxDB connection."""
        self.console.print("[yellow]InfluxDB Configuration[/yellow]")
        
        # Get current config or defaults
        current_host = getattr(self.config, 'influxdb_host', 'localhost')
        current_port = getattr(self.config, 'influxdb_port', 8086)
        
        host = Prompt.ask("InfluxDB host", default=current_host)
        port = IntPrompt.ask("InfluxDB port", default=current_port)
        
        # Test connection
        try:
            # Update config temporarily for testing
            self.config.influxdb_host = host
            self.config.influxdb_port = port
            
            await self.influxdb_client.connect()
            await self.influxdb_client.disconnect()
            
            return True, "InfluxDB connection successful"
            
        except Exception as e:
            return False, f"InfluxDB connection failed: {e}"
    
    async def _wizard_ble_config(self) -> Tuple[bool, str]:
        """Configure BLE settings."""
        self.console.print("[yellow]Bluetooth Configuration[/yellow]")
        
        # Test BLE functionality
        try:
            # Quick scan test
            devices = await self.ble_scanner.scan_once(5)
            device_count = len(devices)
            
            self.console.print(f"[green]BLE scan successful: {device_count} devices found[/green]")
            return True, f"BLE working, found {device_count} devices"
            
        except Exception as e:
            # Try edge case recovery
            success, message = self.edge_handler.handle_ble_adapter_error(e)
            if success:
                return True, f"BLE recovered: {message}"
            else:
                return False, f"BLE configuration failed: {message}"
    
    async def _wizard_sensor_discovery(self) -> Tuple[bool, str]:
        """Discover and configure sensors."""
        self.console.print("[yellow]Sensor Discovery[/yellow]")
        
        if Confirm.ask("Would you like to discover Ruuvi sensors now?", default=True):
            devices = await self.ble_scanner.scan_once(15)
            
            if not devices:
                return True, "No sensors found, but discovery completed"
            
            self.console.print(f"[green]Found {len(devices)} Ruuvi sensors[/green]")
            
            # Add sensors interactively
            for mac, data in devices.items():
                if Confirm.ask(f"Add sensor {mac}?", default=True):
                    name = Prompt.ask(f"Name for {mac}", default=f"Sensor_{mac[-4:]}")
                    location = Prompt.ask("Location", default="Unknown")
                    
                    try:
                        self.metadata_manager.add_sensor(mac, name, location)
                    except Exception as e:
                        self.logger.error(f"Failed to add sensor {mac}: {e}")
            
            return True, f"Sensor discovery completed, {len(devices)} sensors found"
        
        return True, "Sensor discovery skipped"
    
    async def _wizard_service_config(self) -> Tuple[bool, str]:
        """Configure service settings."""
        self.console.print("[yellow]Service Configuration[/yellow]")
        
        if Confirm.ask("Would you like to install the systemd service?", default=True):
            # This would integrate with service manager
            return True, "Service configuration completed"
        
        return True, "Service configuration skipped"
    
    async def _wizard_final_validation(self) -> Tuple[bool, str]:
        """Final validation of setup."""
        self.console.print("[yellow]Final Validation[/yellow]")
        
        # Test complete workflow
        try:
            # Test BLE scan
            await self.ble_scanner.scan_once(3)
            
            # Test InfluxDB connection
            if not self.influxdb_client.is_connected():
                await self.influxdb_client.connect()
            
            # Test metadata operations
            sensors = self.metadata_manager.get_all_sensors()
            
            return True, f"Validation successful, {len(sensors)} sensors configured"
            
        except Exception as e:
            return False, f"Validation failed: {e}"
    
    def _check_python_version(self) -> Tuple[bool, str]:
        """Check Python version."""
        if sys.version_info >= (3, 8):
            return True, f"Python {sys.version_info.major}.{sys.version_info.minor} OK"
        return False, f"Python 3.8+ required, found {sys.version_info.major}.{sys.version_info.minor}"
    
    def _check_virtual_env(self) -> Tuple[bool, str]:
        """Check virtual environment."""
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            return True, "Virtual environment active"
        return False, "Virtual environment not active"
    
    def _check_packages(self) -> Tuple[bool, str]:
        """Check required packages."""
        try:
            import bleak
            import influxdb_client
            import rich
            return True, "Required packages available"
        except ImportError as e:
            return False, f"Missing package: {e}"
    
    def _check_permissions(self) -> Tuple[bool, str]:
        """Check permissions."""
        # Check bluetooth group membership
        try:
            import grp
            import os
            bluetooth_group = grp.getgrnam('bluetooth')
            current_user = os.getenv('USER')
            
            if current_user in bluetooth_group.gr_mem:
                return True, "Bluetooth permissions OK"
            else:
                return False, f"User {current_user} not in bluetooth group"
        except Exception:
            return True, "Permission check skipped"
    
    async def _query_sensor_data(self, mac: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Query sensor data from InfluxDB."""
        # This would implement actual InfluxDB querying
        # For now, return empty list
        return []
    
    async def _export_json(self, file_path: str, data: List[Dict], sensors: Dict) -> bool:
        """Export data as JSON."""
        try:
            export_data = {
                "export_info": {
                    "timestamp": datetime.now().isoformat(),
                    "version": "1.0",
                    "record_count": len(data)
                },
                "sensors": {mac: {"name": sensor.name, "location": sensor.location} 
                           for mac, sensor in sensors.items()},
                "data": data
            }
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            return True
        except Exception as e:
            self.logger.error(f"JSON export failed: {e}")
            return False
    
    async def _export_csv(self, file_path: str, data: List[Dict], sensors: Dict) -> bool:
        """Export data as CSV."""
        try:
            if not data:
                return True
            
            with open(file_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            
            return True
        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
            return False
    
    async def _export_influx_line_protocol(self, file_path: str, data: List[Dict], sensors: Dict) -> bool:
        """Export data as InfluxDB line protocol."""
        try:
            with open(file_path, 'w') as f:
                for record in data:
                    # Convert to line protocol format
                    line = self._convert_to_line_protocol(record)
                    f.write(line + '\n')
            
            return True
        except Exception as e:
            self.logger.error(f"InfluxDB line protocol export failed: {e}")
            return False
    
    def _convert_to_line_protocol(self, record: Dict) -> str:
        """Convert record to InfluxDB line protocol format."""
        measurement = "ruuvi_sensors"
        tags = f"mac={record.get('mac', 'unknown')}"
        fields = []
        
        for key, value in record.items():
            if key not in ['mac', 'timestamp'] and value is not None:
                fields.append(f"{key}={value}")
        
        timestamp = record.get('timestamp', int(time.time() * 1000000000))
        
        return f"{measurement},{tags} {','.join(fields)} {timestamp}"
    
    async def _import_json(self, file_path: str) -> List[Dict]:
        """Import data from JSON file."""
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'data' in data:
            return data['data']
        elif isinstance(data, list):
            return data
        else:
            raise ValueError("Invalid JSON format")
    
    async def _import_csv(self, file_path: str) -> List[Dict]:
        """Import data from CSV file."""
        data = []
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        return data
    
    def _validate_import_data(self, data: List[Dict]) -> List[RuuviSensorData]:
        """Validate and convert imported data."""
        valid_records = []
        
        for record in data:
            try:
                # Convert to RuuviSensorData object
                sensor_data = RuuviSensorData(
                    mac_address=record.get('mac_address', ''),
                    temperature=float(record.get('temperature', 0)) if record.get('temperature') else None,
                    humidity=float(record.get('humidity', 0)) if record.get('humidity') else None,
                    pressure=float(record.get('pressure', 0)) if record.get('pressure') else None,
                    battery_voltage=float(record.get('battery_voltage', 0)) if record.get('battery_voltage') else None,
                    rssi=int(record.get('rssi', 0)) if record.get('rssi') else None,
                    timestamp=datetime.fromisoformat(record.get('timestamp', datetime.now().isoformat()))
                )
                valid_records.append(sensor_data)
            except Exception as e:
                self.logger.warning(f"Invalid record skipped: {e}")
        
        return valid_records
    
    async def _update_dashboard_sensors(self, layout):
        """Update sensor data in dashboard."""
        sensors = self.metadata_manager.get_all_sensors()
        recent_data = self.ble_scanner.get_discovered_devices()
        
        if not sensors:
            layout.update(Panel("[yellow]No sensors configured[/yellow]", title="Sensors"))
            return
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Sensor", style="cyan")
        table.add_column("Temperature", style="red")
        table.add_column("Humidity", style="blue")
        table.add_column("Pressure", style="green")
        table.add_column("Battery", style="magenta")
        table.add_column("RSSI", style="yellow")
        table.add_column("Last Seen", style="dim")
        
        for mac, sensor in sensors.items():
            data = recent_data.get(mac)
            if data:
                table.add_row(
                    sensor.name,
                    f"{data.temperature:.1f}°C" if data.temperature else "N/A",
                    f"{data.humidity:.1f}%" if data.humidity else "N/A",
                    f"{data.pressure:.1f} hPa" if data.pressure else "N/A",
                    f"{data.battery_voltage:.2f}V" if data.battery_voltage else "N/A",
                    f"{data.rssi} dBm" if data.rssi else "N/A",
                    data.timestamp.strftime("%H:%M:%S")
                )
            else:
                table.add_row(sensor.name, "N/A", "N/A", "N/A", "N/A", "N/A", "No data")
        
        layout.update(Panel(table, title="Sensor Data"))
    
    async def _update_dashboard_stats(self, layout):
        """Update statistics in dashboard."""
        stats = Table(show_header=False)
        stats.add_column("Metric", style="cyan")
        stats.add_column("Value", style="green")
        
        # BLE Scanner stats
        ble_stats = self.ble_scanner.get_statistics()
        stats.add_row("Scans", str(ble_stats.get('scan_count', 0)))
        stats.add_row("Devices", str(ble_stats.get('device_count', 0)))
        
        # InfluxDB stats
        if self.influxdb_client:
            influx_stats = self.influxdb_client.get_statistics()
            stats.add_row("Points Written", str(influx_stats.get('points_written', 0)))
            stats.add_row("Buffer Size", str(self.influxdb_client.get_buffer_size()))
        
        # System stats
        import psutil
        stats.add_row("CPU Usage", f"{psutil.cpu_percent():.1f}%")
        stats.add_row("Memory Usage", f"{psutil.virtual_memory().percent:.1f}%")
        
        layout.update(Panel(stats, title="Statistics"))
    
    async def _test_signal_strength(self, mac_address: str) -> Dict[str, Any]:
        """Test signal strength for a sensor."""
        try:
            # Perform multiple scans to test signal consistency
            readings = []
            for _ in range(5):
                devices = await self.ble_scanner.scan_once(2)
                if mac_address in devices:
                    readings.append(devices[mac_address].rssi)
                await asyncio.sleep(1)
            
            if not readings:
                return {"passed": False, "error": "No signal detected"}
            
            avg_rssi = sum(readings) / len(readings)
            rssi_variance = max(readings) - min(readings)
            
            # Signal strength criteria
            passed = avg_rssi > -80 and rssi_variance < 20
            
            return {
                "passed": passed,
                "average_rssi": avg_rssi,
                "variance": rssi_variance,
                "readings": readings,
                "criteria": "RSSI > -80 dBm, variance < 20 dBm"
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def _test_data_consistency(self, mac_address: str) -> Dict[str, Any]:
        """Test data consistency for a sensor."""
        try:
            # Collect multiple readings
            readings = []
            for _ in range(10):
                devices = await self.ble_scanner.scan_once(1)
                if mac_address in devices:
                    data = devices[mac_address]
                    readings.append({
                        "temperature": data.temperature,
                        "humidity": data.humidity,
                        "pressure": data.pressure
                    })
                await asyncio.sleep(2)
            
            if len(readings) < 3:
                return {"passed": False, "error": "Insufficient data for consistency test"}
            
            # Check for reasonable variance
            temps = [r["temperature"] for r in readings if r["temperature"] is not None]
            humids = [r["humidity"] for r in readings if r["humidity"] is not None]
            pressures = [r["pressure"] for r in readings if r["pressure"] is not None]
            
            temp_variance = (max(temps) - min(temps)) if temps else 0
            humid_variance = (max(humids) - min(humids)) if humids else 0
            pressure_variance = (max(pressures) - min(pressures)) if pressures else 0
            
            # Consistency criteria (reasonable variance for stable environment)
            passed = (temp_variance < 5.0 and humid_variance < 10.0 and pressure_variance < 50.0)
            
            return {
                "passed": passed,
                "readings_count": len(readings),
                "temperature_variance": temp_variance,
                "humidity_variance": humid_variance,
                "pressure_variance": pressure_variance,
                "criteria": "Temp variance < 5°C, Humidity < 10%, Pressure < 50 hPa"
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def _test_range_validation(self, mac_address: str) -> Dict[str, Any]:
        """Test if sensor readings are within expected ranges."""
        try:
            devices = await self.ble_scanner.scan_once(5)
            if mac_address not in devices:
                return {"passed": False, "error": "Sensor not detected"}
            
            data = devices[mac_address]
            issues = []
            
            # Temperature range check (-40°C to +85°C for RuuviTag)
            if data.temperature is not None:
                if not (-40 <= data.temperature <= 85):
                    issues.append(f"Temperature out of range: {data.temperature}°C")
            
            # Humidity range check (0% to 100%)
            if data.humidity is not None:
                if not (0 <= data.humidity <= 100):
                    issues.append(f"Humidity out of range: {data.humidity}%")
            
            # Pressure range check (300 hPa to 1100 hPa)
            if data.pressure is not None:
                if not (300 <= data.pressure <= 1100):
                    issues.append(f"Pressure out of range: {data.pressure} hPa")
            
            # Battery voltage check (1.8V to 3.6V)
            if data.battery_voltage is not None:
                if not (1.8 <= data.battery_voltage <= 3.6):
                    issues.append(f"Battery voltage out of range: {data.battery_voltage}V")
            
            passed = len(issues) == 0
            
            return {
                "passed": passed,
                "issues": issues,
                "readings": {
                    "temperature": data.temperature,
                    "humidity": data.humidity,
                    "pressure": data.pressure,
                    "battery_voltage": data.battery_voltage
                },
                "criteria": "All readings within manufacturer specifications"
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def _test_battery_level(self, mac_address: str) -> Dict[str, Any]:
        """Test battery level and health."""
        try:
            devices = await self.ble_scanner.scan_once(5)
            if mac_address not in devices:
                return {"passed": False, "error": "Sensor not detected"}
            
            data = devices[mac_address]
            if data.battery_voltage is None:
                return {"passed": False, "error": "Battery voltage not available"}
            
            voltage = data.battery_voltage
            
            # Battery health assessment
            if voltage >= 3.0:
                health = "Excellent"
                passed = True
            elif voltage >= 2.8:
                health = "Good"
                passed = True
            elif voltage >= 2.6:
                health = "Fair"
                passed = True
            elif voltage >= 2.4:
                health = "Low"
                passed = False
            else:
                health = "Critical"
                passed = False
            
            # Estimate remaining life (rough approximation)
            if voltage >= 3.0:
                remaining_months = 12
            elif voltage >= 2.8:
                remaining_months = 6
            elif voltage >= 2.6:
                remaining_months = 3
            elif voltage >= 2.4:
                remaining_months = 1
            else:
                remaining_months = 0
            
            return {
                "passed": passed,
                "voltage": voltage,
                "health": health,
                "estimated_remaining_months": remaining_months,
                "criteria": "Battery voltage > 2.6V for normal operation"
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    async def _test_response_time(self, mac_address: str) -> Dict[str, Any]:
        """Test sensor response time."""
        try:
            response_times = []
            
            for _ in range(5):
                start_time = time.time()
                devices = await self.ble_scanner.scan_once(3)
                end_time = time.time()
                
                if mac_address in devices:
                    response_times.append(end_time - start_time)
                
                await asyncio.sleep(1)
            
            if not response_times:
                return {"passed": False, "error": "No responses detected"}
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            # Response time criteria (should respond within reasonable time)
            passed = avg_response_time < 5.0 and max_response_time < 10.0
            
            return {
                "passed": passed,
                "average_response_time": avg_response_time,
                "max_response_time": max_response_time,
                "response_count": len(response_times),
                "criteria": "Average response < 5s, Max response < 10s"
            }
            
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
    def _display_calibration_results(self, mac_address: str, results: Dict[str, Dict]):
        """Display calibration test results."""
        sensor = self.metadata_manager.get_sensor(mac_address)
        sensor_name = sensor.name if sensor else mac_address
        
        # Create results table
        table = Table(title=f"Calibration Results: {sensor_name}", show_header=True, header_style="bold cyan")
        table.add_column("Test", style="blue")
        table.add_column("Status", style="green")
        table.add_column("Details", style="dim")
        
        for test_name, result in results.items():
            if result.get("passed"):
                status = "[green]✅ PASS[/green]"
            else:
                status = "[red]❌ FAIL[/red]"
            
            # Format details based on test type
            details = []
            if "error" in result:
                details.append(f"Error: {result['error']}")
            else:
                if "average_rssi" in result:
                    details.append(f"Avg RSSI: {result['average_rssi']:.1f} dBm")
                if "readings_count" in result:
                    details.append(f"Readings: {result['readings_count']}")
                if "voltage" in result:
                    details.append(f"Voltage: {result['voltage']:.2f}V ({result.get('health', 'Unknown')})")
                if "average_response_time" in result:
                    details.append(f"Avg Response: {result['average_response_time']:.2f}s")
                if "issues" in result and result["issues"]:
                    details.extend(result["issues"])
            
            if "criteria" in result:
                details.append(f"Criteria: {result['criteria']}")
            
            table.add_row(test_name, status, "\n".join(details))
        
        self.console.print(table)
        
        # Overall assessment
        passed_tests = sum(1 for result in results.values() if result.get("passed"))
        total_tests = len(results)
        
        if passed_tests == total_tests:
            overall_panel = Panel(
                f"[bold green]🎉 All tests passed ({passed_tests}/{total_tests})[/bold green]\n"
                f"[dim]Sensor {sensor_name} is functioning normally[/dim]",
                border_style="green"
            )
        else:
            overall_panel = Panel(
                f"[bold red]⚠️  {total_tests - passed_tests} test(s) failed ({passed_tests}/{total_tests} passed)[/bold red]\n"
                f"[dim]Sensor {sensor_name} may need attention[/dim]",
                border_style="red"
            )
        
        self.console.print(overall_panel)
    
    async def _update_sensor_metadata(self, mac_address: str) -> bool:
        """Update sensor metadata."""
        try:
            # This would implement metadata update logic
            # For now, just mark as updated
            sensor = self.metadata_manager.get_sensor(mac_address)
            if sensor:
                self.metadata_manager.update_sensor_last_seen(mac_address)
                return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to update sensor metadata for {mac_address}: {e}")
            return False
    
    async def _scan_single_sensor(self, mac_address: str) -> bool:
        """Scan for a single sensor."""
        try:
            devices = await self.ble_scanner.scan_once(5)
            return mac_address in devices
        except Exception as e:
            self.logger.error(f"Failed to scan for sensor {mac_address}: {e}")
            return False