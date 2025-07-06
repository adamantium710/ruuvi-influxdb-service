"""
Service Manager for Ruuvi Sensor Service.
Handles systemd service integration, installation, and management.
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from ..utils.config import Config
from ..utils.logging import ProductionLogger


class ServiceStatus(Enum):
    """Service status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    UNKNOWN = "unknown"
    NOT_INSTALLED = "not_installed"


@dataclass
class ServiceInfo:
    """Service information container."""
    name: str
    status: ServiceStatus
    enabled: bool
    pid: Optional[int] = None
    uptime: Optional[str] = None
    memory_usage: Optional[str] = None
    cpu_usage: Optional[float] = None
    restart_count: int = 0
    last_restart: Optional[str] = None


class ServiceManagerError(Exception):
    """Base exception for service manager operations."""
    pass


class ServiceManager:
    """
    Manages systemd service integration for Ruuvi Sensor Service.
    
    Features:
    - Service installation and configuration
    - Start/stop/restart operations
    - Status monitoring and health checks
    - Auto-restart configuration
    - Log management integration
    """
    
    SERVICE_NAME = "ruuvi-sensor"
    SERVICE_FILE = f"{SERVICE_NAME}.service"
    
    def __init__(self, config: Config, logger: ProductionLogger):
        """Initialize service manager."""
        self.config = config
        self.logger = logger
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent
        self.service_file_path = Path("/etc/systemd/system") / self.SERVICE_FILE
        self.user_service_path = Path.home() / ".config/systemd/user" / self.SERVICE_FILE
        
        # Service configuration
        self.use_user_service = not self._has_sudo_privileges()
        self.service_path = self.user_service_path if self.use_user_service else self.service_file_path
        
        self.logger.info(f"Service manager initialized (user_service: {self.use_user_service})")
    
    def _has_sudo_privileges(self) -> bool:
        """Check if current user has sudo privileges."""
        try:
            result = subprocess.run(
                ["sudo", "-n", "true"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _run_systemctl(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run systemctl command with appropriate privileges."""
        cmd = ["systemctl"]
        
        if self.use_user_service:
            cmd.append("--user")
        else:
            cmd = ["sudo"] + cmd
        
        cmd.extend(command)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=check
            )
            return result
        except subprocess.CalledProcessError as e:
            self.logger.error(f"systemctl command failed: {' '.join(cmd)}")
            self.logger.error(f"stdout: {e.stdout}")
            self.logger.error(f"stderr: {e.stderr}")
            raise ServiceManagerError(f"systemctl command failed: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise ServiceManagerError("systemctl command timed out")
    
    def _get_service_template(self) -> str:
        """Generate systemd service file template."""
        python_path = sys.executable
        project_path = self.project_root.absolute()
        main_script = project_path / "main.py"
        
        # Environment variables
        env_vars = []
        if (project_path / ".env").exists():
            env_vars.append(f"EnvironmentFile={project_path}/.env")
        
        # User and group settings
        user_settings = ""
        if not self.use_user_service:
            current_user = os.getenv("USER", "ruuvi")
            user_settings = f"""User={current_user}
Group={current_user}"""
        
        template = f"""[Unit]
Description=Ruuvi Sensor Service - BLE sensor monitoring and data collection
Documentation=https://github.com/your-org/ruuvi-sensor-service
After=network.target bluetooth.service
Wants=network.target
Requires=bluetooth.service

[Service]
Type=exec
ExecStart={python_path} {main_script} daemon
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

# Working directory
WorkingDirectory={project_path}

# Environment
Environment=PYTHONPATH={project_path}/src
{chr(10).join(env_vars)}

# Security settings
{user_settings}
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={project_path}/data {project_path}/logs {project_path}/backups
PrivateTmp=true

# Resource limits
MemoryMax=512M
CPUQuota=50%

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier={self.SERVICE_NAME}

[Install]
WantedBy={'default.target' if self.use_user_service else 'multi-user.target'}
"""
        return template
    
    def is_installed(self) -> bool:
        """Check if service is installed."""
        return self.service_path.exists()
    
    def install(self, enable_autostart: bool = True) -> bool:
        """
        Install systemd service.
        
        Args:
            enable_autostart: Enable service to start automatically
            
        Returns:
            True if installation successful
        """
        try:
            self.logger.info("Installing systemd service...")
            
            # Create service directory if needed
            self.service_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate and write service file
            service_content = self._get_service_template()
            self.service_path.write_text(service_content)
            
            self.logger.info(f"Service file written to: {self.service_path}")
            
            # Reload systemd
            self._run_systemctl(["daemon-reload"])
            
            # Enable service if requested
            if enable_autostart:
                self.enable()
            
            self.logger.info("Service installed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service installation failed: {e}")
            raise ServiceManagerError(f"Installation failed: {e}")
    
    def uninstall(self) -> bool:
        """
        Uninstall systemd service.
        
        Returns:
            True if uninstallation successful
        """
        try:
            self.logger.info("Uninstalling systemd service...")
            
            # Stop service if running
            if self.get_status().status in [ServiceStatus.ACTIVE]:
                self.stop()
            
            # Disable service
            if self.is_enabled():
                self.disable()
            
            # Remove service file
            if self.service_path.exists():
                self.service_path.unlink()
                self.logger.info(f"Service file removed: {self.service_path}")
            
            # Reload systemd
            self._run_systemctl(["daemon-reload"])
            
            self.logger.info("Service uninstalled successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Service uninstallation failed: {e}")
            raise ServiceManagerError(f"Uninstallation failed: {e}")
    
    def start(self) -> bool:
        """Start the service."""
        try:
            self.logger.info("Starting service...")
            self._run_systemctl(["start", self.SERVICE_NAME])
            
            # Wait for service to start
            time.sleep(2)
            status = self.get_status()
            
            if status.status == ServiceStatus.ACTIVE:
                self.logger.info("Service started successfully")
                return True
            else:
                raise ServiceManagerError(f"Service failed to start: {status.status}")
                
        except Exception as e:
            self.logger.error(f"Failed to start service: {e}")
            raise ServiceManagerError(f"Start failed: {e}")
    
    def stop(self) -> bool:
        """Stop the service."""
        try:
            self.logger.info("Stopping service...")
            self._run_systemctl(["stop", self.SERVICE_NAME])
            
            # Wait for service to stop
            time.sleep(2)
            status = self.get_status()
            
            if status.status == ServiceStatus.INACTIVE:
                self.logger.info("Service stopped successfully")
                return True
            else:
                self.logger.warning(f"Service may not have stopped cleanly: {status.status}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to stop service: {e}")
            raise ServiceManagerError(f"Stop failed: {e}")
    
    def restart(self) -> bool:
        """Restart the service."""
        try:
            self.logger.info("Restarting service...")
            self._run_systemctl(["restart", self.SERVICE_NAME])
            
            # Wait for service to restart
            time.sleep(3)
            status = self.get_status()
            
            if status.status == ServiceStatus.ACTIVE:
                self.logger.info("Service restarted successfully")
                return True
            else:
                raise ServiceManagerError(f"Service failed to restart: {status.status}")
                
        except Exception as e:
            self.logger.error(f"Failed to restart service: {e}")
            raise ServiceManagerError(f"Restart failed: {e}")
    
    def reload(self) -> bool:
        """Reload service configuration."""
        try:
            self.logger.info("Reloading service configuration...")
            self._run_systemctl(["reload", self.SERVICE_NAME])
            self.logger.info("Service configuration reloaded")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to reload service: {e}")
            raise ServiceManagerError(f"Reload failed: {e}")
    
    def enable(self) -> bool:
        """Enable service to start automatically."""
        try:
            self.logger.info("Enabling service autostart...")
            self._run_systemctl(["enable", self.SERVICE_NAME])
            self.logger.info("Service autostart enabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to enable service: {e}")
            raise ServiceManagerError(f"Enable failed: {e}")
    
    def disable(self) -> bool:
        """Disable service autostart."""
        try:
            self.logger.info("Disabling service autostart...")
            self._run_systemctl(["disable", self.SERVICE_NAME])
            self.logger.info("Service autostart disabled")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to disable service: {e}")
            raise ServiceManagerError(f"Disable failed: {e}")
    
    def is_enabled(self) -> bool:
        """Check if service is enabled for autostart."""
        try:
            result = self._run_systemctl(["is-enabled", self.SERVICE_NAME], check=False)
            return result.returncode == 0 and "enabled" in result.stdout
        except Exception:
            return False
    
    def get_status(self) -> ServiceInfo:
        """Get detailed service status information."""
        if not self.is_installed():
            return ServiceInfo(
                name=self.SERVICE_NAME,
                status=ServiceStatus.NOT_INSTALLED,
                enabled=False
            )
        
        try:
            # Get basic status
            result = self._run_systemctl(["status", self.SERVICE_NAME], check=False)
            
            # Parse status
            status = ServiceStatus.UNKNOWN
            pid = None
            uptime = None
            
            if result.returncode == 0:
                if "Active: active (running)" in result.stdout:
                    status = ServiceStatus.ACTIVE
                elif "Active: inactive" in result.stdout:
                    status = ServiceStatus.INACTIVE
                elif "Active: failed" in result.stdout:
                    status = ServiceStatus.FAILED
            
            # Extract PID if running
            if status == ServiceStatus.ACTIVE:
                for line in result.stdout.split('\n'):
                    if "Main PID:" in line:
                        try:
                            pid = int(line.split("Main PID:")[1].split()[0])
                        except (IndexError, ValueError):
                            pass
                    elif "Active:" in line and "since" in line:
                        try:
                            uptime = line.split("since")[1].strip()
                        except IndexError:
                            pass
            
            # Get memory and CPU usage if running
            memory_usage = None
            cpu_usage = None
            
            if pid:
                try:
                    # Get memory usage
                    mem_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "rss="],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if mem_result.returncode == 0:
                        memory_kb = int(mem_result.stdout.strip())
                        memory_usage = f"{memory_kb / 1024:.1f} MB"
                    
                    # Get CPU usage
                    cpu_result = subprocess.run(
                        ["ps", "-p", str(pid), "-o", "pcpu="],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if cpu_result.returncode == 0:
                        cpu_usage = float(cpu_result.stdout.strip())
                        
                except (subprocess.TimeoutExpired, ValueError, subprocess.CalledProcessError):
                    pass
            
            return ServiceInfo(
                name=self.SERVICE_NAME,
                status=status,
                enabled=self.is_enabled(),
                pid=pid,
                uptime=uptime,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get service status: {e}")
            return ServiceInfo(
                name=self.SERVICE_NAME,
                status=ServiceStatus.UNKNOWN,
                enabled=False
            )
    
    def get_logs(self, lines: int = 50, follow: bool = False) -> str:
        """
        Get service logs.
        
        Args:
            lines: Number of log lines to retrieve
            follow: Whether to follow logs (for streaming)
            
        Returns:
            Log content as string
        """
        try:
            cmd = ["journalctl"]
            
            if self.use_user_service:
                cmd.append("--user")
            
            cmd.extend([
                "-u", self.SERVICE_NAME,
                "-n", str(lines),
                "--no-pager"
            ])
            
            if follow:
                cmd.append("-f")
            
            if not self.use_user_service:
                cmd = ["sudo"] + cmd
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30 if not follow else None
            )
            
            return result.stdout
            
        except Exception as e:
            self.logger.error(f"Failed to get service logs: {e}")
            return f"Error retrieving logs: {e}"
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive service health check.
        
        Returns:
            Health check results
        """
        health = {
            "timestamp": time.time(),
            "service_installed": self.is_installed(),
            "service_enabled": self.is_enabled(),
            "status": None,
            "issues": [],
            "recommendations": []
        }
        
        try:
            # Get service status
            status = self.get_status()
            health["status"] = status.status.value
            
            # Check for issues
            if not health["service_installed"]:
                health["issues"].append("Service not installed")
                health["recommendations"].append("Run service installation")
            
            if status.status == ServiceStatus.FAILED:
                health["issues"].append("Service is in failed state")
                health["recommendations"].append("Check service logs and restart")
            
            if status.status == ServiceStatus.INACTIVE and health["service_enabled"]:
                health["issues"].append("Service is enabled but not running")
                health["recommendations"].append("Start the service")
            
            # Check resource usage
            if status.cpu_usage and status.cpu_usage > 80:
                health["issues"].append(f"High CPU usage: {status.cpu_usage}%")
                health["recommendations"].append("Monitor system resources")
            
            # Check if service is responsive (if running)
            if status.status == ServiceStatus.ACTIVE:
                # Could add more sophisticated health checks here
                # like checking if the service is actually scanning for sensors
                pass
            
            health["healthy"] = len(health["issues"]) == 0
            
        except Exception as e:
            health["issues"].append(f"Health check failed: {e}")
            health["healthy"] = False
        
        return health
    
    def setup_log_rotation(self) -> bool:
        """Set up log rotation for service logs."""
        try:
            # systemd journal handles log rotation automatically
            # but we can configure retention policies
            
            if not self.use_user_service:
                # System-wide journal configuration
                journal_conf = Path("/etc/systemd/journald.conf.d")
                journal_conf.mkdir(exist_ok=True)
                
                ruuvi_conf = journal_conf / "ruuvi-sensor.conf"
                ruuvi_conf.write_text(f"""[Journal]
# Ruuvi Sensor Service log retention
SystemMaxUse=100M
SystemMaxFileSize=10M
SystemMaxFiles=10
MaxRetentionSec=7day
""")
                
                # Restart journald to apply changes
                subprocess.run(["sudo", "systemctl", "restart", "systemd-journald"], check=True)
            
            self.logger.info("Log rotation configured")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup log rotation: {e}")
            return False