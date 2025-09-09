#!/usr/bin/env python3
"""
Register device 84b772dc334a using the app's registration functionality
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def register_device_84b772dc334a():
    """Register device 84b772dc334a"""
    device_id = "84b772dc334a"
    
    print(f"🚀 Registering device: {device_id}")
    
    try:
        # Step 1: Register with API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {"deviceId": device_id}
        
        print(f"📡 Sending to API: {api_url}")
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"API Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Device {device_id} registered with API successfully")
            
            # Step 2: Register with IoT Hub
            try:
                from utils.dynamic_device_manager import device_manager
                
                device_info = {
                    "registration_method": "manual_registration",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "registered_via": "registration_script"
                }
                
                success, message = device_manager.register_device_without_token(device_id, device_info)
                
                if success:
                    print(f"✅ Device {device_id} registered with IoT Hub successfully")
                else:
                    print(f"⚠️ IoT Hub registration warning: {message}")
                    
            except Exception as e:
                print(f"⚠️ IoT Hub registration error: {e}")
            
            # Step 3: Save locally
            try:
                from database.local_storage import LocalStorage
                local_db = LocalStorage()
                local_db.save_device_registration(device_id, datetime.now(timezone.utc).isoformat())
                print(f"✅ Device {device_id} saved to local database")
            except Exception as e:
                print(f"⚠️ Local save error: {e}")
            
            return True
        else:
            print(f"❌ API registration failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def main():
    """Main registration function"""
    print("🎯 Device Registration Script")
    print("=" * 50)
    
    success = register_device_84b772dc334a()
    
    if success:
        print("\n🎉 Registration Complete!")
        print("✅ Device 84b772dc334a is now registered")
        print("📊 Check https://iot.caleffionline.it/ to see the device")
    else:
        print("\n❌ Registration Failed!")
        print("Please check the error messages above")

if __name__ == "__main__":
    main()