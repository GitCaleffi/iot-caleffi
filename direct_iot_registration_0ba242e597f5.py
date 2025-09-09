#!/usr/bin/env python3
"""
Direct IoT Hub registration for device 0ba242e597f5
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def direct_iot_registration():
    """Send registration message directly to IoT Hub"""
    device_id = "0ba242e597f5"
    
    print(f"📡 Direct IoT Hub registration for: {device_id}")
    
    try:
        # Get device manager
        from utils.dynamic_device_manager import device_manager
        
        # Get connection string
        conn_str = device_manager.get_device_connection_string(device_id)
        if not conn_str:
            print("❌ No connection string available")
            return False
        
        print("✅ Connection string obtained")
        
        # Create IoT Hub client
        from iot.hub_client import HubClient
        hub_client = HubClient(conn_str)
        
        # Connect and send message
        if hub_client.connect():
            print("✅ Connected to IoT Hub")
            
            registration_message = {
                "deviceId": device_id,
                "messageType": "device_registration", 
                "status": "registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "registrationMethod": "direct_registration",
                "action": "register"
            }
            
            print(f"📝 Sending message: {json.dumps(registration_message, indent=2)}")
            
            success = hub_client.send_message(registration_message, device_id)
            if success:
                print("✅ Registration message sent to IoT Hub successfully")
                return True
            else:
                print("❌ Failed to send message to IoT Hub")
                return False
        else:
            print("❌ Failed to connect to IoT Hub")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("📡 Direct IoT Hub Registration Test")
    print("=" * 50)
    
    success = direct_iot_registration()
    
    if success:
        print("\n🎉 Success!")
        print("✅ Device 0ba242e597f5 registration sent to IoT Hub")
        print("📊 Message should now appear in Azure IoT Hub")
        print("🌐 Check https://iot.caleffionline.it/ for frontend updates")
    else:
        print("\n❌ Failed!")

if __name__ == "__main__":
    main()