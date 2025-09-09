#!/usr/bin/env python3
"""
Send IoT Hub registration message for device 0ba242e597f5
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def send_iot_registration():
    """Send registration message to IoT Hub for device 0ba242e597f5"""
    device_id = "0ba242e597f5"
    
    print(f"📡 Sending IoT Hub registration for: {device_id}")
    
    try:
        # Get connection string
        from utils.dynamic_registration_service import get_dynamic_registration_service
        reg_service = get_dynamic_registration_service()
        
        if not reg_service:
            print("❌ Registration service not available")
            return False
        
        conn_str = reg_service.get_device_connection_string(device_id)
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
                "registrationMethod": "manual_registration"
            }
            
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
    print("📡 IoT Hub Registration Message Test")
    print("=" * 50)
    
    success = send_iot_registration()
    
    if success:
        print("\n🎉 Success!")
        print("✅ Registration message sent to IoT Hub")
        print("📊 Check Azure IoT Hub for the message")
    else:
        print("\n❌ Failed!")

if __name__ == "__main__":
    main()