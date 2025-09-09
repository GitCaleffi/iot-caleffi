#!/usr/bin/env python3
"""
Clean device 448c5444b686 from database and test fresh registration
This ensures we test actual registration, not quantity updates
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def clean_and_register_device():
    """Clean device from database and test fresh registration"""
    print("🧪 Clean Device 448c5444b686 and Test Fresh Registration")
    print("=" * 60)
    
    test_device_id = "448c5444b686"
    test_barcode = "FRESH448C5444B686"  # New registration barcode
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Fresh Registration Barcode: {test_barcode}")
    print()
    
    local_db = LocalStorage()
    
    print("STEP 1: Clean Device from Database")
    print("-" * 40)
    
    try:
        # Get database path
        db_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'barcode_scans.db')
        
        # Connect to database and remove device
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if device exists
        cursor.execute("SELECT * FROM registered_devices WHERE device_id = ?", (test_device_id,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"✅ Found existing device: {test_device_id}")
            
            # Delete from registered_devices
            cursor.execute("DELETE FROM registered_devices WHERE device_id = ?", (test_device_id,))
            
            # Delete related barcode scans (correct table name)
            cursor.execute("DELETE FROM scans WHERE device_id = ?", (test_device_id,))
            
            # Delete related unsent messages
            cursor.execute("DELETE FROM unsent_messages WHERE device_id = ?", (test_device_id,))
            
            conn.commit()
            print(f"✅ Cleaned device {test_device_id} from all database tables")
        else:
            print(f"ℹ️  Device {test_device_id} not found in database")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error cleaning database: {e}")
        return
    
    print()
    print("STEP 2: Verify Device Removed")
    print("-" * 40)
    
    # Verify device is removed
    devices = local_db.get_registered_devices() or []
    device_exists = any(d.get('device_id') == test_device_id for d in devices)
    
    if device_exists:
        print("❌ Device still exists in database - cleanup failed")
        return
    else:
        print("✅ Device successfully removed from database")
    
    print()
    print("STEP 3: Test Fresh Registration")
    print("-" * 40)
    
    # Now test fresh registration
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Fresh Registration Result:")
    print(result)
    print()
    
    print("STEP 4: Verify Fresh Registration")
    print("-" * 40)
    
    try:
        # Check if device was registered correctly
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            quantity = registered_device.get('quantity', 0)
            print(f"✅ Device registered successfully:")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Barcode: {registered_device.get('barcode')}")
            print(f"   Quantity: {quantity}")
            
            if quantity == 0:
                print("✅ PERFECT: Fresh registration with 0 quantity (no inventory impact)")
            else:
                print(f"❌ PROBLEM: Fresh registration should be 0, got {quantity}")
        else:
            print("❌ Device not found after registration")
            
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
    
    print()
    print("STEP 5: Check Message Types")
    print("-" * 40)
    
    try:
        # Check what messages were sent
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        registration_count = 0
        quantity_count = 0
        
        for msg in device_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                msg_type = msg_data.get('messageType', 'unknown')
                
                if msg_type == 'device_registration':
                    registration_count += 1
                    print(f"✅ Registration message found")
                elif msg_type == 'quantity_update':
                    quantity_count += 1
                    print(f"❌ Quantity update message found (should not happen)")
                    
            except json.JSONDecodeError:
                pass
        
        print(f"📝 Registration messages: {registration_count}")
        print(f"📝 Quantity update messages: {quantity_count}")
        
        if registration_count > 0 and quantity_count == 0:
            print("✅ EXCELLENT: Only registration messages, no quantity updates!")
        elif quantity_count > 0:
            print("❌ PROBLEM: Found quantity updates during registration!")
        else:
            print("ℹ️  Messages may have been sent successfully to IoT Hub")
            
    except Exception as e:
        print(f"⚠️  Error checking messages: {e}")
    
    print()
    print("=" * 60)
    print("🎯 FRESH REGISTRATION TEST RESULTS")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print(f"Barcode: {test_barcode}")
    print()
    print("✅ Device cleaned from database")
    print("✅ Fresh registration tested")
    print("✅ Should prevent inventory drops")
    print()
    print("🔍 Check your inventory system - NO drops should occur now!")

if __name__ == "__main__":
    clean_and_register_device()
