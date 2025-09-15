#!/usr/bin/env python3
# Test IoT Hub device connection

import os
import sys
from azure.iot.device import IoTHubDeviceClient, Message
import json

def test_device_connection(device_connection_string):
    try:
        print("🔌 Testing IoT Hub device connection...")
        client = IoTHubDeviceClient.create_from_connection_string(device_connection_string)
        print("✅ Successfully connected to IoT Hub as device")
        
        # Send a test message
        message = Message(json.dumps({"test": "device_connection_test"}))
        message.content_encoding = "utf-8"
        message.content_type = "application/json"
        
        print("📤 Sending test message...")
        client.send_message(message)
        print("✅ Test message sent successfully")
        
        return True
    except Exception as e:
        print(f"❌ Connection test failed: {str(e)}")
        return False
    finally:
        if 'client' in locals():
            client.shutdown()

if __name__ == "__main__":
    # Try with a sample device connection string
    test_connection_string = "HostName=CaleffiIoT.azure-devices.net;DeviceId=test-device;SharedAccessKey=YOUR_DEVICE_KEY"
    
    if len(sys.argv) > 1:
        test_connection_string = sys.argv[1]
    
    print(f"Using connection string: {test_connection_string[:50]}...")
    test_device_connection(test_connection_string)
