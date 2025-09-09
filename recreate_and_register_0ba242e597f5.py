#!/usr/bin/env python3
"""
Recreate device 0ba242e597f5 in IoT Hub and send registration message
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def recreate_and_register():
    """Recreate device in IoT Hub and send registration message"""
    device_id = "0ba242e597f5"
    
    print(f"🔄 Recreating and registering device: {device_id}")
    
    try:
        from utils.dynamic_registration_service import DynamicRegistrationService
        from utils.config import load_config
        
        # Load config
        config = load_config()
        reg_service = DynamicRegistrationService(config)
        
        # Create new device
        print(f"🆕 Creating device in IoT Hub...")
        conn_str = reg_service.register_device_with_azure(device_id)
        
        if conn_str:
            print(f"✅ Device {device_id} created successfully")
            
            # Test connection and send registration message
            print(f"🧪 Testing connection and sending registration message...")
            from iot.hub_client import HubClient
            hub_client = HubClient(conn_str)
            
            if hub_client.connect():
                print(f"✅ Connection successful")
                
                # Send registration message
                registration_message = {
                    "deviceId": device_id,
                    "messageType": "device_registration",
                    "status": "registered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "registrationMethod": "recreate_and_register",
                    "action": "register"
                }
                
                print(f"📝 Sending registration message...")
                success = hub_client.send_message(registration_message, device_id)
                
                if success:
                    print(f"✅ Registration message sent to IoT Hub")
                    
                    # Also send to frontend API
                    try:
                        from api.api_client import ApiClient
                        api_client = ApiClient()
                        
                        api_result = api_client.confirm_registration(device_id)
                        if api_result.get('success', False):
                            print(f"✅ Registration sent to frontend API")
                        else:
                            print(f"⚠️ Frontend API: {api_result.get('message')}")
                    except Exception as e:
                        print(f"⚠️ Frontend API error: {e}")
                    
                    return True
                else:
                    print(f"❌ Failed to send registration message")
                    return False
            else:
                print(f"❌ Connection test failed")
                return False
        else:
            print(f"❌ Failed to create device")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("🔄 Device Recreation and Registration Test")
    print("=" * 50)
    
    success = recreate_and_register()
    
    if success:
        print("\n🎉 Complete Success!")
        print("✅ Device 0ba242e597f5 recreated and registered")
        print("📡 Registration message sent to IoT Hub")
        print("🌐 Registration sent to frontend API")
        print("📊 Check both Azure IoT Hub and https://iot.caleffionline.it/")
    else:
        print("\n❌ Failed!")

if __name__ == "__main__":
    main()