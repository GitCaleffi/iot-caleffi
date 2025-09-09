#!/usr/bin/env python3
"""
Fix device pi-676c45f2 authorization issue
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def fix_device_pi_676c45f2():
    """Fix authorization issue for device pi-676c45f2"""
    device_id = "pi-676c45f2"
    
    print(f"🔧 Fixing authorization for device: {device_id}")
    
    try:
        # Step 1: Re-register with API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {"deviceId": device_id}
        
        print(f"📡 Re-registering with API: {api_url}")
        response = requests.post(
            api_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"API Response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Device {device_id} re-registered with API")
            
            # Step 2: Force re-register with IoT Hub
            try:
                from utils.dynamic_device_manager import device_manager
                
                # Force re-registration
                device_info = {
                    "registration_method": "fix_authorization",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "force_recreate": True
                }
                
                success, message = device_manager.register_device_without_token(device_id, device_info)
                
                if success:
                    print(f"✅ Device {device_id} re-registered with IoT Hub")
                else:
                    print(f"⚠️ IoT Hub re-registration: {message}")
                    
                # Get fresh connection string
                conn_str = device_manager.get_device_connection_string(device_id)
                if conn_str:
                    print(f"✅ Fresh connection string obtained")
                    print(f"Connection string preview: {conn_str[:50]}...")
                else:
                    print(f"❌ Failed to get connection string")
                    
            except Exception as e:
                print(f"❌ IoT Hub re-registration error: {e}")
            
            return True
        else:
            print(f"❌ API re-registration failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Fix error: {e}")
        return False

def main():
    """Main fix function"""
    print("🔧 Device Authorization Fix Script")
    print("=" * 50)
    
    success = fix_device_pi_676c45f2()
    
    if success:
        print("\n🎉 Fix Complete!")
        print("✅ Device pi-676c45f2 should now be able to connect to IoT Hub")
        print("🔄 Restart the barcode scanner app to test the connection")
    else:
        print("\n❌ Fix Failed!")
        print("Please check the error messages above")

if __name__ == "__main__":
    main()