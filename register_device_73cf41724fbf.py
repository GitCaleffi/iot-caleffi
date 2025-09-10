#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment_package/src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from utils.config import load_config
from utils.dynamic_registration_service import get_dynamic_registration_service
from database.local_storage import LocalStorage
from iot.hub_client import HubClient

def register_device_e0999b9c7158():
    """Register device e0999b9c7158"""
    
    device_id = "e0999b9c7158"
    
    print("=" * 60)
    print("🔔 REGISTERING DEVICE e0999b9c7158")
    print("=" * 60)
    print(f"Device ID: {device_id}")
    print("=" * 60)
    
    try:
        # Step 1: Load configuration
        print(f"\n🔧 Step 1: Loading configuration...")
        config = load_config()
        print("✅ Configuration loaded")
        
        # Step 2: Initialize local storage
        print(f"\n🔧 Step 2: Initializing local storage...")
        local_db = LocalStorage()
        
        # Check if device already registered
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            print(f"⚠️ Device {device_id} is already registered")
            # Show registration date
            for device in registered_devices:
                if device['device_id'] == device_id:
                    print(f"📅 Registration date: {device.get('registration_date', 'Unknown')}")
            
            # Send fresh registration notification even if already registered
            print(f"\n🔔 Sending fresh registration notification to IoT Hub...")
            
            # Get connection string for existing device
            iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
            reg_service = get_dynamic_registration_service(iot_hub_connection_string)
            device_connection_string = reg_service.register_device_with_azure(device_id)
            
            if device_connection_string:
                hub_client = HubClient(device_connection_string)
                
                registration_message = {
                    "messageType": "device_registration",
                    "action": "register",
                    "deviceId": device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "registration_method": "refresh_registration",
                    "status": "registered",
                    "message": f"Device {device_id} registration refreshed successfully"
                }
                
                success = hub_client.send_message(registration_message, device_id)
                
                if success:
                    print("✅ Fresh registration notification sent to IoT Hub")
                else:
                    print("⚠️ Failed to send fresh registration notification")
            
            return True
        
        print("✅ Local storage initialized - device not yet registered")
        
        # Step 3: Register with Azure IoT Hub
        print(f"\n🔧 Step 3: Registering device with Azure IoT Hub...")
        iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
        
        if not iot_hub_connection_string:
            print("❌ No IoT Hub connection string found in config")
            return False
            
        reg_service = get_dynamic_registration_service(iot_hub_connection_string)
        
        if not reg_service:
            print("❌ Failed to get dynamic registration service")
            return False
            
        device_connection_string = reg_service.register_device_with_azure(device_id)
        
        if not device_connection_string:
            print("❌ Failed to get device connection string")
            return False
            
        print("✅ Device registered with Azure IoT Hub")
        
        # Step 4: Save to local database
        print(f"\n🔧 Step 4: Saving to local database...")
        local_db.save_device_registration(device_id, datetime.now(timezone.utc).isoformat())
        print("✅ Device saved to local database")
        
        # Step 5: Send registration notification to IoT Hub
        print(f"\n🔧 Step 5: Sending registration notification to IoT Hub...")
        hub_client = HubClient(device_connection_string)
        
        registration_message = {
            "messageType": "device_registration",
            "action": "register",
            "deviceId": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "registration_method": "manual_registration",
            "status": "registered",
            "message": "Device 73cf41724fbf registration completed successfully"
        }
        
        success = hub_client.send_message(registration_message, device_id)
        
        if success:
            print("✅ Registration notification sent to IoT Hub")
        else:
            print("⚠️ Failed to send registration notification to IoT Hub")
        
        # Step 6: Summary
        print(f"\n" + "=" * 60)
        print("🎉 DEVICE 73cf41724fbf REGISTRATION COMPLETED")
        print("=" * 60)
        print(f"✅ Device ID: {device_id}")
        print(f"✅ Azure IoT Hub: Registered")
        print(f"✅ Local Database: Saved")
        print(f"✅ IoT Hub Notification: {'Sent' if success else 'Failed'}")
        print(f"📅 Registration Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Error during registration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting device e0999b9c7158 registration...")
    success = register_device_e0999b9c7158()
    
    if success:
        print("\n🎉 Device e0999b9c7158 registered successfully!")
        print("📱 Check IoT Hub for registration messages")
    else:
        print("\n💥 Device e0999b9c7158 registration failed!")
        print("🔍 Check error logs for troubleshooting")
