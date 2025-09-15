#!/usr/bin/env python3

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from iot.hub_client import HubClient
from utils.config import load_config

def test_iot_hub():
    """Test IoT Hub connection and send a test message"""
    print("🔍 Testing IoT Hub Connection...")
    
    # Load config
    config = load_config()
    devices = config.get("iot_hub", {}).get("devices", {})
    
    device_id = "pi-c1323007"
    
    if device_id not in devices:
        print(f"❌ Device {device_id} not found in config")
        return
    
    connection_string = devices[device_id].get("connection_string")
    
    if not connection_string:
        print(f"❌ No connection string for {device_id}")
        return
    
    print(f"✅ Found device: {device_id}")
    print(f"🔗 Connection string: {connection_string[:50]}...")
    
    # Test connection
    try:
        hub_client = HubClient(connection_string, device_id)
        
        if hub_client.connect():
            print("✅ Connected to IoT Hub successfully")
            
            # Send test message
            test_barcode = "1234567890123"
            success = hub_client.send_message(test_barcode, device_id)
            
            if success:
                print(f"✅ Test message sent successfully: {test_barcode}")
            else:
                print("❌ Failed to send test message")
        else:
            print("❌ Failed to connect to IoT Hub")
            
    except Exception as e:
        print(f"❌ IoT Hub error: {e}")

if __name__ == "__main__":
    test_iot_hub()
