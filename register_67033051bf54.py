#!/usr/bin/env python3
"""Register device ID 67033051bf54 in Azure IoT Hub"""

import sys
import os
import json
import base64
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def register_device_67033051bf54():
    """Register device ID 67033051bf54 in Azure IoT Hub"""
    
    DEVICE_ID = "67033051bf54"
    
    print("🚀 REGISTERING DEVICE IN IOT HUB")
    print("=" * 40)
    print(f"📱 Device ID: {DEVICE_ID}")
    print()
    
    try:
        # Load config
        from utils.config import load_config
        config = load_config()
        
        if not config:
            print("❌ Failed to load config")
            return False
        
        # Get IoT Hub connection string
        iot_hub_config = config.get("iot_hub", {})
        connection_string = iot_hub_config.get("connection_string")
        
        if not connection_string:
            print("❌ IoT Hub connection string not found")
            return False
        
        print("✅ Config loaded")
        
        # Parse hostname
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        hostname = parts.get('HostName')
        
        if not hostname:
            print("❌ HostName not found")
            return False
        
        print(f"🌐 Hostname: {hostname}")
        
        # Initialize Registry Manager
        print("\n🔧 Initializing Registry Manager...")
        from azure.iot.hub import IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
        print("✅ Registry Manager initialized")
        
        # Check if device exists
        print(f"\n🔍 Checking device {DEVICE_ID}...")
        device_conn_str = None
        
        try:
            existing_device = registry_manager.get_device(DEVICE_ID)
            if existing_device and existing_device.authentication and existing_device.authentication.symmetric_key:
                primary_key = existing_device.authentication.symmetric_key.primary_key
                device_conn_str = f"HostName={hostname};DeviceId={DEVICE_ID};SharedAccessKey={primary_key}"
                print(f"✅ Device {DEVICE_ID} already exists")
            else:
                print("⚠️ Device exists but no keys")
                return False
        except Exception as e:
            if "Not Found" in str(e):
                print(f"ℹ️ Device {DEVICE_ID} not found, creating...")
                
                # Create device
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                
                device = registry_manager.create_device_with_sas(
                    device_id=DEVICE_ID,
                    primary_key=primary_key,
                    secondary_key=secondary_key,
                    status="enabled"
                )
                
                device_conn_str = f"HostName={hostname};DeviceId={DEVICE_ID};SharedAccessKey={primary_key}"
                print(f"✅ Device {DEVICE_ID} created")
            else:
                print(f"❌ Error checking device: {e}")
                return False
        
        # Test connection
        if device_conn_str:
            print("\n📡 Testing IoT Hub connection...")
            test_success = test_connection(device_conn_str, DEVICE_ID)
            return test_success
        else:
            print("❌ No connection string available")
            return False
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def test_connection(connection_string, device_id):
    """Test IoT Hub connection"""
    try:
        from iot.hub_client import HubClient
        
        hub_client = HubClient(connection_string)
        
        if hub_client.connect():
            print("✅ IoT Hub connected")
            
            # Send test message
            test_message = {
                "deviceId": device_id,
                "messageType": "registration_test",
                "timestamp": datetime.now().isoformat(),
                "test": True
            }
            
            success = hub_client.send_message(test_message, device_id)
            
            if success:
                print("✅ Test message sent")
            else:
                print("⚠️ Test message failed")
            
            hub_client.disconnect()
            return success
        else:
            print("❌ IoT Hub connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting device registration...")
    success = register_device_67033051bf54()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 REGISTRATION SUCCESSFUL! ✅")
        print("📱 Device 67033051bf54 ready for use")
    else:
        print("❌ REGISTRATION FAILED")
    print("=" * 40)
    
    sys.exit(0 if success else 1)