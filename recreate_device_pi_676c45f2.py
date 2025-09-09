#!/usr/bin/env python3
"""
Recreate device pi-676c45f2 in Azure IoT Hub
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def recreate_device():
    """Recreate device in Azure IoT Hub"""
    device_id = "pi-676c45f2"
    
    print(f"🔄 Recreating device: {device_id}")
    
    try:
        from utils.dynamic_registration_service import DynamicRegistrationService
        from utils.config import load_config
        
        # Load config
        config = load_config()
        reg_service = DynamicRegistrationService(config)
        
        # Delete device if it exists
        try:
            print(f"🗑️ Attempting to delete existing device...")
            reg_service.delete_device_from_azure(device_id)
            print(f"✅ Device deleted (or didn't exist)")
        except Exception as e:
            print(f"ℹ️ Delete attempt: {e}")
        
        # Create new device
        print(f"🆕 Creating new device...")
        conn_str = reg_service.register_device_with_azure(device_id)
        
        if conn_str:
            print(f"✅ Device {device_id} created successfully")
            print(f"Connection string preview: {conn_str[:50]}...")
            
            # Test the new connection
            print(f"🧪 Testing new connection...")
            from iot.hub_client import HubClient
            hub_client = HubClient(conn_str)
            
            if hub_client.connect():
                print(f"✅ Connection test successful")
                
                # Send test registration message
                test_message = {
                    "deviceId": device_id,
                    "messageType": "device_registration",
                    "status": "recreated",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                success = hub_client.send_message(test_message, device_id)
                if success:
                    print(f"✅ Test registration message sent")
                else:
                    print(f"⚠️ Test message failed")
                
                return True
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
    """Main recreation function"""
    print("🔄 Device Recreation Script")
    print("=" * 50)
    
    success = recreate_device()
    
    if success:
        print("\n🎉 Recreation Complete!")
        print("✅ Device pi-676c45f2 recreated and tested")
        print("📡 Registration message sent to IoT Hub")
    else:
        print("\n❌ Recreation Failed!")
        print("Check the error messages above")

if __name__ == "__main__":
    main()