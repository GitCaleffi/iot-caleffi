#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage
import json

def debug_registration_flow():
    """Debug the registration flow to see where messages are failing"""
    
    print("🔍 **Registration Flow Debug**")
    print("=" * 50)
    
    # Test with a new device to see full registration flow
    test_device_id = "debug_reg_flow_001"
    
    print(f"📱 Testing registration flow with: {test_device_id}")
    print("-" * 30)
    
    # Check if device exists
    storage = LocalStorage()
    registered_devices = storage.get_registered_devices()
    existing_device = next((dev for dev in registered_devices if dev.get('device_id') == test_device_id), None)
    
    if existing_device:
        print(f"⚠️ Device already exists - this will test existing device flow")
        print(f"   Current quantity: {existing_device.get('quantity', 0)}")
    else:
        print(f"✅ Device is new - this will test new registration flow")
    
    print(f"\n🔍 Starting registration scan...")
    print(f"📱 Scanning device barcode: {test_device_id}")
    
    # Capture the registration result
    registration_result = process_barcode_scan(test_device_id, test_device_id)
    
    print(f"\n📋 **Registration Result:**")
    print(registration_result)
    
    # Check what was actually saved
    updated_devices = storage.get_registered_devices()
    final_device = next((dev for dev in updated_devices if dev.get('device_id') == test_device_id), None)
    
    print(f"\n🔍 **Device Status After Registration:**")
    if final_device:
        print(f"✅ Device found in local database")
        print(f"   • Device ID: {final_device.get('device_id')}")
        print(f"   • Quantity: {final_device.get('quantity', 0)}")
        print(f"   • Registered At: {final_device.get('registered_at')}")
        print(f"   • Connection String: {'✅ Present' if final_device.get('connection_string') else '❌ Missing'}")
    else:
        print(f"❌ Device NOT found in local database")
    
    # Check unsent messages
    print(f"\n📤 **Checking Unsent Messages:**")
    try:
        unsent_messages = storage.get_unsent_messages()
        device_messages = [msg for msg in unsent_messages if msg.get('device_id') == test_device_id]
        
        if device_messages:
            print(f"📨 Found {len(device_messages)} unsent messages for device:")
            for i, msg in enumerate(device_messages, 1):
                print(f"   {i}. Type: {msg.get('message_type', 'unknown')}")
                print(f"      Content: {msg.get('message_content', 'N/A')[:100]}...")
        else:
            print(f"📭 No unsent messages found for device {test_device_id}")
    except Exception as e:
        print(f"❌ Error checking unsent messages: {e}")
    
    print(f"\n🎯 **Key Points to Check:**")
    print(f"1. Frontend API Response: Check logs for 200/400 status")
    print(f"2. IoT Hub Message: Check if registration message was sent")
    print(f"3. Connection String: Verify device has valid connection string")
    print(f"4. Message Format: Ensure registration message has correct format")
    
    return final_device is not None

if __name__ == "__main__":
    try:
        debug_registration_flow()
        print(f"\n🏁 Registration flow debug completed!")
        print(f"📋 Check the logs above to identify where the flow is failing.")
    except Exception as e:
        print(f"\n❌ Debug failed with error: {e}")
        import traceback
        traceback.print_exc()
