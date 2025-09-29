#!/usr/bin/env python3
"""
Configuration Status Checker
This script checks the current configuration status and shows which config file is being used.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from utils.config import load_config, get_config_path
    print("✅ Successfully imported config utilities")
except ImportError as e:
    print(f"❌ Failed to import config utilities: {e}")
    sys.exit(1)

def main():
    print("🔍 Barcode Scanner Configuration Status Check")
    print("=" * 50)
    
    # Check which config path will be used
    print("\n📁 Configuration Path Detection:")
    try:
        config_path = get_config_path()
        print(f"Selected config path: {config_path}")
        print(f"Config file exists: {'✅' if config_path.exists() else '❌'}")
        
        if config_path.exists():
            size = config_path.stat().st_size
            print(f"Config file size: {size} bytes")
        
    except Exception as e:
        print(f"❌ Error getting config path: {e}")
        return
    
    # Try to load the configuration
    print("\n⚙️ Configuration Loading:")
    try:
        config = load_config()
        
        if config is None:
            print("❌ Failed to load configuration")
            return
        
        print("✅ Configuration loaded successfully")
        
        # Show key configuration details
        print("\n📊 Configuration Summary:")
        
        # IoT Hub configuration
        iot_hub = config.get('iot_hub', {})
        connection_string = iot_hub.get('connection_string', '')
        device_id = iot_hub.get('deviceId', '')
        
        if connection_string:
            # Determine connection type
            if 'SharedAccessKeyName' in connection_string:
                conn_type = "IoT Hub Owner (Commercial)"
                print(f"🔑 Connection Type: {conn_type}")
                print(f"📱 Device ID Mode: Auto-generated from barcodes")
            elif 'DeviceId' in connection_string:
                conn_type = "Device Connection"
                print(f"🔑 Connection Type: {conn_type}")
                print(f"📱 Device ID: {device_id}")
            else:
                print(f"⚠️ Unknown connection string format")
            
            # Show hostname
            parts = dict(part.split('=', 1) for part in connection_string.split(';'))
            hostname = parts.get('HostName', 'Unknown')
            print(f"🌐 IoT Hub Hostname: {hostname}")
        else:
            print("❌ No IoT Hub connection string found")
        
        # API configuration
        api_config = config.get('api', {})
        if api_config:
            print(f"🔗 API Base URL: {api_config.get('base_url', 'Not configured')}")
        
        # Deployment mode
        deployment = config.get('deployment', {})
        if deployment:
            print(f"🚀 Deployment Mode: {deployment.get('mode', 'Not specified')}")
            print(f"🔧 Auto Registration: {deployment.get('auto_device_registration', False)}")
        
        # Raspberry Pi configuration
        pi_config = config.get('raspberry_pi', {})
        if pi_config:
            print(f"🍓 Pi Discovery: {pi_config.get('dynamic_discovery', False)}")
            print(f"📡 Remote Monitoring: {pi_config.get('remote_connectivity_monitoring', False)}")
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
