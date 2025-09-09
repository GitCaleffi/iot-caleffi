#!/usr/bin/env python3
"""
Test device registration with specific device ID 448c5444b686
This will help identify why registration is still causing inventory drops
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_device_448c5444b686():
    """Test registration with device ID 448c5444b686"""
    print("🧪 Testing Device Registration: 448c5444b686")
    print("=" * 60)
    
    test_device_id = "448c5444b686"
    test_barcode = "REG448C5444B686"  # Clear registration barcode
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Registration Barcode: {test_barcode}")
    print()
    
    local_db = LocalStorage()
    
    # Check current device status
    devices = local_db.get_registered_devices() or []
    existing_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
    
    if existing_device:
        print("ℹ️  Device already exists in database:")
        print(f"   Current Quantity: {existing_device.get('quantity', 0)}")
        print(f"   Registered Barcode: {existing_device.get('barcode', 'Unknown')}")
        print("   Will test as quantity update instead of fresh registration")
    else:
        print("✅ Device not found - will test fresh registration")
    
    print()
    print("STEP 1: Process Registration/Scan")
    print("-" * 40)
    
    # Process the barcode scan
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Result:")
    print(result)
    print()
    
    print("STEP 2: Check Database After Processing")
    print("-" * 40)
    
    try:
        # Check device status after processing
        devices = local_db.get_registered_devices() or []
        updated_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if updated_device:
            new_quantity = updated_device.get('quantity', 0)
            print(f"✅ Device found in database:")
            print(f"   Device ID: {updated_device.get('device_id')}")
            print(f"   Barcode: {updated_device.get('barcode')}")
            print(f"   Quantity: {new_quantity}")
            
            if existing_device:
                old_quantity = existing_device.get('quantity', 0)
                if new_quantity > old_quantity:
                    print(f"📈 Quantity increased: {old_quantity} → {new_quantity}")
                elif new_quantity == old_quantity:
                    print(f"➡️  Quantity unchanged: {new_quantity}")
            else:
                if new_quantity == 0:
                    print("✅ GOOD: New device registered with 0 quantity")
                else:
                    print(f"⚠️  New device has quantity {new_quantity} (expected 0)")
        else:
            print("❌ Device not found in database after processing")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    print()
    print("STEP 3: Check Messages Sent")
    print("-" * 40)
    
    try:
        # Check what messages were generated
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        if device_messages:
            print(f"📝 Found {len(device_messages)} message(s):")
            for msg in device_messages[-2:]:  # Show last 2 messages
                try:
                    msg_data = json.loads(msg.get('message_data', '{}'))
                    msg_type = msg_data.get('messageType', 'unknown')
                    
                    if msg_type == 'device_registration':
                        print(f"   ✅ Registration message")
                        print(f"      Device: {msg_data.get('deviceId')}")
                        print(f"      Note: {msg_data.get('note', 'N/A')}")
                    elif msg_type == 'quantity_update':
                        print(f"   📊 Quantity update message")
                        print(f"      Barcode: {msg_data.get('scannedBarcode')}")
                        print(f"      Quantity: {msg_data.get('previousQuantity')} → {msg_data.get('newQuantity')}")
                    else:
                        print(f"   ❓ Unknown message type: {msg_type}")
                        
                except json.JSONDecodeError:
                    print(f"   ⚠️  Could not parse message")
        else:
            print("ℹ️  No unsent messages (may have been sent successfully)")
            
    except Exception as e:
        print(f"⚠️  Error checking messages: {e}")
    
    print()
    print("=" * 60)
    print("🎯 ANALYSIS")
    print("=" * 60)
    
    if existing_device:
        print("📋 This was an EXISTING device - quantity update expected")
        print("   If inventory dropped, the issue is in quantity update logic")
    else:
        print("🆕 This was a NEW device - registration expected")
        print("   If inventory dropped, the issue is in registration logic")
    
    print()
    print("🔍 Check your inventory system to see if drops occurred")
    print("🔍 Compare the timestamp with inventory drop notifications")

if __name__ == "__main__":
    test_device_448c5444b686()
