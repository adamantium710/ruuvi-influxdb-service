"""
Edge case handling and error recovery for Ruuvi Sensor Service.

This module provides comprehensive error handling for various edge cases
that can occur during operation, including hardware failures, network issues,
file corruption, and resource exhaustion scenarios.
"""

import os
import sys
import json
import shutil
import psutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from ..utils.config import Config
from ..utils.logging import ProductionLogger


class EdgeCaseHandler:
    """
    Comprehensive edge case handler for the Ruuvi Sensor Service.
    
    Handles various failure scenarios and provides recovery mechanisms:
    - BLE adapter errors and hardware compatibility issues
    - Corrupt/missing configuration files
    - Network connectivity problems
    - Resource exhaustion (memory, disk space)
    - Permission issues
    - Concurrent file access problems
    """
    
    def __init__(self, config: Config, logger: ProductionLogger):
        """Initialize edge case handler."""
        self.config = config
        self.logger = logger
        self.recovery_attempts = {}
        self.max_recovery_attempts = 3
        self.recovery_cooldown = timedelta(minutes=5)
        
    def handle_ble_adapter_error(self, error: Exception) -> Tuple[bool, str]:
        """
        Handle BLE adapter errors with comprehensive recovery strategies.
        
        Args:
            error: The BLE-related exception
            
        Returns:
            Tuple of (success, message) indicating recovery status
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        self.logger.warning(f"BLE adapter error detected: {error_type} - {error_msg}")
        
        # Check if we've exceeded recovery attempts
        if not self._can_attempt_recovery("ble_adapter"):
            return False, "Maximum BLE recovery attempts exceeded"
        
        # Increment recovery attempt counter
        self._record_recovery_attempt("ble_adapter")
        
        # Common BLE error patterns and solutions
        recovery_strategies = [
            self._check_bluetooth_service,
            self._check_bluetooth_permissions,
            self._check_bluetooth_hardware,
            self._reset_bluetooth_adapter,
            self._suggest_system_solutions
        ]
        
        for strategy in recovery_strategies:
            try:
                success, message = strategy(error_msg)
                if success:
                    self.logger.info(f"BLE recovery successful: {message}")
                    return True, message
                else:
                    self.logger.debug(f"BLE recovery strategy failed: {message}")
            except Exception as e:
                self.logger.error(f"BLE recovery strategy error: {e}")
        
        # If all strategies failed, provide comprehensive guidance
        guidance = self._generate_ble_troubleshooting_guide(error_msg)
        return False, guidance
    
    def handle_file_corruption(self, file_path: str, error: Exception) -> Tuple[bool, str]:
        """
        Handle corrupt or missing configuration files with backup recovery.
        
        Args:
            file_path: Path to the corrupted file
            error: The file-related exception
            
        Returns:
            Tuple of (success, message) indicating recovery status
        """
        self.logger.error(f"File corruption detected: {file_path} - {error}")
        
        file_path_obj = Path(file_path)
        backup_dir = file_path_obj.parent / "backups"
        
        # Try to recover from backup
        if self._restore_from_backup(file_path_obj, backup_dir):
            return True, f"Successfully restored {file_path} from backup"
        
        # Try to create minimal valid file
        if self._create_minimal_file(file_path_obj):
            return True, f"Created minimal valid {file_path}"
        
        return False, f"Unable to recover {file_path}. Manual intervention required."
    
    def handle_network_connectivity(self, host: str, port: int, error: Exception) -> Tuple[bool, str]:
        """
        Handle network connectivity issues with retry and fallback strategies.
        
        Args:
            host: Target host
            port: Target port
            error: Network-related exception
            
        Returns:
            Tuple of (success, message) indicating connectivity status
        """
        self.logger.warning(f"Network connectivity issue: {host}:{port} - {error}")
        
        # Check basic network connectivity
        if not self._check_network_interface():
            return False, "Network interface is down"
        
        # Check DNS resolution
        if not self._check_dns_resolution(host):
            return False, f"DNS resolution failed for {host}"
        
        # Check port connectivity
        if not self._check_port_connectivity(host, port):
            return False, f"Port {port} is not accessible on {host}"
        
        # Check firewall rules
        firewall_issues = self._check_firewall_rules(host, port)
        if firewall_issues:
            return False, f"Firewall may be blocking connection: {firewall_issues}"
        
        return True, "Network connectivity appears normal"
    
    def handle_resource_exhaustion(self) -> Tuple[bool, str]:
        """
        Handle resource exhaustion scenarios (memory, disk space).
        
        Returns:
            Tuple of (success, message) indicating resource status
        """
        issues = []
        
        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            issues.append(f"High memory usage: {memory.percent:.1f}%")
            
        # Check disk space
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        if disk_percent > 90:
            issues.append(f"Low disk space: {disk_percent:.1f}% used")
            
        # Check available file descriptors
        try:
            process = psutil.Process()
            fd_count = process.num_fds()
            if fd_count > 900:  # Typical limit is 1024
                issues.append(f"High file descriptor usage: {fd_count}")
        except Exception:
            pass
        
        if issues:
            # Attempt cleanup
            cleanup_success = self._perform_resource_cleanup()
            if cleanup_success:
                return True, f"Resource issues detected and cleaned up: {'; '.join(issues)}"
            else:
                return False, f"Resource exhaustion detected: {'; '.join(issues)}"
        
        return True, "Resource usage is normal"
    
    def handle_permission_error(self, path: str, error: Exception) -> Tuple[bool, str]:
        """
        Handle permission-related errors with guidance.
        
        Args:
            path: Path that caused permission error
            error: Permission-related exception
            
        Returns:
            Tuple of (success, message) with guidance
        """
        self.logger.error(f"Permission error: {path} - {error}")
        
        path_obj = Path(path)
        
        # Check if path exists
        if not path_obj.exists():
            return False, f"Path does not exist: {path}"
        
        # Check current permissions
        stat_info = path_obj.stat()
        current_perms = oct(stat_info.st_mode)[-3:]
        
        # Generate permission guidance
        guidance = [
            f"Permission denied for: {path}",
            f"Current permissions: {current_perms}",
            f"Owner: {stat_info.st_uid}",
            f"Group: {stat_info.st_gid}",
            "",
            "Suggested fixes:",
        ]
        
        # Specific guidance based on path type
        if "bluetooth" in path.lower() or "hci" in path.lower():
            guidance.extend([
                f"• Add user to bluetooth group: sudo usermod -a -G bluetooth $USER",
                f"• Restart session or run: newgrp bluetooth",
                f"• Check bluetooth service: sudo systemctl status bluetooth"
            ])
        elif path_obj.is_dir():
            guidance.extend([
                f"• Fix directory permissions: sudo chmod 755 {path}",
                f"• Fix ownership: sudo chown $USER:$USER {path}"
            ])
        else:
            guidance.extend([
                f"• Fix file permissions: sudo chmod 644 {path}",
                f"• Fix ownership: sudo chown $USER:$USER {path}"
            ])
        
        return False, "\n".join(guidance)
    
    def handle_concurrent_access(self, file_path: str, error: Exception) -> Tuple[bool, str]:
        """
        Handle concurrent file access issues.
        
        Args:
            file_path: Path to file with concurrent access issue
            error: Concurrent access exception
            
        Returns:
            Tuple of (success, message) indicating resolution status
        """
        self.logger.warning(f"Concurrent access issue: {file_path} - {error}")
        
        # Check for lock files
        lock_file = Path(f"{file_path}.lock")
        if lock_file.exists():
            # Check if lock is stale
            try:
                lock_age = datetime.now() - datetime.fromtimestamp(lock_file.stat().st_mtime)
                if lock_age > timedelta(minutes=5):
                    lock_file.unlink()
                    return True, "Removed stale lock file"
                else:
                    return False, f"File is locked by another process (age: {lock_age})"
            except Exception:
                # Remove problematic lock file
                try:
                    lock_file.unlink()
                    return True, "Removed problematic lock file"
                except Exception:
                    return False, "Unable to remove lock file"
        
        # Check for processes using the file
        try:
            for proc in psutil.process_iter(['pid', 'name', 'open_files']):
                try:
                    if proc.info['open_files']:
                        for file_info in proc.info['open_files']:
                            if file_info.path == file_path:
                                return False, f"File in use by process: {proc.info['name']} (PID: {proc.info['pid']})"
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return True, "No concurrent access issues detected"
    
    def _can_attempt_recovery(self, recovery_type: str) -> bool:
        """Check if we can attempt recovery for a given type."""
        if recovery_type not in self.recovery_attempts:
            return True
        
        attempts, last_attempt = self.recovery_attempts[recovery_type]
        
        # Check if we've exceeded max attempts
        if attempts >= self.max_recovery_attempts:
            # Check if cooldown period has passed
            if datetime.now() - last_attempt > self.recovery_cooldown:
                # Reset attempts after cooldown
                self.recovery_attempts[recovery_type] = (0, datetime.now())
                return True
            return False
        
        return True
    
    def _record_recovery_attempt(self, recovery_type: str):
        """Record a recovery attempt."""
        if recovery_type in self.recovery_attempts:
            attempts, _ = self.recovery_attempts[recovery_type]
            self.recovery_attempts[recovery_type] = (attempts + 1, datetime.now())
        else:
            self.recovery_attempts[recovery_type] = (1, datetime.now())
    
    def _check_bluetooth_service(self, error_msg: str) -> Tuple[bool, str]:
        """Check if bluetooth service is running."""
        try:
            import subprocess
            result = subprocess.run(['systemctl', 'is-active', 'bluetooth'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                return False, "Bluetooth service is not active. Run: sudo systemctl start bluetooth"
            return True, "Bluetooth service is active"
        except Exception as e:
            return False, f"Unable to check bluetooth service: {e}"
    
    def _check_bluetooth_permissions(self, error_msg: str) -> Tuple[bool, str]:
        """Check bluetooth permissions."""
        try:
            import grp
            bluetooth_group = grp.getgrnam('bluetooth')
            current_user = os.getenv('USER')
            
            if current_user not in [member for member in bluetooth_group.gr_mem]:
                return False, f"User {current_user} not in bluetooth group. Run: sudo usermod -a -G bluetooth {current_user}"
            
            return True, "Bluetooth permissions are correct"
        except KeyError:
            return False, "Bluetooth group does not exist"
        except Exception as e:
            return False, f"Unable to check bluetooth permissions: {e}"
    
    def _check_bluetooth_hardware(self, error_msg: str) -> Tuple[bool, str]:
        """Check bluetooth hardware availability."""
        try:
            import subprocess
            result = subprocess.run(['hciconfig'], capture_output=True, text=True)
            if result.returncode != 0 or 'hci' not in result.stdout:
                return False, "No bluetooth adapter found. Check hardware connection."
            
            if 'DOWN' in result.stdout:
                return False, "Bluetooth adapter is down. Run: sudo hciconfig hci0 up"
            
            return True, "Bluetooth hardware is available and up"
        except Exception as e:
            return False, f"Unable to check bluetooth hardware: {e}"
    
    def _reset_bluetooth_adapter(self, error_msg: str) -> Tuple[bool, str]:
        """Attempt to reset bluetooth adapter."""
        try:
            import subprocess
            
            # Reset bluetooth adapter
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'down'], check=False)
            subprocess.run(['sudo', 'hciconfig', 'hci0', 'up'], check=False)
            
            # Restart bluetooth service
            subprocess.run(['sudo', 'systemctl', 'restart', 'bluetooth'], check=False)
            
            return True, "Bluetooth adapter reset completed"
        except Exception as e:
            return False, f"Unable to reset bluetooth adapter: {e}"
    
    def _suggest_system_solutions(self, error_msg: str) -> Tuple[bool, str]:
        """Provide system-level troubleshooting suggestions."""
        suggestions = [
            "System-level troubleshooting suggestions:",
            "1. Reboot the system to reset all hardware",
            "2. Check dmesg for hardware errors: dmesg | grep -i bluetooth",
            "3. Reinstall bluetooth packages: sudo apt install --reinstall bluez",
            "4. Check for conflicting processes: sudo lsof /dev/rfcomm*",
            "5. Verify kernel modules: lsmod | grep bluetooth"
        ]
        
        return False, "\n".join(suggestions)
    
    def _generate_ble_troubleshooting_guide(self, error_msg: str) -> str:
        """Generate comprehensive BLE troubleshooting guide."""
        guide = [
            "BLE Troubleshooting Guide:",
            "=" * 50,
            f"Error: {error_msg}",
            "",
            "Quick Fixes:",
            "1. Check bluetooth service: sudo systemctl status bluetooth",
            "2. Add user to bluetooth group: sudo usermod -a -G bluetooth $USER",
            "3. Restart bluetooth: sudo systemctl restart bluetooth",
            "4. Check adapter status: hciconfig",
            "",
            "Hardware Issues:",
            "• Ensure bluetooth adapter is connected and recognized",
            "• Check USB connections for external adapters",
            "• Verify adapter compatibility with your system",
            "",
            "Permission Issues:",
            "• Log out and back in after adding to bluetooth group",
            "• Check /dev/rfcomm* permissions",
            "• Verify udev rules for bluetooth devices",
            "",
            "Virtualization Issues:",
            "• Ensure bluetooth passthrough is enabled",
            "• Check host system bluetooth functionality",
            "• Consider using USB passthrough for adapters",
            "",
            "If problems persist:",
            "• Check system logs: journalctl -u bluetooth",
            "• Test with bluetoothctl scan on",
            "• Contact system administrator for hardware verification"
        ]
        
        return "\n".join(guide)
    
    def _restore_from_backup(self, file_path: Path, backup_dir: Path) -> bool:
        """Attempt to restore file from backup."""
        try:
            if not backup_dir.exists():
                return False
            
            # Find most recent backup
            backup_files = list(backup_dir.glob(f"{file_path.name}.*"))
            if not backup_files:
                return False
            
            # Sort by modification time, newest first
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            latest_backup = backup_files[0]
            
            # Restore from backup
            shutil.copy2(latest_backup, file_path)
            self.logger.info(f"Restored {file_path} from backup: {latest_backup}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to restore from backup: {e}")
            return False
    
    def _create_minimal_file(self, file_path: Path) -> bool:
        """Create minimal valid file."""
        try:
            if file_path.suffix == '.json':
                # Create minimal JSON structure
                if 'metadata' in file_path.name:
                    minimal_data = {
                        "version": "1.0",
                        "created": datetime.now().isoformat(),
                        "sensors": {}
                    }
                else:
                    minimal_data = {}
                
                with open(file_path, 'w') as f:
                    json.dump(minimal_data, f, indent=2)
                
                self.logger.info(f"Created minimal JSON file: {file_path}")
                return True
            
            elif file_path.suffix in ['.conf', '.cfg']:
                # Create minimal config file
                with open(file_path, 'w') as f:
                    f.write(f"# Minimal configuration file created on {datetime.now()}\n")
                
                self.logger.info(f"Created minimal config file: {file_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to create minimal file: {e}")
            return False
        
        return False
    
    def _check_network_interface(self) -> bool:
        """Check if network interface is up."""
        try:
            interfaces = psutil.net_if_stats()
            for interface, stats in interfaces.items():
                if stats.isup and interface != 'lo':
                    return True
            return False
        except Exception:
            return False
    
    def _check_dns_resolution(self, host: str) -> bool:
        """Check DNS resolution."""
        try:
            import socket
            socket.gethostbyname(host)
            return True
        except Exception:
            return False
    
    def _check_port_connectivity(self, host: str, port: int) -> bool:
        """Check port connectivity."""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _check_firewall_rules(self, host: str, port: int) -> Optional[str]:
        """Check for potential firewall issues."""
        try:
            import subprocess
            
            # Check if ufw is active
            result = subprocess.run(['ufw', 'status'], capture_output=True, text=True)
            if 'Status: active' in result.stdout:
                if str(port) not in result.stdout:
                    return f"UFW firewall may be blocking port {port}"
            
            # Check iptables rules
            result = subprocess.run(['iptables', '-L'], capture_output=True, text=True)
            if 'DROP' in result.stdout or 'REJECT' in result.stdout:
                return "Iptables rules may be blocking connection"
                
        except Exception:
            pass
        
        return None
    
    def _perform_resource_cleanup(self) -> bool:
        """Perform resource cleanup."""
        try:
            cleanup_actions = []
            
            # Clean up log files if disk space is low
            disk = psutil.disk_usage('/')
            if (disk.used / disk.total) * 100 > 90:
                log_dir = Path(self.config.log_directory)
                if log_dir.exists():
                    # Remove old log files
                    for log_file in log_dir.glob('*.log.*'):
                        if log_file.stat().st_mtime < (datetime.now() - timedelta(days=7)).timestamp():
                            log_file.unlink()
                            cleanup_actions.append(f"Removed old log: {log_file}")
            
            # Force garbage collection if memory is high
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                import gc
                gc.collect()
                cleanup_actions.append("Forced garbage collection")
            
            if cleanup_actions:
                self.logger.info(f"Resource cleanup performed: {'; '.join(cleanup_actions)}")
                return True
                
        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")
        
        return False


class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass


class RecoveryError(Exception):
    """Exception raised when recovery operations fail."""
    pass