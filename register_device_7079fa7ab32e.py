#!/usr/bin/env python3
"""
Register device ID 7079fa7ab32e using the existing barcode scanner system
"""

import sys
import os
import json
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def register_device_7079fa7ab32e():
    """Register device 7079fa7ab32e using existing system functions"""
    device_id = "7079fa7ab32e"
    test_barcode = "1234567890123"  # Test EAN-13 barcode
    
    print("=" * 60)
    print(f"REGISTERING DEVICE: {device_id}")
    print("=" * 60)
    
    try:
        # Import the main barcode scanner functions
        from barcode_scanner_app import confirm_registration, process_barcode_scan
        from database.local_storage import LocalStorage
        
        storage = LocalStorage()
        
        # Check if device already registered
        print(f"1. Checking if device {device_id} is already registered...")
        registered_devices = storage.get_registered_devices()
        device_exists = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_exists:
            print(f"   ⚠️  Device {device_id} is already registered")
            for device in registered_devices:
                if device['device_id'] == device_id:
                    print(f"   Registration date: {device.get('registration_date', 'Unknown')}")
        else:
            print(f"   ✅ Device {device_id} not found - proceeding with registration")
            
            # Register the device using the existing system
            print(f"\n2. Registering device {device_id} with test barcode {test_barcode}...")
            
            try:
                # Use the existing confirm_registration function
                result = confirm_registration(test_barcode, device_id)
                print(f"   Registration result: {result}")
                
                if "successfully" in str(result).lower():
                    print(f"   ✅ Device {device_id} registered successfully!")
                else:
                    print(f"   ⚠️  Registration may have issues: {result}")
                    
            except Exception as e:
                print(f"   ❌ Registration error: {str(e)}")
        
        # Test barcode scanning with the registered device
        print(f"\n3. Testing barcode scan with registered device...")
        test_scan_barcode = "5901234123457"  # Different test barcode
        
        try:
            scan_result = process_barcode_scan(test_scan_barcode, device_id)
            print(f"   Scan result: {scan_result}")
            
            if "successfully" in str(scan_result).lower() or "sent" in str(scan_result).lower():
                print(f"   ✅ Barcode scan processed successfully!")
            else:
                print(f"   ⚠️  Scan processing may have issues: {scan_result}")
                
        except Exception as e:
            print(f"   ❌ Scan processing error: {str(e)}")
        
        # Check final status
        print(f"\n4. Final status check...")
        updated_devices = storage.get_registered_devices()
        device_now_exists = any(device['device_id'] == device_id for device in updated_devices)
        
        if device_now_exists:
            print(f"   ✅ Device {device_id} is now registered in local database")
            
            # Show device details
            for device in updated_devices:
                if device['device_id'] == device_id:
                    print(f"   Device details: {device}")
        else:
            print(f"   ❌ Device {device_id} not found in database after registration")
        
        print(f"\n" + "=" * 60)
        print("DEVICE REGISTRATION COMPLETED")
        print("=" * 60)
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("Make sure you're running this from the correct directory")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

def check_device_status():
    """Check the current status of device 7079fa7ab32e"""
    device_id = "7079fa7ab32e"
    
    print(f"\n" + "=" * 60)
    print(f"DEVICE STATUS CHECK: {device_id}")
    print("=" * 60)
    
    try:
        from database.local_storage import LocalStorage
        storage = LocalStorage()
        
        # Check if device is registered
        devices = storage.get_registered_devices()
        device_found = False
        
        for device in devices:
            if device['device_id'] == device_id:
                device_found = True
                print(f"✅ Device {device_id} is registered")
                print(f"   Registration details: {device}")
                break
        
        if not device_found:
            print(f"❌ Device {device_id} is not registered")
        
        # Check barcode scans for this device
        try:
            # Try to get scans for this device
            conn = storage.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM barcode_scans WHERE device_id = ? ORDER BY timestamp DESC LIMIT 5", (device_id,))
            scans = cursor.fetchall()
            conn.close()
            
            if scans:
                print(f"\n📊 Recent barcode scans for {device_id}:")
                for scan in scans:
                    print(f"   - Barcode: {scan[1]}, Timestamp: {scan[3]}")
            else:
                print(f"\n📊 No barcode scans found for {device_id}")
                
        except Exception as e:
            print(f"   ⚠️  Could not check barcode scans: {str(e)}")
        
    except Exception as e:
        print(f"❌ Status check error: {str(e)}")

if __name__ == "__main__":
    print("USB Scanner Device Registration")
    print("Target Device ID: 7079fa7ab32e")
    
    # Register the device
    register_device_7079fa7ab32e()
    
    # Check status
    check_device_status()
    
    print(f"\n🎯 Registration process completed for device 7079fa7ab32e")
