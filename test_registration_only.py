#!/usr/bin/env python3
"""
Test that device registration ONLY registers device without quantity updates
This should prevent inventory drops during registration
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_registration_only():
    """Test that registration does NOT trigger quantity updates"""
    print("🧪 Testing Registration-Only Functionality")
    print("=" * 60)
    
    # Test parameters
    test_device_id = "448c5444b686"
    test_barcode = "9876543210987"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Test Barcode: {test_barcode}")
    print()
    
    # Clear any existing registration for clean test
    local_db = LocalStorage()
    
    print("STEP 1: Clean Registration Test")
    print("-" * 40)
    
    # Test device registration
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Registration Result:")
    print(result)
    print()
    
    print("STEP 2: Verify NO Quantity Updates During Registration")
    print("-" * 40)
    
    try:
        # Check registered device
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            quantity = registered_device.get('quantity', 0)
            print(f"✅ Device registered with quantity: {quantity}")
            if quantity == 0:
                print("✅ CORRECT: Registration started with 0 quantity")
            else:
                print(f"❌ WRONG: Registration should start with 0, got {quantity}")
        else:
            print("❌ Device not found in database")
            
    except Exception as e:
        print(f"❌ Error checking device: {e}")
    
    print()
    print("STEP 3: Check IoT Hub Messages")
    print("-" * 40)
    
    try:
        # Check unsent messages
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        registration_messages = []
        quantity_messages = []
        
        for msg in device_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                msg_type = msg_data.get('messageType', 'unknown')
                
                if msg_type == 'device_registration':
                    registration_messages.append(msg_data)
                elif msg_type == 'quantity_update':
                    quantity_messages.append(msg_data)
                    
            except json.JSONDecodeError:
                pass
        
        print(f"📝 Registration messages: {len(registration_messages)}")
        print(f"📝 Quantity update messages: {len(quantity_messages)}")
        
        if len(registration_messages) > 0 and len(quantity_messages) == 0:
            print("✅ CORRECT: Only registration messages, no quantity updates")
        elif len(quantity_messages) > 0:
            print("❌ WRONG: Found quantity update messages during registration!")
            for qty_msg in quantity_messages:
                print(f"   • Quantity: {qty_msg.get('previousQuantity')} → {qty_msg.get('newQuantity')}")
        else:
            print("⚠️  No messages found")
            
    except Exception as e:
        print(f"⚠️  Error checking messages: {e}")
    
    print()
    print("STEP 4: Test Actual Barcode Scan (Should Update Quantity)")
    print("-" * 40)
    
    # Now test a real barcode scan that should update quantity
    result2 = process_barcode_scan(test_barcode, test_device_id)
    print("Barcode Scan Result:")
    print(result2)
    print()
    
    print("STEP 5: Verify Quantity Updated After Real Scan")
    print("-" * 40)
    
    try:
        # Check updated quantity
        devices = local_db.get_registered_devices() or []
        updated_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if updated_device:
            new_quantity = updated_device.get('quantity', 0)
            print(f"✅ Device quantity after barcode scan: {new_quantity}")
            if new_quantity == 1:
                print("✅ CORRECT: Quantity updated to 1 after real scan")
            else:
                print(f"⚠️  Expected quantity 1, got {new_quantity}")
        else:
            print("❌ Device not found after scan")
            
    except Exception as e:
        print(f"❌ Error checking updated quantity: {e}")
    
    print()
    print("=" * 60)
    print("🎯 REGISTRATION-ONLY TEST SUMMARY")
    print("=" * 60)
    print("Expected behavior:")
    print("1. ✅ Registration should NOT trigger quantity updates")
    print("2. ✅ Registration should start with quantity = 0")
    print("3. ✅ Only 'device_registration' messages should be sent")
    print("4. ✅ NO 'quantity_update' messages during registration")
    print("5. ✅ Real barcode scans should update quantity normally")
    print()
    print("This prevents inventory drops during device registration!")

if __name__ == "__main__":
    test_registration_only()
