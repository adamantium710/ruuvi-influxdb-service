#!/usr/bin/env python3
"""
Debug script to test metadata save operations and identify the file operation issue.
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from src.utils.config import Config
from src.utils.logging import ProductionLogger
from src.metadata.manager import MetadataManager

def test_file_operations():
    """Test the file operations that are failing."""
    
    print("=== Testing File Operations ===")
    
    # Test basic file creation in data directory
    data_dir = Path("data")
    test_file = data_dir / "test.tmp"
    final_file = data_dir / "test.json"
    
    try:
        # Create test file
        with open(test_file, 'w') as f:
            json.dump({"test": "data"}, f)
        print(f"✓ Created temporary file: {test_file}")
        
        # Test atomic move
        test_file.replace(final_file)
        print(f"✓ Atomic move successful: {test_file} -> {final_file}")
        
        # Cleanup
        if final_file.exists():
            final_file.unlink()
            print("✓ Cleanup successful")
            
    except Exception as e:
        print(f"✗ File operation failed: {e}")
        return False
    
    return True

def test_metadata_manager():
    """Test the MetadataManager save operation."""
    
    print("\n=== Testing MetadataManager ===")
    
    try:
        # Initialize config and logger
        config = Config()
        logger = ProductionLogger(config)
        
        print(f"Metadata file path: {config.metadata_file}")
        print(f"Backup directory: {config.backup_dir}")
        
        # Initialize metadata manager
        manager = MetadataManager(config, logger)
        
        # Load current metadata
        metadata = manager.load()
        print(f"✓ Loaded metadata with {len(metadata.sensors)} sensors")
        
        # Try to save metadata
        manager.save()
        print("✓ Metadata save successful")
        
    except Exception as e:
        print(f"✗ MetadataManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def check_permissions():
    """Check file permissions and ownership."""
    
    print("\n=== Checking Permissions ===")
    
    data_dir = Path("data")
    backup_dir = Path("backups")
    
    for directory in [data_dir, backup_dir]:
        if directory.exists():
            stat = directory.stat()
            print(f"{directory}: mode={oct(stat.st_mode)}, uid={stat.st_uid}, gid={stat.st_gid}")
        else:
            print(f"{directory}: does not exist")
    
    # Check metadata file
    metadata_file = data_dir / "metadata.json"
    if metadata_file.exists():
        stat = metadata_file.stat()
        print(f"{metadata_file}: mode={oct(stat.st_mode)}, uid={stat.st_uid}, gid={stat.st_gid}")

def main():
    """Main debug function."""
    
    print("Ruuvi Metadata Save Debug Tool")
    print("=" * 40)
    
    # Check current user
    print(f"Running as: uid={os.getuid()}, gid={os.getgid()}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check permissions
    check_permissions()
    
    # Test basic file operations
    if not test_file_operations():
        print("\n❌ Basic file operations failed!")
        return 1
    
    # Test metadata manager
    if not test_metadata_manager():
        print("\n❌ MetadataManager test failed!")
        return 1
    
    print("\n✅ All tests passed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())