#!/usr/bin/env python3
"""Simple registration script for device ID 149f33d4a830"""

import sys
import os
import json
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def simple_register_device():
    """Simple device registration using Azure IoT Hub Registry Manager directly"""
    
    DEVICE_ID = "149f33d4a830"
    
    print("🚀 SIMPLE DEVICE REGISTRATION")
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
            print("❌ IoT Hub connection string not found in config")
            return False
        
        print("✅ Config loaded successfully")
        print(f"🔗 IoT Hub: {connection_string[:50]}...")
        
        # Parse hostname from connection string
        try:
            parts = dict(part.split('=', 1) for part in connection_string.split(';'))
            hostname = parts.get('HostName')
            if not hostname:
                print("❌ HostName not found in connection string")
                return False
            print(f"🌐 Hostname: {hostname}")
        except Exception as e:
            print(f"❌ Error parsing connection string: {e}")
            return False
        
        # Initialize Azure IoT Hub Registry Manager
        print("\n🔧 Initializing Azure IoT Hub Registry Manager...")
        try:
            from azure.iot.hub import IoTHubRegistryManager
            registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
            print("✅ Registry Manager initialized")
        except Exception as e:
            print(f"❌ Registry Manager initialization failed: {e}")
            return False
        
        # Check if device already exists
        print(f"\n🔍 Checking if device {DEVICE_ID} exists...")
        try:
            existing_device = registry_manager.get_device(DEVICE_ID)
            if existing_device:
                print(f"✅ Device {DEVICE_ID} already exists")
                
                # Get connection string for existing device
                if existing_device.authentication and existing_device.authentication.symmetric_key:
                    primary_key = existing_device.authentication.symmetric_key.primary_key
                    device_conn_str = f"HostName={hostname};DeviceId={DEVICE_ID};SharedAccessKey={primary_key}"
                    print(f"🔗 Device connection string: {device_conn_str[:50]}...")
                    
                    # Test the connection
                    print("\n📡 Testing IoT Hub connection...")
                    test_success = test_iot_hub_connection(device_conn_str, DEVICE_ID)
                    
                    return test_success
                else:
                    print("⚠️ Device exists but has no authentication keys")
                    return False
        except Exception as e:
            if "Not Found" in str(e):
                print(f"ℹ️ Device {DEVICE_ID} does not exist, will create it")
            else:
                print(f"❌ Error checking device: {e}")
                return False
        
        # Create new device
        print(f"\n📝 Creating device {DEVICE_ID}...")
        try:
            import base64
            
            # Generate secure keys
            primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            
            device = registry_manager.create_device_with_sas(
                device_id=DEVICE_ID,
                primary_key=primary_key,
                secondary_key=secondary_key,
                status="enabled"
            )
            
            print(f"✅ Device {DEVICE_ID} created successfully")
            
            # Generate connection string
            device_conn_str = f"HostName={hostname};DeviceId={DEVICE_ID};SharedAccessKey={primary_key}"
            print(f"🔗 Device connection string: {device_conn_str[:50]}...")
            
            # Test the connection
            print("\n📡 Testing IoT Hub connection...")
            test_success = test_iot_hub_connection(device_conn_str, DEVICE_ID)
            
            return test_success
            
        except Exception as e:
            print(f"❌ Error creating device: {e}")
            return False\n        \n    except Exception as e:\n        print(f"❌ Registration error: {e}")\n        return False\n\ndef test_iot_hub_connection(connection_string, device_id):
    """Test IoT Hub connection and send a test message"""
    try:
        from iot.hub_client import HubClient
        
        hub_client = HubClient(connection_string)
        
        if hub_client.connect():
            print("✅ IoT Hub connection successful")
            
            # Send test message
            test_message = {
                "deviceId": device_id,
                "messageType": "registration_test",
                "barcode": "4545452521452",
                "timestamp": datetime.now().isoformat(),
                "test": True,
                "status": "device_registered"
            }
            
            send_success = hub_client.send_message(json.dumps(test_message), device_id)
            
            if send_success:
                print("✅ Test message sent successfully")
                print(f"📤 Message: {json.dumps(test_message, indent=2)}")
            else:
                print("⚠️ Test message send failed")
            
            hub_client.disconnect()
            return send_success
        else:
            print("❌ IoT Hub connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting simple device registration...")
    success = simple_register_device()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 DEVICE REGISTRATION SUCCESSFUL! ✅")
        print("📱 Device 149f33d4a830 is ready for barcode scanning")
        print("📡 IoT Hub connection verified")
        print("📤 Test message sent successfully")
    else:
        print("❌ DEVICE REGISTRATION FAILED")
        print("🔧 Check the errors above")
    print("=" * 40)
    
    sys.exit(0 if success else 1)