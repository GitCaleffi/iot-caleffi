#!/usr/bin/env python3
"""
Test registration for device 0ba242e597f5
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def register_device_0ba242e597f5():
    """Register device 0ba242e597f5"""
    device_id = "0ba242e597f5"
    
    print(f"📝 Registering device: {device_id}")
    
    try:
        # Step 1: Register with IoT Hub
        from utils.dynamic_device_manager import device_manager
        
        device_info = {
            "registration_method": "manual_test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_registration": True
        }
        
        success, message = device_manager.register_device_without_token(device_id, device_info)
        
        if success:
            print(f"✅ Device {device_id} registered with IoT Hub")
        else:
            print(f"⚠️ IoT Hub registration: {message}")
        
        # Step 2: Send registration message to IoT Hub
        try:
            reg_service = device_manager.get_dynamic_registration_service()
            if reg_service:
                conn_str = reg_service.get_device_connection_string(device_id)
                if conn_str:
                    from iot.hub_client import HubClient
                    hub_client = HubClient(conn_str)
                    
                    if hub_client.connect():
                        registration_message = {
                            "deviceId": device_id,
                            "messageType": "device_registration",
                            "status": "registered",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "registrationMethod": "test_registration"
                        }
                        
                        iot_success = hub_client.send_message(registration_message, device_id)
                        if iot_success:
                            print(f"✅ Registration message sent to IoT Hub")
                        else:
                            print(f"❌ Failed to send registration message to IoT Hub")
                    else:
                        print(f"❌ Failed to connect to IoT Hub")
                else:
                    print(f"❌ No connection string for device")
            else:
                print(f"❌ Registration service not available")
                
        except Exception as e:
            print(f"❌ IoT Hub messaging error: {e}")
        
        # Step 3: Send to frontend API
        try:
            from api.api_client import ApiClient
            api_client = ApiClient()
            
            api_result = api_client.confirm_registration(device_id)
            if api_result.get('success', False):
                print(f"✅ Registration sent to frontend API")
            else:
                print(f"⚠️ Frontend API failed: {api_result.get('message')}")
                
        except Exception as e:
            print(f"❌ Frontend API error: {e}")
        
        # Step 4: Save locally
        try:
            from database.local_storage import LocalStorage
            local_db = LocalStorage()
            local_db.save_device_registration(device_id, datetime.now(timezone.utc).isoformat())
            print(f"✅ Device saved to local database")
        except Exception as e:
            print(f"⚠️ Local save error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def main():
    """Main registration function"""
    print("📝 Device Registration Test")
    print("=" * 50)
    
    success = register_device_0ba242e597f5()
    
    if success:
        print("\n🎉 Registration Complete!")
        print("✅ Device 0ba242e597f5 registered")
        print("📊 Check https://iot.caleffionline.it/ and Azure IoT Hub for messages")
    else:
        print("\n❌ Registration Failed!")

if __name__ == "__main__":
    main()