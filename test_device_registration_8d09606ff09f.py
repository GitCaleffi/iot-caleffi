#!/usr/bin/env python3
"""
Test device registration functionality with specific device ID: 8d09606ff09f
Tests the registration process from barcode_scanner_app.py
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_device_registration():
    """Test device registration with specific device ID"""
    print("🧪 Testing Device Registration Functionality")
    print("=" * 60)
    
    # Test parameters
    test_device_id = "8d09606ff09f"
    test_barcode = "1234567890123"  # Test barcode for registration
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Test Barcode: {test_barcode}")
    print()
    
    # Clear any existing registration for clean test
    local_db = LocalStorage()
    try:
        # Check if device already exists
        devices = local_db.get_registered_devices() or []
        existing_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if existing_device:
            print(f"⚠️  Device {test_device_id} already registered")
            print(f"   Registration time: {existing_device.get('registration_time', 'Unknown')}")
            print(f"   Barcode: {existing_device.get('barcode', 'Unknown')}")
            print()
            print("🔄 Testing with already registered device...")
        else:
            print(f"✅ Device {test_device_id} not found - will test fresh registration")
            
    except Exception as e:
        print(f"⚠️  Error checking existing devices: {e}")
    
    print()
    print("STEP 1: Device Registration Test")
    print("-" * 40)
    
    # Test device registration
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Registration Result:")
    print(result)
    print()
    
    print("STEP 2: Verify Registration in Database")
    print("-" * 40)
    
    try:
        # Check if device was registered
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            print("✅ Device successfully registered in local database:")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Barcode: {registered_device.get('barcode')}")
            print(f"   Registration Time: {registered_device.get('registration_time')}")
            print(f"   Quantity: {registered_device.get('quantity', 0)}")
        else:
            print("❌ Device not found in local database")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    print()
    print("STEP 3: Check Barcode Scans")
    print("-" * 40)
    
    try:
        # Check barcode scans
        scans = local_db.get_barcode_scans() or []
        device_scans = [s for s in scans if s.get('device_id') == test_device_id]
        
        if device_scans:
            print(f"✅ Found {len(device_scans)} barcode scan(s) for device {test_device_id}:")
            for scan in device_scans[-3:]:  # Show last 3 scans
                print(f"   • Barcode: {scan.get('barcode')} at {scan.get('scan_time')}")
        else:
            print(f"ℹ️  No barcode scans found for device {test_device_id}")
            
    except Exception as e:
        print(f"⚠️  Error checking barcode scans: {e}")
    
    print()
    print("STEP 4: Test Second Scan (Quantity Update)")
    print("-" * 40)
    
    # Test quantity update with second scan
    result2 = process_barcode_scan(test_barcode, test_device_id)
    print("Second Scan Result:")
    print(result2)
    print()
    
    print("STEP 5: Verify Updated Quantity")
    print("-" * 40)
    
    try:
        # Check updated quantity
        devices = local_db.get_registered_devices() or []
        updated_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if updated_device:
            quantity = updated_device.get('quantity', 0)
            print(f"✅ Device quantity after second scan: {quantity}")
            if quantity > 1:
                print("✅ Quantity update working correctly")
            else:
                print("⚠️  Quantity may not have updated properly")
        else:
            print("❌ Device not found after second scan")
            
    except Exception as e:
        print(f"❌ Error checking updated quantity: {e}")
    
    print()
    print("STEP 6: Check IoT Hub Messages")
    print("-" * 40)
    
    try:
        # Check unsent messages (if any)
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = [m for m in unsent_messages if test_device_id in m.get('message_data', '')]
        
        if device_messages:
            print(f"📝 Found {len(device_messages)} IoT Hub message(s) for device:")
            for msg in device_messages[-2:]:  # Show last 2 messages
                try:
                    msg_data = json.loads(msg.get('message_data', '{}'))
                    msg_type = msg_data.get('messageType', 'unknown')
                    print(f"   • Type: {msg_type}")
                    if msg_type == 'device_registration':
                        print(f"     Device ID: {msg_data.get('deviceId')}")
                    elif msg_type == 'quantity_update':
                        print(f"     Barcode: {msg_data.get('scannedBarcode')}")
                        print(f"     Quantity: {msg_data.get('previousQuantity')} → {msg_data.get('newQuantity')}")
                except json.JSONDecodeError:
                    print(f"   • Raw message: {msg.get('message_data', '')[:100]}...")
        else:
            print("ℹ️  No unsent IoT Hub messages found (messages may have been sent successfully)")
            
    except Exception as e:
        print(f"⚠️  Error checking IoT Hub messages: {e}")
    
    print()
    print("=" * 60)
    print("🎯 REGISTRATION TEST SUMMARY")
    print("=" * 60)
    print(f"Device ID: {test_device_id}")
    print(f"Test Barcode: {test_barcode}")
    print()
    print("Expected behavior:")
    print("1. ✅ First scan should register device")
    print("2. ✅ Device should be saved in local database")
    print("3. ✅ Registration message should be sent to IoT Hub")
    print("4. ✅ Second scan should update quantity")
    print("5. ✅ Quantity update message should be sent to IoT Hub")
    print()
    print("🔍 Check IoT Hub portal for messages from device:", test_device_id)

if __name__ == "__main__":
    test_device_registration()
