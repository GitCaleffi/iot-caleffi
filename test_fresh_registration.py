#!/usr/bin/env python3
"""
Test fresh device registration with completely new device ID
This ensures we test actual registration, not quantity updates
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_fresh_registration():
    """Test registration with a completely new device ID"""
    print("🧪 Testing Fresh Device Registration (No Quantity Updates)")
    print("=" * 60)
    
    # Generate unique device ID to ensure fresh registration
    unique_id = str(uuid.uuid4())[:8]
    test_device_id = f"fresh-device-{unique_id}"
    test_barcode = f"REG{unique_id}"
    
    print(f"📱 New Device ID: {test_device_id}")
    print(f"🏷️  Registration Barcode: {test_barcode}")
    print()
    
    local_db = LocalStorage()
    
    # Verify device doesn't exist
    devices = local_db.get_registered_devices() or []
    existing = any(d.get('device_id') == test_device_id for d in devices)
    
    if existing:
        print("❌ Device already exists - test invalid")
        return
    else:
        print("✅ Confirmed: Device does not exist - will test fresh registration")
    
    print()
    print("STEP 1: Fresh Device Registration")
    print("-" * 40)
    
    # Test fresh device registration
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Registration Result:")
    print(result)
    print()
    
    print("STEP 2: Verify Registration (No Quantity Updates)")
    print("-" * 40)
    
    try:
        # Check if device was registered correctly
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            quantity = registered_device.get('quantity', 0)
            print(f"✅ Device registered successfully")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Barcode: {registered_device.get('barcode')}")
            print(f"   Quantity: {quantity}")
            
            if quantity == 0:
                print("✅ CORRECT: Registration started with 0 quantity (no inventory impact)")
            else:
                print(f"❌ WRONG: Registration should start with 0, got {quantity}")
        else:
            print("❌ Device not found in database after registration")
            
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
    
    print()
    print("STEP 3: Check Message Types Sent")
    print("-" * 40)
    
    try:
        # Check what messages were sent
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        registration_count = 0
        quantity_count = 0
        
        print(f"📝 Found {len(device_messages)} message(s) for this device:")
        
        for msg in device_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                msg_type = msg_data.get('messageType', 'unknown')
                
                if msg_type == 'device_registration':
                    registration_count += 1
                    print(f"   ✅ Registration message: {msg_data.get('deviceId')}")
                    print(f"      Note: {msg_data.get('note', 'N/A')}")
                elif msg_type == 'quantity_update':
                    quantity_count += 1
                    print(f"   ❌ Quantity update: {msg_data.get('previousQuantity')} → {msg_data.get('newQuantity')}")
                else:
                    print(f"   ⚠️  Unknown message type: {msg_type}")
                    
            except json.JSONDecodeError:
                print(f"   ⚠️  Could not parse message")
        
        print()
        if registration_count > 0 and quantity_count == 0:
            print("✅ PERFECT: Only registration messages sent, no quantity updates!")
        elif quantity_count > 0:
            print("❌ PROBLEM: Quantity update messages found during registration!")
        else:
            print("⚠️  No messages found (may have been sent successfully to IoT Hub)")
            
    except Exception as e:
        print(f"⚠️  Error checking messages: {e}")
    
    print()
    print("=" * 60)
    print("🎯 FRESH REGISTRATION TEST RESULTS")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print(f"Barcode: {test_barcode}")
    print()
    print("✅ Expected: Registration only, no quantity updates")
    print("✅ Expected: Quantity starts at 0")
    print("✅ Expected: No inventory impact during registration")
    print()
    print("This should prevent the inventory drop issue!")

if __name__ == "__main__":
    test_fresh_registration()
