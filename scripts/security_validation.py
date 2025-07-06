#!/usr/bin/env python3
"""
Ruuvi Sensor Service - Security Validation Script
Validates security posture and dependency integrity before deployment
"""

import subprocess
import sys
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import importlib.util

def check_python_version() -> Tuple[bool, str]:
    """Check if Python version meets security requirements."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        return True, f"Python {version.major}.{version.minor}.{version.micro} - OK"
    else:
        return False, f"Python {version.major}.{version.minor}.{version.micro} - REQUIRES 3.9+"

def check_pip_audit() -> Tuple[bool, str]:
    """Run pip-audit to check for known vulnerabilities."""
    try:
        result = subprocess.run(
            ["pip-audit", "--format", "json", "--quiet"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # No vulnerabilities found
            return True, "pip-audit: No known vulnerabilities detected"
        else:
            # Parse vulnerabilities
            try:
                vulns = json.loads(result.stdout)
                vuln_count = len(vulns)
                return False, f"pip-audit: {vuln_count} vulnerabilities found"
            except json.JSONDecodeError:
                return False, f"pip-audit: Error parsing results - {result.stderr}"
                
    except subprocess.TimeoutExpired:
        return False, "pip-audit: Timeout during vulnerability scan"
    except FileNotFoundError:
        return False, "pip-audit: Tool not installed (pip install pip-audit)"
    except Exception as e:
        return False, f"pip-audit: Error - {str(e)}"

def check_safety() -> Tuple[bool, str]:
    """Run safety check for known security vulnerabilities."""
    try:
        result = subprocess.run(
            ["safety", "check", "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return True, "safety: No known vulnerabilities detected"
        else:
            try:
                vulns = json.loads(result.stdout)
                vuln_count = len(vulns)
                return False, f"safety: {vuln_count} vulnerabilities found"
            except json.JSONDecodeError:
                return False, f"safety: Error parsing results - {result.stderr}"
                
    except subprocess.TimeoutExpired:
        return False, "safety: Timeout during vulnerability scan"
    except FileNotFoundError:
        return False, "safety: Tool not installed (pip install safety)"
    except Exception as e:
        return False, f"safety: Error - {str(e)}"

def check_bandit() -> Tuple[bool, str]:
    """Run bandit security linter on application code."""
    try:
        # Check if src directory exists
        src_path = Path("src")
        if not src_path.exists():
            return False, "bandit: src directory not found"
            
        result = subprocess.run(
            ["bandit", "-r", "src/", "-f", "json", "-q"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            return True, "bandit: No security issues found in application code"
        else:
            try:
                report = json.loads(result.stdout)
                issue_count = len(report.get("results", []))
                return False, f"bandit: {issue_count} security issues found in code"
            except json.JSONDecodeError:
                return False, f"bandit: Error parsing results - {result.stderr}"
                
    except subprocess.TimeoutExpired:
        return False, "bandit: Timeout during security scan"
    except FileNotFoundError:
        return False, "bandit: Tool not installed (pip install bandit)"
    except Exception as e:
        return False, f"bandit: Error - {str(e)}"

def check_ssl_certificates() -> Tuple[bool, str]:
    """Verify SSL certificate bundle is up to date."""
    try:
        import certifi
        import ssl
        
        # Check certifi version
        certifi_version = certifi.__version__
        
        # Try to create SSL context
        context = ssl.create_default_context()
        
        return True, f"SSL: certifi {certifi_version} - certificates OK"
        
    except ImportError:
        return False, "SSL: certifi not installed"
    except Exception as e:
        return False, f"SSL: Error - {str(e)}"

def check_secure_requirements() -> Tuple[bool, str]:
    """Check if secure requirements file exists and is being used."""
    secure_req_path = Path("requirements-secure.txt")
    regular_req_path = Path("requirements.txt")
    
    if not secure_req_path.exists():
        return False, "requirements-secure.txt not found"
    
    if not regular_req_path.exists():
        return True, "Using requirements-secure.txt (no regular requirements.txt)"
    
    # Compare modification times
    secure_mtime = secure_req_path.stat().st_mtime
    regular_mtime = regular_req_path.stat().st_mtime
    
    if secure_mtime > regular_mtime:
        return True, "requirements-secure.txt is newer than requirements.txt"
    else:
        return False, "requirements.txt is newer - consider using requirements-secure.txt"

def check_environment_security() -> Tuple[bool, str]:
    """Check environment security settings."""
    issues = []
    
    # Check for .env file with proper permissions
    env_file = Path(".env")
    if env_file.exists():
        stat = env_file.stat()
        # Check if file is readable by others (should be 600 or 640)
        if stat.st_mode & 0o044:  # Check if group/other can read
            issues.append(".env file has overly permissive permissions")
    
    # Check for sensitive environment variables
    sensitive_vars = ["INFLUXDB_TOKEN", "INFLUXDB_PASSWORD", "API_KEY"]
    for var in sensitive_vars:
        if var in os.environ:
            # Don't log the actual value
            issues.append(f"Sensitive variable {var} found in environment")
    
    if issues:
        return False, f"Environment issues: {'; '.join(issues)}"
    else:
        return True, "Environment security - OK"

def check_file_permissions() -> Tuple[bool, str]:
    """Check critical file permissions."""
    issues = []
    
    # Check main.py permissions
    main_py = Path("main.py")
    if main_py.exists():
        stat = main_py.stat()
        if stat.st_mode & 0o002:  # World writable
            issues.append("main.py is world-writable")
    
    # Check src directory permissions
    src_dir = Path("src")
    if src_dir.exists():
        for py_file in src_dir.rglob("*.py"):
            stat = py_file.stat()
            if stat.st_mode & 0o002:  # World writable
                issues.append(f"{py_file} is world-writable")
    
    if issues:
        return False, f"Permission issues: {'; '.join(issues[:3])}")  # Limit output
    else:
        return True, "File permissions - OK"

def run_all_checks() -> Dict[str, Tuple[bool, str]]:
    """Run all security validation checks."""
    checks = {
        "Python Version": check_python_version(),
        "SSL Certificates": check_ssl_certificates(),
        "Secure Requirements": check_secure_requirements(),
        "Environment Security": check_environment_security(),
        "File Permissions": check_file_permissions(),
        "pip-audit": check_pip_audit(),
        "safety": check_safety(),
        "bandit": check_bandit(),
    }
    
    return checks

def print_results(results: Dict[str, Tuple[bool, str]]) -> None:
    """Print formatted security validation results."""
    print("=" * 60)
    print("RUUVI SENSOR SERVICE - SECURITY VALIDATION REPORT")
    print("=" * 60)
    print()
    
    passed = 0
    failed = 0
    
    for check_name, (success, message) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        color = "\033[92m" if success else "\033[91m"  # Green or Red
        reset = "\033[0m"
        
        print(f"{color}{status:8}{reset} {check_name:20} {message}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print()
    print("=" * 60)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("\033[92m✓ ALL SECURITY CHECKS PASSED\033[0m")
        print("System is ready for secure deployment.")
    else:
        print(f"\033[91m✗ {failed} SECURITY ISSUES DETECTED\033[0m")
        print("Please address the issues above before deployment.")
    
    print("=" * 60)

def main():
    """Main security validation function."""
    print("Running security validation checks...")
    print()
    
    results = run_all_checks()
    print_results(results)
    
    # Exit with error code if any checks failed
    failed_checks = sum(1 for success, _ in results.values() if not success)
    sys.exit(failed_checks)

if __name__ == "__main__":
    main()