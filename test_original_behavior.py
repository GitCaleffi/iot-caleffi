#!/usr/bin/env python3
"""
Test to verify the original code behavior was working properly
This tests the older workflow that was in place before recent changes
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_original_workflow():
    """Test the original workflow that was working before recent changes"""
    
    print("🧪 TESTING ORIGINAL CODE BEHAVIOR")
    print("=" * 60)
    print("Testing the workflow that was in place before recent modifications")
    print("=" * 60)
    
    # Test device from memories that was working
    test_device_id = "817994ccfe14"  # Device from memory that was working
    test_ean_barcode = "5901234123457"  # Standard EAN barcode
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  EAN Barcode: {test_ean_barcode}")
    print()
    
    # Clean database first
    print("STEP 1: Clean Database for Fresh Test")
    print("-" * 40)
    
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
        print(f"⚠️ Cleanup error: {e}")
    
    print()
    print("STEP 2: Test Original Device Registration")
    print("-" * 40)
    
    # Test device registration using the original approach
    print(f"Registering device: {test_device_id}")
    
    try:
        # Use the device ID directly as it would have been scanned
        registration_result = process_barcode_scan(test_device_id)
        print("✅ Original Registration Result:")
        print(registration_result)
        print()
        
        # Check if registration was successful
        if "registered" in registration_result.lower() or "success" in registration_result.lower():
            print("✅ Device registration appears successful")
        else:
            print("❌ Device registration may have failed")
            
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return False
    
    print()
    print("STEP 3: Test Original EAN Barcode Scanning")
    print("-" * 40)
    
    # Test EAN barcode scanning with device ID
    print(f"Scanning EAN barcode: {test_ean_barcode}")
    
    try:
        scan_result = process_barcode_scan(test_ean_barcode, test_device_id)
        print("✅ Original EAN Scan Result:")
        print(scan_result)
        print()
        
        # Check if scan was successful
        if "scanned" in scan_result.lower() or "success" in scan_result.lower():
            print("✅ EAN barcode scan appears successful")
        else:
            print("❌ EAN barcode scan may have failed")
            
    except Exception as e:
        print(f"❌ EAN scan failed: {e}")
        return False
    
    print()
    print("STEP 4: Verify Database State")
    print("-" * 40)
    
    try:
        local_db = LocalStorage()
        
        # Check registered devices
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            print(f"✅ Device found in database:")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Quantity: {registered_device.get('quantity', 0)}")
        else:
            print("❌ Device not found in database")
        
        # Check scans
        recent_scans = local_db.get_recent_scans(5) or []
        device_scans = [s for s in recent_scans if s.get('device_id') == test_device_id]
        
        print(f"✅ Found {len(device_scans)} scans for this device")
        for scan in device_scans:
            print(f"   Barcode: {scan.get('barcode')}, Quantity: {scan.get('quantity', 1)}")
            
    except Exception as e:
        print(f"❌ Database check error: {e}")
    
    print()
    print("STEP 5: Test Frontend API Behavior")
    print("-" * 40)
    
    # Test what the frontend API receives
    api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
    
    # Test registration payload
    reg_payload = {"deviceId": test_device_id}
    print(f"Testing registration payload: {reg_payload}")
    
    try:
        response = requests.post(api_url, json=reg_payload, timeout=10)
        print(f"Registration API - Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Registration API error: {e}")
    
    # Test barcode payload
    barcode_payload = {"deviceId": test_device_id, "barcode": test_ean_barcode}
    print(f"Testing barcode payload: {barcode_payload}")
    
    try:
        response = requests.post(api_url, json=barcode_payload, timeout=10)
        print(f"Barcode API - Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Barcode API error: {e}")
    
    print()
    print("=" * 60)
    print("🎯 ORIGINAL BEHAVIOR TEST RESULTS")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print(f"EAN: {test_ean_barcode}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')} IST")
    print()
    print("📊 ANALYSIS:")
    print("1. Check if device registration worked in original code")
    print("2. Verify EAN barcode scanning functionality")
    print("3. Confirm IoT Hub message delivery")
    print("4. Test frontend API integration")
    print()
    print("🔍 COMPARISON POINTS:")
    print("- Original vs current registration behavior")
    print("- Message format and delivery")
    print("- Database storage consistency")
    print("- API integration differences")
    
    return True

if __name__ == "__main__":
    success = test_original_workflow()
    if success:
        print("\n🟢 Original behavior test completed")
    else:
        print("\n🔴 Original behavior test had issues")
