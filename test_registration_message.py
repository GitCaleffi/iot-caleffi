#!/usr/bin/env python3
"""
Test sending registration message directly to IoT Hub
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def test_registration_message():
    """Send registration message directly to IoT Hub"""
    device_id = "pi-676c45f2"
    
    print(f"📡 Testing registration message for device: {device_id}")
    
    try:
        # Get device connection string
        from utils.dynamic_device_manager import device_manager
        conn_str = device_manager.get_device_connection_string(device_id)
        
        if not conn_str:
            print(f"❌ No connection string for device {device_id}")
            return False
        
        print(f"✅ Connection string obtained")
        
        # Create IoT Hub client
        from iot.hub_client import HubClient
        hub_client = HubClient(conn_str)
        
        # Connect to IoT Hub
        if not hub_client.connect():
            print(f"❌ Failed to connect to IoT Hub")
            return False
        
        print(f"✅ Connected to IoT Hub")
        
        # Create registration message
        registration_message = {
            "deviceId": device_id,
            "messageType": "device_registration",
            "action": "register",
            "status": "registered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "registrationMethod": "manual_test"
        }
        
        print(f"📝 Sending registration message:")
        print(json.dumps(registration_message, indent=2))
        
        # Send message
        success = hub_client.send_message(registration_message, device_id)
        
        if success:
            print(f"✅ Registration message sent successfully")
            return True
        else:
            print(f"❌ Failed to send registration message")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main test function"""
    print("📡 IoT Hub Registration Message Test")
    print("=" * 50)
    
    success = test_registration_message()
    
    if success:
        print("\n🎉 Test Complete!")
        print("✅ Registration message sent to IoT Hub")
        print("📊 Check Azure IoT Hub to see the message")
    else:
        print("\n❌ Test Failed!")
        print("Check the error messages above")

if __name__ == "__main__":
    main()