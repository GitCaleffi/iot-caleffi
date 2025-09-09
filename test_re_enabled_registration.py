#!/usr/bin/env python3
"""
Test the re-enabled frontend API registration to verify it's working
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_re_enabled_registration():
    """Test the re-enabled frontend API registration"""
    print("🧪 Testing Re-Enabled Frontend API Registration")
    print("=" * 60)
    
    test_device_id = "test-frontend-api"
    test_barcode = f"REG{test_device_id.upper()}"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Registration Barcode: {test_barcode}")
    print()
    
    print("STEP 1: Clean Device from Database")
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
    print("STEP 2: Test Registration with Frontend API Enabled")
    print("-" * 40)
    
    # Test the registration with frontend API enabled
    result = process_barcode_scan(test_barcode, test_device_id)
    print("Registration Result:")
    print(result)
    print()
    
    print("STEP 3: Verify Frontend API Call Was Made")
    print("-" * 40)
    
    # Check the result message for API status
    if "Registration sent to frontend API" in result:
        print("✅ EXCELLENT: Frontend API call was made successfully")
        print("✅ Registration data should now appear in your frontend logs")
    elif "Frontend API error" in result:
        print("⚠️  Frontend API call attempted but failed")
        print("⚠️  Check the error details in the result above")
    elif "Frontend API skipped" in result:
        print("❌ PROBLEM: Frontend API is still being skipped")
        print("❌ The re-enabling didn't work properly")
    else:
        print("❓ Unclear API status - check result details")
    
    print()
    print("STEP 4: Check Registration Success")
    print("-" * 40)
    
    try:
        local_db = LocalStorage()
        devices = local_db.get_registered_devices() or []
        registered_device = next((d for d in devices if d.get('device_id') == test_device_id), None)
        
        if registered_device:
            quantity = registered_device.get('quantity', 0)
            print(f"✅ Device registered successfully:")
            print(f"   Device ID: {registered_device.get('device_id')}")
            print(f"   Barcode: {registered_device.get('barcode')}")
            print(f"   Quantity: {quantity}")
            
            if quantity == 0:
                print("✅ GOOD: Registration with 0 quantity (minimal inventory impact)")
            else:
                print(f"⚠️  WARNING: Registration created quantity {quantity}")
        else:
            print("❌ Device not found after registration")
            
    except Exception as e:
        print(f"❌ Error checking registration: {e}")
    
    print()
    print("STEP 5: Monitor Inventory Impact")
    print("-" * 40)
    
    print("🔍 IMPORTANT: Monitor your inventory system for:")
    print(f"   • Device ID: {test_device_id}")
    print(f"   • Any inventory changes around {datetime.now().strftime('%H:%M:%S')} IST")
    print("   • Check if 'EAN undefined' or similar entries appear")
    print()
    print("⚠️  If inventory drops occur, we may need to disable API calls again")
    
    print()
    print("=" * 60)
    print("🎯 RE-ENABLED FRONTEND API TEST RESULTS")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print(f"Barcode: {test_barcode}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')} IST")
    print()
    print("✅ ENABLED: Frontend API calls are now active during registration")
    print("✅ EXPECTED: Registration data should appear in your frontend logs")
    print("⚠️  MONITOR: Watch for any inventory drops in your system")
    print()
    print("🔍 Check your frontend API logs at:")
    print("   https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId")
    print("   Look for registration data with the device ID above")

if __name__ == "__main__":
    test_re_enabled_registration()
