#!/usr/bin/env python3
"""
Client Configuration Update Script
This script helps update the configuration on Raspberry Pi clients to use the correct config.json file.
"""

import os
import json
import shutil
from pathlib import Path

def find_config_files():
    """Find all config.json files on the system"""
    print("🔍 Searching for config.json files...")
    
    # Common locations to search
    search_paths = [
        Path.home(),  # /home/pi
        Path("/var/www/html"),
        Path("/opt"),
        Path("/usr/local"),
        Path.cwd(),  # Current directory
    ]
    
    config_files = []
    
    for search_path in search_paths:
        if search_path.exists():
            try:
                # Find all config.json files recursively
                for config_file in search_path.rglob("config.json"):
                    if config_file.is_file():
                        config_files.append(config_file)
                        print(f"  ✅ Found: {config_file}")
            except PermissionError:
                print(f"  ⚠️ Permission denied: {search_path}")
            except Exception as e:
                print(f"  ❌ Error searching {search_path}: {e}")
    
    return config_files

def analyze_config_file(config_path):
    """Analyze a config file to determine its type and validity"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Check if it's a barcode scanner config
        has_iot_hub = 'iot_hub' in config
        has_barcode_scanner = 'barcode_scanner' in config
        has_api = 'api' in config
        
        # Check connection string type
        connection_string = config.get('iot_hub', {}).get('connection_string', '')
        is_owner_connection = 'SharedAccessKeyName' in connection_string
        is_device_connection = 'DeviceId' in connection_string
        
        info = {
            'path': config_path,
            'size': config_path.stat().st_size,
            'modified': config_path.stat().st_mtime,
            'is_barcode_config': has_iot_hub and has_barcode_scanner,
            'has_api_config': has_api,
            'connection_type': 'owner' if is_owner_connection else 'device' if is_device_connection else 'none',
            'valid': has_iot_hub and connection_string
        }
        
        return info
    except Exception as e:
        return {
            'path': config_path,
            'error': str(e),
            'valid': False
        }

def copy_config_to_client_location(source_config, target_dir):
    """Copy the correct config to the client location"""
    try:
        target_path = target_dir / 'config.json'
        
        # Create backup if target exists
        if target_path.exists():
            backup_path = target_path.with_suffix('.json.backup')
            shutil.copy2(target_path, backup_path)
            print(f"  📦 Backup created: {backup_path}")
        
        # Copy the source config
        shutil.copy2(source_config, target_path)
        print(f"  ✅ Config copied to: {target_path}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error copying config: {e}")
        return False

def main():
    print("🔧 Barcode Scanner Client Configuration Update Tool")
    print("=" * 60)
    
    # Find all config files
    config_files = find_config_files()
    
    if not config_files:
        print("❌ No config.json files found!")
        return
    
    print(f"\n📊 Analyzing {len(config_files)} config files...")
    
    # Analyze each config file
    valid_configs = []
    for config_file in config_files:
        info = analyze_config_file(config_file)
        
        print(f"\n📄 {config_file}")
        if 'error' in info:
            print(f"  ❌ Error: {info['error']}")
        else:
            print(f"  📏 Size: {info['size']} bytes")
            print(f"  🔧 Barcode Config: {'✅' if info['is_barcode_config'] else '❌'}")
            print(f"  🌐 API Config: {'✅' if info['has_api_config'] else '❌'}")
            print(f"  🔑 Connection: {info['connection_type']}")
            print(f"  ✅ Valid: {'✅' if info['valid'] else '❌'}")
            
            if info['valid'] and info['is_barcode_config']:
                valid_configs.append(info)
    
    if not valid_configs:
        print("\n❌ No valid barcode scanner config files found!")
        return
    
    print(f"\n🎯 Found {len(valid_configs)} valid barcode scanner configs:")
    for i, config in enumerate(valid_configs, 1):
        print(f"  {i}. {config['path']} ({config['connection_type']} connection)")
    
    # Find the best config (prefer owner connections for commercial deployment)
    best_config = None
    for config in valid_configs:
        if config['connection_type'] == 'owner':
            best_config = config
            break
    
    if not best_config:
        best_config = valid_configs[0]
    
    print(f"\n🏆 Best config selected: {best_config['path']}")
    
    # Determine client deployment locations
    client_locations = [
        Path.home() / "azure-iot-hub-python" / "deployment_package",
        Path.home() / "barcode_scanner_clean" / "deployment_package", 
        Path("/opt/barcode_scanner/deployment_package"),
        Path.cwd() / "deployment_package"
    ]
    
    print(f"\n📋 Updating client locations...")
    updated_count = 0
    
    for location in client_locations:
        if location.exists():
            print(f"\n📁 Updating: {location}")
            if copy_config_to_client_location(best_config['path'], location):
                updated_count += 1
        else:
            print(f"  ⚠️ Location not found: {location}")
    
    print(f"\n🎉 Configuration update complete!")
    print(f"✅ Updated {updated_count} client locations")
    print(f"🔧 Using config: {best_config['path']}")
    
    # Show next steps
    print(f"\n📋 Next Steps:")
    print(f"1. Restart the barcode scanner service on the Raspberry Pi")
    print(f"2. Check that it's using the correct config path")
    print(f"3. Verify IoT Hub connectivity")

if __name__ == "__main__":
    main()
