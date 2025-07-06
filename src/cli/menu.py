"""
Main CLI menu system for Ruuvi Sensor Service.
Provides interactive command-line interface using click and rich.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.layout import Layout
from rich.live import Live

from ..utils.config import Config, ConfigurationError
from ..utils.logging import ProductionLogger, PerformanceMonitor
from ..metadata.manager import MetadataManager, MetadataError
from ..ble.scanner import RuuviBLEScanner, RuuviSensorData
from ..influxdb.client import RuuviInfluxDBClient
from ..service.manager import ServiceManager, ServiceStatus, ServiceManagerError
from ..exceptions.edge_cases import EdgeCaseHandler
from .advanced_features import AdvancedCLIFeatures


class CLIError(Exception):
    """Base exception for CLI operations."""
    pass


class RuuviCLI:
    """
    Main CLI application for Ruuvi Sensor Service.
    
    Features:
    - Interactive menu system
    - Sensor discovery and management
    - Configuration validation
    - Real-time monitoring
    - Service management
    """
    
    def __init__(self):
        """Initialize CLI application."""
        self.console = Console()
        self.config: Optional[Config] = None
        self.logger: Optional[ProductionLogger] = None
        self.performance_monitor: Optional[PerformanceMonitor] = None
        self.metadata_manager: Optional[MetadataManager] = None
        self.ble_scanner: Optional[RuuviBLEScanner] = None
        self.influxdb_client: Optional[RuuviInfluxDBClient] = None
        self.service_manager: Optional[ServiceManager] = None
        self.edge_handler: Optional[EdgeCaseHandler] = None
        self.advanced_features: Optional[AdvancedCLIFeatures] = None
        
        # CLI state
        self._running = False
        self._monitoring = False
    
    def _initialize_components(self):
        """Initialize all components with error handling."""
        try:
            # Load configuration
            self.config = Config()
            self.config.validate_environment()
            
            # Initialize logging
            self.logger = ProductionLogger(self.config)
            self.performance_monitor = PerformanceMonitor(self.logger)
            
            # Initialize metadata manager
            self.metadata_manager = MetadataManager(self.config, self.logger)
            
            # Initialize BLE scanner
            self.ble_scanner = RuuviBLEScanner(self.config, self.logger, self.performance_monitor)
            
            # Initialize InfluxDB client
            self.influxdb_client = RuuviInfluxDBClient(self.config, self.logger, self.performance_monitor)
            
            # Initialize service manager
            self.service_manager = ServiceManager(self.config, self.logger)
            
            # Initialize edge case handler
            self.edge_handler = EdgeCaseHandler(self.config, self.logger)
            
            # Initialize advanced features
            self.advanced_features = AdvancedCLIFeatures(
                self.config, self.logger, self.metadata_manager,
                self.ble_scanner, self.influxdb_client
            )
            
            self.logger.info("CLI components initialized successfully")
            
        except ConfigurationError as e:
            self.console.print(f"[red]Configuration Error: {e}[/red]")
            raise CLIError(f"Configuration error: {e}")
        except Exception as e:
            self.console.print(f"[red]Initialization Error: {e}[/red]")
            raise CLIError(f"Initialization error: {e}")
    
    def _print_header(self):
        """Print application header."""
        header = Panel.fit(
            "[bold blue]Ruuvi Sensor Service[/bold blue]\n"
            "[dim]BLE sensor monitoring and data collection[/dim]",
            border_style="blue"
        )
        self.console.print(header)
        self.console.print()
    
    def _print_system_status(self):
        """Print system status information."""
        if not all([self.config, self.logger, self.metadata_manager]):
            self.console.print("[red]System not initialized[/red]")
            return
        
        # Create status table
        table = Table(title="System Status", show_header=True, header_style="bold magenta")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="dim")
        
        # Configuration status
        try:
            self.config.validate_environment()
            table.add_row("Configuration", "✓ Valid", f"Environment: {self.config.environment}")
        except Exception as e:
            table.add_row("Configuration", "✗ Invalid", str(e))
        
        # Virtual environment status
        if self.config.is_virtual_environment():
            table.add_row("Virtual Environment", "✓ Active", f"Python: {sys.version.split()[0]}")
        else:
            table.add_row("Virtual Environment", "⚠ Not Active", "Consider using virtual environment")
        
        # Metadata status
        try:
            metadata = self.metadata_manager.load()
            sensor_count = len(metadata.sensors)
            active_count = len(metadata.get_active_sensors())
            table.add_row("Metadata", "✓ Loaded", f"{sensor_count} sensors ({active_count} active)")
        except Exception as e:
            table.add_row("Metadata", "✗ Error", str(e))
        
        # InfluxDB status
        if self.influxdb_client and self.influxdb_client.is_connected():
            stats = self.influxdb_client.get_statistics()
            table.add_row("InfluxDB", "✓ Connected", f"Points written: {stats['points_written']}")
        else:
            table.add_row("InfluxDB", "✗ Disconnected", "Not connected")
        
        # BLE Scanner status
        if self.ble_scanner:
            stats = self.ble_scanner.get_statistics()
            table.add_row("BLE Scanner", "✓ Ready", f"Scans: {stats['scan_count']}, Devices: {stats['device_count']}")
        else:
            table.add_row("BLE Scanner", "✗ Not Ready", "Scanner not initialized")
        
        self.console.print(table)
        self.console.print()
    
    def _print_sensor_list(self):
        """Print list of configured sensors."""
        if not self.metadata_manager:
            self.console.print("[red]Metadata manager not initialized[/red]")
            return
        
        try:
            sensors = self.metadata_manager.get_all_sensors()
            
            if not sensors:
                self.console.print("[yellow]No sensors configured[/yellow]")
                return
            
            # Create sensors table
            table = Table(title="Configured Sensors", show_header=True, header_style="bold magenta")
            table.add_column("MAC Address", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Location", style="blue")
            table.add_column("Status", style="yellow")
            table.add_column("Last Seen", style="dim")
            
            for mac, sensor in sensors.items():
                status = "🟢 Active" if sensor.enabled and sensor.status.value == "active" else "🔴 Inactive"
                last_seen = sensor.last_seen.strftime("%Y-%m-%d %H:%M") if sensor.last_seen else "Never"
                
                table.add_row(
                    mac,
                    sensor.name,
                    sensor.location or "Unknown",
                    status,
                    last_seen
                )
            
            self.console.print(table)
            
        except Exception as e:
            self.console.print(f"[red]Error loading sensors: {e}[/red]")
        
        self.console.print()
    
    async def _discover_sensors(self, duration: int = 10):
        """Discover Ruuvi sensors via BLE scan."""
        if not self.ble_scanner:
            self.console.print("[red]BLE scanner not initialized[/red]")
            return
        
        self.console.print(f"[blue]Scanning for Ruuvi sensors for {duration} seconds...[/blue]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("Scanning...", total=None)
            
            try:
                discovered = await self.ble_scanner.scan_once(duration)
                
                if not discovered:
                    self.console.print("[yellow]No Ruuvi sensors found[/yellow]")
                    return
                
                # Create discovery table
                table = Table(title="Discovered Sensors", show_header=True, header_style="bold green")
                table.add_column("MAC Address", style="cyan")
                table.add_column("RSSI", style="yellow")
                table.add_column("Temperature", style="red")
                table.add_column("Humidity", style="blue")
                table.add_column("Pressure", style="green")
                table.add_column("Battery", style="magenta")
                
                for mac, data in discovered.items():
                    table.add_row(
                        mac,
                        f"{data.rssi} dBm" if data.rssi else "N/A",
                        f"{data.temperature:.1f}°C" if data.temperature else "N/A",
                        f"{data.humidity:.1f}%" if data.humidity else "N/A",
                        f"{data.pressure:.1f} hPa" if data.pressure else "N/A",
                        f"{data.battery_voltage:.2f}V" if data.battery_voltage else "N/A"
                    )
                
                self.console.print(table)
                
                # Ask to add new sensors
                for mac, data in discovered.items():
                    if not self.metadata_manager.get_sensor(mac):
                        if Confirm.ask(f"Add sensor {mac} to configuration?"):
                            name = Prompt.ask(f"Enter name for sensor {mac}")
                            location = Prompt.ask("Enter location (optional)", default="")
                            
                            try:
                                self.metadata_manager.add_sensor(mac, name, location)
                                self.console.print(f"[green]Added sensor: {name} ({mac})[/green]")
                            except Exception as e:
                                self.console.print(f"[red]Error adding sensor: {e}[/red]")
                
            except Exception as e:
                self.console.print(f"[red]Scan failed: {e}[/red]")
        
        self.console.print()
    
    async def _start_monitoring(self):
        """Start real-time sensor monitoring."""
        if not all([self.ble_scanner, self.influxdb_client, self.metadata_manager]):
            self.console.print("[red]Components not initialized[/red]")
            return
        
        self.console.print("[blue]Starting sensor monitoring...[/blue]")
        
        # Connect to InfluxDB
        try:
            await self.influxdb_client.connect()
        except Exception as e:
            self.console.print(f"[red]Failed to connect to InfluxDB: {e}[/red]")
            return
        
        # Set up data callback
        def data_callback(sensor_data: RuuviSensorData):
            # Update metadata
            self.metadata_manager.update_sensor_last_seen(sensor_data.mac_address)
            
            # Write to InfluxDB
            asyncio.create_task(self.influxdb_client.write_sensor_data(sensor_data))
        
        self.ble_scanner.add_callback(data_callback)
        
        # Start continuous scanning
        await self.ble_scanner.start_continuous_scan()
        self._monitoring = True
        
        self.console.print("[green]Monitoring started. Press Ctrl+C to stop.[/green]")
        
        try:
            # Create live display
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body")
            )
            
            with Live(layout, refresh_per_second=1, console=self.console) as live:
                while self._monitoring:
                    # Update header
                    layout["header"].update(Panel(
                        f"[bold green]Monitoring Active[/bold green] - "
                        f"Buffer: {self.influxdb_client.get_buffer_size()} points",
                        border_style="green"
                    ))
                    
                    # Update body with recent data
                    recent_devices = self.ble_scanner.get_discovered_devices()
                    if recent_devices:
                        table = Table(show_header=True, header_style="bold blue")
                        table.add_column("Sensor", style="cyan")
                        table.add_column("Temperature", style="red")
                        table.add_column("Humidity", style="blue")
                        table.add_column("RSSI", style="yellow")
                        table.add_column("Last Update", style="dim")
                        
                        for mac, data in list(recent_devices.items())[-10:]:  # Show last 10
                            sensor = self.metadata_manager.get_sensor(mac)
                            name = sensor.name if sensor else mac[:8] + "..."
                            
                            table.add_row(
                                name,
                                f"{data.temperature:.1f}°C" if data.temperature else "N/A",
                                f"{data.humidity:.1f}%" if data.humidity else "N/A",
                                f"{data.rssi} dBm" if data.rssi else "N/A",
                                data.timestamp.strftime("%H:%M:%S")
                            )
                        
                        layout["body"].update(table)
                    else:
                        layout["body"].update(Panel("[yellow]No recent sensor data[/yellow]"))
                    
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            pass
        finally:
            await self._stop_monitoring()
    
    async def _stop_monitoring(self):
        """Stop sensor monitoring."""
        self._monitoring = False
        
        if self.ble_scanner:
            await self.ble_scanner.stop_continuous_scan()
        
        if self.influxdb_client:
            await self.influxdb_client.flush_all()
            await self.influxdb_client.disconnect()
        
        self.console.print("[yellow]Monitoring stopped[/yellow]")
    
    def _show_configuration(self):
        """Show current configuration."""
        if not self.config:
            self.console.print("[red]Configuration not loaded[/red]")
            return
        
        # Create configuration table
        table = Table(title="Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Setting", style="blue")
        table.add_column("Value", style="green")
        table.add_column("Description", style="dim")
        
        # Add key configuration items
        config_items = [
            ("Environment", self.config.environment, "Current environment"),
            ("Log Level", self.config.log_level, "Logging level"),
            ("BLE Adapter", self.config.ble_adapter, "Bluetooth adapter"),
            ("Scan Interval", f"{self.config.ble_scan_interval}s", "BLE scan interval"),
            ("InfluxDB Host", self.config.influxdb_host, "InfluxDB server"),
            ("InfluxDB Bucket", self.config.influxdb_bucket, "Data bucket"),
            ("Batch Size", str(self.config.influxdb_batch_size), "Write batch size"),
            ("Metadata File", self.config.metadata_file, "Sensor metadata file"),
        ]
        
        for setting, value, description in config_items:
            table.add_row(setting, str(value), description)
        
        self.console.print(table)
        self.console.print()
    
    async def _main_menu(self):
        """Display main menu and handle user input."""
        while self._running:
            self.console.clear()
            self._print_header()
            self._print_system_status()
            
            # Menu options
            menu_options = [
                "1. View Sensors",
                "2. Discover Sensors",
                "3. Start Monitoring",
                "4. Manage Service",
                "5. Show Configuration",
                "6. System Statistics",
                "7. Advanced Features",
                "8. Setup Wizard",
                "9. Exit"
            ]
            
            self.console.print("[bold yellow]Main Menu[/bold yellow]")
            for option in menu_options:
                self.console.print(f"  {option}")
            self.console.print()
            
            choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8", "9"])
            
            try:
                if choice == "1":
                    self.console.clear()
                    self._print_header()
                    self._print_sensor_list()
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "2":
                    self.console.clear()
                    self._print_header()
                    duration = int(Prompt.ask("Scan duration (seconds)", default="10"))
                    await self._discover_sensors(duration)
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "3":
                    self.console.clear()
                    self._print_header()
                    await self._start_monitoring()
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "4":
                    self.console.clear()
                    self._print_header()
                    await self._service_management_menu()
                
                elif choice == "5":
                    self.console.clear()
                    self._print_header()
                    self._show_configuration()
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "6":
                    self.console.clear()
                    self._print_header()
                    self._show_statistics()
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "7":
                    self.console.clear()
                    self._print_header()
                    await self._advanced_features_menu()
                
                elif choice == "8":
                    self.console.clear()
                    self._print_header()
                    await self._setup_wizard()
                    Prompt.ask("Press Enter to continue")
                
                elif choice == "9":
                    if Confirm.ask("Are you sure you want to exit?"):
                        self._running = False
                
            except KeyboardInterrupt:
                if Confirm.ask("\nExit application?"):
                    self._running = False
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                Prompt.ask("Press Enter to continue")
    
    def _show_statistics(self):
        """Show system statistics."""
        # Create statistics table
        table = Table(title="System Statistics", show_header=True, header_style="bold green")
        table.add_column("Component", style="cyan")
        table.add_column("Metric", style="blue")
        table.add_column("Value", style="green")
        
        # BLE Scanner statistics
        if self.ble_scanner:
            stats = self.ble_scanner.get_statistics()
            for metric, value in stats.items():
                table.add_row("BLE Scanner", metric.replace("_", " ").title(), str(value))
        
        # InfluxDB statistics
        if self.influxdb_client:
            stats = self.influxdb_client.get_statistics()
            for metric, value in stats.items():
                if metric not in ["last_write_time", "last_health_check"]:
                    table.add_row("InfluxDB", metric.replace("_", " ").title(), str(value))
        
        # Performance statistics
        if self.performance_monitor:
            metrics = self.performance_monitor.get_metrics()
            for metric, value in metrics.items():
                table.add_row("Performance", metric.replace("_", " ").title(), str(value))
        
        self.console.print(table)
        self.console.print()
    
    async def _advanced_features_menu(self):
        """Display and handle advanced features submenu."""
        while True:
            self.console.print("\n[bold cyan]Advanced Features[/bold cyan]")
            self.console.print("1. Data Export/Import")
            self.console.print("2. Sensor Testing & Calibration")
            self.console.print("3. Batch Operations")
            self.console.print("4. Real-time Dashboard")
            self.console.print("5. Back to Main Menu")
            
            choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5"])
            
            try:
                if choice == "1":
                    await self._data_export_import_menu()
                elif choice == "2":
                    await self._sensor_testing_menu()
                elif choice == "3":
                    await self._batch_operations_menu()
                elif choice == "4":
                    await self.advanced_features.real_time_dashboard()
                elif choice == "5":
                    break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                self.logger.error(f"Advanced features error: {e}")
                Prompt.ask("Press Enter to continue")
    
    async def _data_export_import_menu(self):
        """Handle data export/import operations."""
        self.console.print("\n[bold cyan]Data Export/Import[/bold cyan]")
        self.console.print("1. Export Data")
        self.console.print("2. Import Data")
        self.console.print("3. Back")
        
        choice = Prompt.ask("Select option", choices=["1", "2", "3"])
        
        if choice == "1":
            # Export data
            format_choice = Prompt.ask(
                "Export format",
                choices=["json", "csv", "influxdb"],
                default="json"
            )
            
            if format_choice == "influxdb":
                host = Prompt.ask("InfluxDB host", default="localhost")
                port = int(Prompt.ask("InfluxDB port", default="8086"))
                database = Prompt.ask("Database name", default="ruuvi_export")
                await self.advanced_features.export_data(format_choice, host=host, port=port, database=database)
            else:
                filename = Prompt.ask(f"Output filename", default=f"ruuvi_export.{format_choice}")
                await self.advanced_features.export_data(format_choice, filename=filename)
        
        elif choice == "2":
            # Import data
            filename = Prompt.ask("Import filename")
            if filename and Path(filename).exists():
                await self.advanced_features.import_data(filename)
            else:
                self.console.print("[red]File not found[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _sensor_testing_menu(self):
        """Handle sensor testing and calibration."""
        self.console.print("\n[bold cyan]Sensor Testing & Calibration[/bold cyan]")
        self.console.print("1. Signal Strength Test")
        self.console.print("2. Data Consistency Test")
        self.console.print("3. Range Validation Test")
        self.console.print("4. Battery Health Test")
        self.console.print("5. Response Time Test")
        self.console.print("6. Run All Tests")
        self.console.print("7. Back")
        
        choice = Prompt.ask("Select test", choices=["1", "2", "3", "4", "5", "6", "7"])
        
        if choice == "7":
            return
        
        # Get sensor MAC address
        mac_address = Prompt.ask("Sensor MAC address (or 'all' for all sensors)")
        
        test_map = {
            "1": "signal_strength",
            "2": "data_consistency",
            "3": "range_validation",
            "4": "battery_health",
            "5": "response_time",
            "6": "all"
        }
        
        test_type = test_map[choice]
        await self.advanced_features.sensor_calibration_test(mac_address, test_type)
        Prompt.ask("Press Enter to continue")
    
    async def _batch_operations_menu(self):
        """Handle batch operations."""
        self.console.print("\n[bold cyan]Batch Operations[/bold cyan]")
        self.console.print("1. Update Multiple Sensors")
        self.console.print("2. Export Multiple Sensors")
        self.console.print("3. Test Multiple Sensors")
        self.console.print("4. Back")
        
        choice = Prompt.ask("Select operation", choices=["1", "2", "3", "4"])
        
        if choice == "4":
            return
        
        # Get sensor list
        sensor_input = Prompt.ask("Sensor MAC addresses (comma-separated, or 'all')")
        if sensor_input.lower() == 'all':
            sensors = ['all']
        else:
            sensors = [s.strip() for s in sensor_input.split(',')]
        
        operation_map = {
            "1": "update",
            "2": "export",
            "3": "test"
        }
        
        operation = operation_map[choice]
        await self.advanced_features.batch_operations(sensors, operation)
        Prompt.ask("Press Enter to continue")
    
    async def _setup_wizard(self):
        """Run the interactive setup wizard."""
        await self.advanced_features.interactive_setup_wizard()
    
    async def _service_management_menu(self):
        """Service management submenu."""
        if not self.service_manager:
            self.console.print("[red]Service manager not initialized[/red]")
            Prompt.ask("Press Enter to continue")
            return
        
        while True:
            self.console.clear()
            self._print_header()
            
            # Show current service status
            try:
                service_info = self.service_manager.get_status()
                self._print_service_status(service_info)
            except Exception as e:
                self.console.print(f"[red]Error getting service status: {e}[/red]")
            
            # Service management menu
            service_options = [
                "1. Install Service",
                "2. Uninstall Service",
                "3. Start Service",
                "4. Stop Service",
                "5. Restart Service",
                "6. Enable Auto-start",
                "7. Disable Auto-start",
                "8. View Service Logs",
                "9. Service Health Check",
                "10. Back to Main Menu"
            ]
            
            self.console.print("[bold yellow]Service Management[/bold yellow]")
            for option in service_options:
                self.console.print(f"  {option}")
            self.console.print()
            
            choice = Prompt.ask("Select option", choices=[str(i) for i in range(1, 11)])
            
            try:
                if choice == "1":
                    await self._install_service()
                elif choice == "2":
                    await self._uninstall_service()
                elif choice == "3":
                    await self._start_service()
                elif choice == "4":
                    await self._stop_service()
                elif choice == "5":
                    await self._restart_service()
                elif choice == "6":
                    await self._enable_service()
                elif choice == "7":
                    await self._disable_service()
                elif choice == "8":
                    await self._view_service_logs()
                elif choice == "9":
                    await self._service_health_check()
                elif choice == "10":
                    break
                    
            except KeyboardInterrupt:
                if Confirm.ask("\nReturn to main menu?"):
                    break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")
                Prompt.ask("Press Enter to continue")
    
    def _print_service_status(self, service_info):
        """Print service status information."""
        # Create service status table
        table = Table(title="Service Status", show_header=True, header_style="bold cyan")
        table.add_column("Property", style="blue")
        table.add_column("Value", style="green")
        
        # Status with color coding
        status_color = {
            ServiceStatus.ACTIVE: "green",
            ServiceStatus.INACTIVE: "yellow",
            ServiceStatus.FAILED: "red",
            ServiceStatus.NOT_INSTALLED: "dim",
            ServiceStatus.UNKNOWN: "dim"
        }
        
        status_text = f"[{status_color.get(service_info.status, 'dim')}]{service_info.status.value}[/{status_color.get(service_info.status, 'dim')}]"
        
        table.add_row("Service Name", service_info.name)
        table.add_row("Status", status_text)
        table.add_row("Auto-start", "✓ Enabled" if service_info.enabled else "✗ Disabled")
        
        if service_info.pid:
            table.add_row("Process ID", str(service_info.pid))
        
        if service_info.uptime:
            table.add_row("Uptime", service_info.uptime)
            
        if service_info.memory_usage:
            table.add_row("Memory Usage", service_info.memory_usage)
            
        if service_info.cpu_usage is not None:
            table.add_row("CPU Usage", f"{service_info.cpu_usage:.1f}%")
        
        self.console.print(table)
        self.console.print()
    
    async def _install_service(self):
        """Install systemd service."""
        try:
            if self.service_manager.is_installed():
                if not Confirm.ask("Service is already installed. Reinstall?"):
                    return
            
            enable_autostart = Confirm.ask("Enable automatic startup?", default=True)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Installing service...", total=None)
                
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.install, enable_autostart
                )
                
                if success:
                    self.console.print("[green]✓ Service installed successfully[/green]")
                    if enable_autostart:
                        self.console.print("[green]✓ Auto-start enabled[/green]")
                else:
                    self.console.print("[red]✗ Service installation failed[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]Installation error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _uninstall_service(self):
        """Uninstall systemd service."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[yellow]Service is not installed[/yellow]")
                Prompt.ask("Press Enter to continue")
                return
            
            if not Confirm.ask("Are you sure you want to uninstall the service?"):
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Uninstalling service...", total=None)
                
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.uninstall
                )
                
                if success:
                    self.console.print("[green]✓ Service uninstalled successfully[/green]")
                else:
                    self.console.print("[red]✗ Service uninstallation failed[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]Uninstallation error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _start_service(self):
        """Start the service."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed. Install it first.[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Starting service...", total=None)
                
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.start
                )
                
                if success:
                    self.console.print("[green]✓ Service started successfully[/green]")
                else:
                    self.console.print("[red]✗ Service start failed[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]Start error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _stop_service(self):
        """Stop the service."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Stopping service...", total=None)
                
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.stop
                )
                
                if success:
                    self.console.print("[green]✓ Service stopped successfully[/green]")
                else:
                    self.console.print("[red]✗ Service stop failed[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]Stop error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _restart_service(self):
        """Restart the service."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Restarting service...", total=None)
                
                success = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.restart
                )
                
                if success:
                    self.console.print("[green]✓ Service restarted successfully[/green]")
                else:
                    self.console.print("[red]✗ Service restart failed[/red]")
                    
        except Exception as e:
            self.console.print(f"[red]Restart error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _enable_service(self):
        """Enable service auto-start."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            success = await asyncio.get_event_loop().run_in_executor(
                None, self.service_manager.enable
            )
            
            if success:
                self.console.print("[green]✓ Service auto-start enabled[/green]")
            else:
                self.console.print("[red]✗ Failed to enable auto-start[/red]")
                
        except Exception as e:
            self.console.print(f"[red]Enable error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _disable_service(self):
        """Disable service auto-start."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            success = await asyncio.get_event_loop().run_in_executor(
                None, self.service_manager.disable
            )
            
            if success:
                self.console.print("[green]✓ Service auto-start disabled[/green]")
            else:
                self.console.print("[red]✗ Failed to disable auto-start[/red]")
                
        except Exception as e:
            self.console.print(f"[red]Disable error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _view_service_logs(self):
        """View service logs."""
        try:
            if not self.service_manager.is_installed():
                self.console.print("[red]Service is not installed[/red]")
                Prompt.ask("Press Enter to continue")
                return
            
            lines = int(Prompt.ask("Number of log lines to show", default="50"))
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Retrieving logs...", total=None)
                
                logs = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.get_logs, lines
                )
            
            if logs.strip():
                self.console.print(Panel(
                    logs,
                    title="Service Logs",
                    border_style="blue"
                ))
            else:
                self.console.print("[yellow]No logs available[/yellow]")
                
        except Exception as e:
            self.console.print(f"[red]Log retrieval error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def _service_health_check(self):
        """Perform service health check."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Performing health check...", total=None)
                
                health = await asyncio.get_event_loop().run_in_executor(
                    None, self.service_manager.health_check
                )
            
            # Create health check table
            table = Table(title="Service Health Check", show_header=True, header_style="bold green")
            table.add_column("Check", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details", style="dim")
            
            # Overall health
            overall_status = "✓ Healthy" if health["healthy"] else "✗ Unhealthy"
            status_color = "green" if health["healthy"] else "red"
            
            table.add_row("Overall Health", f"[{status_color}]{overall_status}[/{status_color}]", "")
            table.add_row("Service Installed", "✓ Yes" if health["service_installed"] else "✗ No", "")
            table.add_row("Auto-start Enabled", "✓ Yes" if health["service_enabled"] else "✗ No", "")
            
            if health["status"]:
                table.add_row("Service Status", health["status"], "")
            
            self.console.print(table)
            
            # Show issues and recommendations
            if health["issues"]:
                self.console.print("\n[bold red]Issues Found:[/bold red]")
                for issue in health["issues"]:
                    self.console.print(f"  • {issue}")
            
            if health["recommendations"]:
                self.console.print("\n[bold yellow]Recommendations:[/bold yellow]")
                for rec in health["recommendations"]:
                    self.console.print(f"  • {rec}")
                    
        except Exception as e:
            self.console.print(f"[red]Health check error: {e}[/red]")
        
        Prompt.ask("Press Enter to continue")
    
    async def run(self):
        """Run the CLI application."""
        try:
            self._initialize_components()
            self._running = True
            await self._main_menu()
            
        except CLIError:
            sys.exit(1)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Application interrupted[/yellow]")
        except Exception as e:
            self.console.print(f"[red]Unexpected error: {e}[/red]")
            sys.exit(1)
        finally:
            # Cleanup
            if self._monitoring:
                await self._stop_monitoring()
            
            if self.ble_scanner:
                await self.ble_scanner.cleanup()
            
            self.console.print("[blue]Goodbye![/blue]")


# Click commands for CLI entry points
@click.group()
@click.version_option(version="1.0.0", prog_name="ruuvi-service")
def cli():
    """Ruuvi Sensor Service - BLE sensor monitoring and data collection."""
    pass


@cli.command()
def menu():
    """Launch interactive menu."""
    app = RuuviCLI()
    asyncio.run(app.run())


@cli.command()
@click.option("--duration", "-d", default=10, help="Scan duration in seconds")
def discover(duration):
    """Discover Ruuvi sensors."""
    async def run_discovery():
        app = RuuviCLI()
        app._initialize_components()
        await app._discover_sensors(duration)
    
    asyncio.run(run_discovery())


@cli.command()
def monitor():
    """Start sensor monitoring."""
    async def run_monitoring():
        app = RuuviCLI()
        app._initialize_components()
        await app._start_monitoring()
    
    asyncio.run(run_monitoring())


@cli.command()
def status():
    """Show system status."""
    app = RuuviCLI()
    app._initialize_components()
    app._print_system_status()


if __name__ == "__main__":
    cli()