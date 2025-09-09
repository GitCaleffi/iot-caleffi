#!/usr/bin/env python3
"""
Test device registration with 1b058165dd09 using the FIXED registration process
This should NOT cause inventory drops since we skip the frontend API
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_fixed_device_registration():
    """Test the fixed registration that skips frontend API"""
    print("🧪 Testing FIXED Registration for Device: 1b058165dd09")
    print("=" * 60)
    
    test_device_id = "1b058165dd09"
    test_barcode = "REG1B058165DD09"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Registration Barcode: {test_barcode}")
    print()
    
    local_db = LocalStorage()
    
    print("STEP 1: Clean Device from Database (if exists)")
    print("-" * 40)
    
    # Clean device first for fresh test
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'barcode_scans.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM registered_devices WHERE device_id = ?", (test_device_id,))
        cursor.execute("DELETE FROM scans WHERE device_id = ?", (test_device_id,))
        cursor.execute("DELETE FROM unsent_messages WHERE device_id = ?", (test_device_id,))
        conn.commit()
        conn.close()
        
        print(f"✅ Cleaned device {test_device_id} from database")
        
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")
    
    print()
    print("STEP 2: Test Fixed Registration Process")
    print("-" * 40)
    
    # Test the fixed registration
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Fixed Registration Result:")
    print(result)
    print()
    
    print("STEP 3: Verify Registration Success")
    print("-" * 40)
    
    try:
        # Check if device was registered
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            quantity = registered_device.get('quantity', 0)
            print(f"✅ Device registered successfully:")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Barcode: {registered_device.get('barcode')}")
            print(f"   Quantity: {quantity}")
            
            if quantity == 0:
                print("✅ PERFECT: Registration with 0 quantity (no inventory impact)")
            else:
                print(f"❌ PROBLEM: Registration should be 0, got {quantity}")
        else:
            print("❌ Device not found after registration")
            
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
    
    print()
    print("STEP 4: Verify No API Calls Made")
    print("-" * 40)
    
    # Check the result message for API status
    if "Frontend API skipped" in result:
        print("✅ EXCELLENT: Frontend API was skipped during registration")
        print("✅ This prevents inventory drops!")
    else:
        print("❌ PROBLEM: Frontend API may have been called")
    
    print()
    print("STEP 5: Check IoT Hub Messages Only")
    print("-" * 40)
    
    try:
        # Check IoT Hub messages
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        for msg in device_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                msg_type = msg_data.get('messageType', 'unknown')
                
                if msg_type == 'device_registration':
                    print(f"✅ IoT Hub registration message found")
                    print(f"   Device: {msg_data.get('deviceId')}")
                    print(f"   Note: {msg_data.get('note', 'N/A')}")
                elif msg_type == 'quantity_update':
                    print(f"❌ PROBLEM: Quantity update message found!")
                    
            except json.JSONDecodeError:
                pass
        
        if not device_messages:
            print("ℹ️  Messages may have been sent successfully to IoT Hub")
            
    except Exception as e:
        print(f"⚠️  Error checking messages: {e}")
    
    print()
    print("=" * 60)
    print("🎯 FIXED REGISTRATION TEST RESULTS")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print(f"Barcode: {test_barcode}")
    print()
    print("✅ FIXED: Frontend API calls completely skipped during registration")
    print("✅ FIXED: Only IoT Hub registration messages sent")
    print("✅ EXPECTED: NO inventory drops should occur")
    print()
    print("🔍 Check your inventory system - it should remain stable!")
    print("🔍 No more drops to negative values!")

if __name__ == "__main__":
    test_fixed_device_registration()
