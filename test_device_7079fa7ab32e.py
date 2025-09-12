#!/usr/bin/env python3
"""
Simple test script to register device ID 7079fa7ab32e and test barcode flows
"""

import sys
import os
import json
import sqlite3
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_device_registration():
    """Test device registration for device ID 7079fa7ab32e"""
    print("=" * 60)
    print("TESTING DEVICE REGISTRATION FOR: 7079fa7ab32e")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"
    test_barcode = "1234567890123"  # Test EAN-13 barcode
    
    try:
        # Import required modules
        from database.local_storage import LocalStorage
        from api.api_client import ApiClient
        from iot.hub_client import HubClient
        
        # Initialize components
        storage = LocalStorage()
        api_client = ApiClient()
        hub_client = HubClient()
        
        print(f"✅ Successfully imported all required modules")
        
        # Test 1: Check if device already registered
        print(f"\n1. Checking if device {device_id} is already registered...")
        registered_devices = storage.get_registered_devices()
        print(f"   Currently registered devices: {len(registered_devices)}")
        
        device_exists = any(device['device_id'] == device_id for device in registered_devices)
        if device_exists:
            print(f"   ⚠️  Device {device_id} is already registered")
            for device in registered_devices:
                if device['device_id'] == device_id:
                    print(f"   Registration date: {device.get('registration_date', 'Unknown')}")
        else:
            print(f"   ✅ Device {device_id} is not yet registered - proceeding with registration")
        
        # Test 2: Register device with API
        print(f"\n2. Testing API registration for device {device_id}...")
        try:
            api_result = api_client.confirm_registration(device_id)
            if api_result and api_result.get('success'):
                print(f"   ✅ API registration successful")
                print(f"   Response: {api_result}")
            else:
                print(f"   ⚠️  API registration failed or returned error")
                print(f"   Response: {api_result}")
        except Exception as e:
            print(f"   ❌ API registration error: {str(e)}")
        
        # Test 3: Register device locally
        print(f"\n3. Registering device {device_id} locally...")
        try:
            if not device_exists:
                storage.save_device_registration(device_id, test_barcode)
                print(f"   ✅ Device registered locally with test barcode: {test_barcode}")
            else:
                print(f"   ⚠️  Device already exists locally, skipping local registration")
        except Exception as e:
            print(f"   ❌ Local registration error: {str(e)}")
        
        # Test 4: Test IoT Hub connection and device registration
        print(f"\n4. Testing IoT Hub device registration...")
        try:
            # Try to register device with IoT Hub
            from iot.dynamic_registration_service import get_dynamic_registration_service
            registration_service = get_dynamic_registration_service()
            
            if registration_service:
                connection_string = registration_service.register_device(device_id)
                if connection_string:
                    print(f"   ✅ IoT Hub device registration successful")
                    print(f"   Connection string obtained (length: {len(connection_string)})")
                else:
                    print(f"   ⚠️  IoT Hub registration returned empty connection string")
            else:
                print(f"   ❌ Could not initialize dynamic registration service")
                
        except Exception as e:
            print(f"   ❌ IoT Hub registration error: {str(e)}")
        
        # Test 5: Send test message to IoT Hub
        print(f"\n5. Testing IoT Hub message sending...")
        try:
            test_message = {
                "deviceId": device_id,
                "messageType": "device_registration",
                "action": "register",
                "scannedBarcode": test_barcode,
                "timestamp": datetime.now().isoformat(),
                "status": "registered"
            }
            
            result = hub_client.send_message(json.dumps(test_message), device_id)
            if result:
                print(f"   ✅ Test registration message sent to IoT Hub")
                print(f"   Message ID: {result}")
            else:
                print(f"   ⚠️  IoT Hub message sending failed")
                
        except Exception as e:
            print(f"   ❌ IoT Hub message error: {str(e)}")
        
        print(f"\n" + "=" * 60)
        print("DEVICE REGISTRATION TEST COMPLETED")
        print("=" * 60)
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("Please ensure all required modules are available")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

def test_barcode_scanning():
    """Test barcode scanning flow with registered device"""
    print("\n" + "=" * 60)
    print("TESTING BARCODE SCANNING FLOW")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"
    test_barcodes = [
        "1234567890123",  # EAN-13
        "5901234123457",  # Another EAN-13
        "8978456598745"   # Another test barcode
    ]
    
    try:
        from database.local_storage import LocalStorage
        from api.api_client import ApiClient
        from iot.hub_client import HubClient
        
        storage = LocalStorage()
        api_client = ApiClient()
        hub_client = HubClient()
        
        for i, barcode in enumerate(test_barcodes, 1):
            print(f"\n{i}. Testing barcode scan: {barcode}")
            
            # Save scan locally
            try:
                storage.save_barcode_scan(barcode, device_id)
                print(f"   ✅ Barcode saved locally")
            except Exception as e:
                print(f"   ❌ Local save error: {str(e)}")
            
            # Send to API
            try:
                api_result = api_client.send_barcode_scan(device_id, barcode, 1)
                if api_result and api_result.get('success'):
                    print(f"   ✅ Barcode sent to API successfully")
                else:
                    print(f"   ⚠️  API send failed: {api_result}")
            except Exception as e:
                print(f"   ❌ API send error: {str(e)}")
            
            # Send to IoT Hub
            try:
                quantity_message = {
                    "deviceId": device_id,
                    "messageType": "quantity_update",
                    "scannedBarcode": barcode,
                    "quantity": 1,
                    "timestamp": datetime.now().isoformat()
                }
                
                result = hub_client.send_message(json.dumps(quantity_message), device_id)
                if result:
                    print(f"   ✅ Quantity message sent to IoT Hub")
                    print(f"   Message ID: {result}")
                else:
                    print(f"   ⚠️  IoT Hub send failed")
            except Exception as e:
                print(f"   ❌ IoT Hub send error: {str(e)}")
        
        print(f"\n" + "=" * 60)
        print("BARCODE SCANNING TEST COMPLETED")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Barcode scanning test error: {str(e)}")

def check_database_status():
    """Check current database status"""
    print("\n" + "=" * 60)
    print("DATABASE STATUS CHECK")
    print("=" * 60)
    
    try:
        from database.local_storage import LocalStorage
        storage = LocalStorage()
        
        # Check registered devices
        devices = storage.get_registered_devices()
        print(f"Registered devices: {len(devices)}")
        for device in devices:
            print(f"  - {device['device_id']} (registered: {device.get('registration_date', 'Unknown')})")
        
        # Check barcode scans
        scans = storage.get_all_scans()
        print(f"\nTotal barcode scans: {len(scans)}")
        
        # Check scans for our specific device
        device_scans = [scan for scan in scans if scan.get('device_id') == '7079fa7ab32e']
        print(f"Scans for device 7079fa7ab32e: {len(device_scans)}")
        
        for scan in device_scans[-5:]:  # Show last 5 scans
            print(f"  - {scan['barcode']} at {scan.get('timestamp', 'Unknown')}")
            
    except Exception as e:
        print(f"❌ Database check error: {str(e)}")

if __name__ == "__main__":
    print("USB Scanner Registration Testing")
    print("Device ID: 7079fa7ab32e")
    print("=" * 60)
    
    # Run tests
    test_device_registration()
    test_barcode_scanning()
    check_database_status()
    
    print(f"\n🎯 All tests completed for device 7079fa7ab32e")
