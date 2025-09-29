#!/usr/bin/env python3
"""
Emergency Fix for Device ID Issue
Run this to fix the problematic device ID 17994ccfe143
"""

import sys
import json
from pathlib import Path

def fix_problematic_device():
    """Fix the problematic device ID 17994ccfe143"""
    print("🚨 Emergency Fix for Device ID Issue")
    print("=" * 40)
    
    problematic_id = "17994ccfe143"
    print(f"🎯 Target problematic device ID: {problematic_id}")
    
    # Check device_config.json
    config_file = Path("device_config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            devices = config.get('devices', {})
            if problematic_id in devices:
                print(f"❌ Found problematic device in config: {problematic_id}")
                
                # Remove the problematic device
                del devices[problematic_id]
                
                # Save updated config
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                print(f"✅ Removed problematic device from config")
            else:
                print(f"✅ Problematic device not found in config")
                
        except Exception as e:
            print(f"❌ Error checking config: {e}")
    
    # Check local database
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'deployment_package' / 'src'))
        from database.local_storage import LocalStorage
        
        local_db = LocalStorage()
        
        # Check if problematic device exists in database
        device_id = local_db.get_device_id()
        if device_id == problematic_id:
            print(f"❌ Found problematic device in database: {device_id}")
            
            # Clear the device ID (this will force re-registration with proper ID)
            # Note: This would require adding a method to LocalStorage
            print(f"⚠️ Manual intervention needed to clear device from database")
        else:
            print(f"✅ Database device ID is OK: {device_id}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    print(f"\n📋 Next steps:")
    print(f"1. Restart the barcode scanner service")
    print(f"2. Use proper device registration with valid device ID")
    print(f"3. Avoid using test barcodes as device IDs")

if __name__ == "__main__":
    fix_problematic_device()
