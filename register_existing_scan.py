#!/usr/bin/env python3
"""
Register device using existing scan data
"""

import sys
import os
from datetime import datetime

# Add paths for imports
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def register_existing_device():
    """Register device using existing scan data"""
    
    print("🔧 Registering Device with Existing Scan")
    print("=" * 45)
    
    # Device info from your logs
    device_id = "7079fa7ab32e"
    scanned_barcode = "17994ccfe145"
    test_barcode = "817994ccfe14"  # Required test barcode
    
    print(f"📱 Device ID: {device_id}")
    print(f"📦 Scanned Barcode: {scanned_barcode}")
    print(f"🧪 Test Barcode: {test_barcode}")
    
    try:
        # Import database
        from database.local_storage import LocalStorage
        storage = LocalStorage()
        
        # Save device registration
        print("\n💾 Saving device registration...")
        storage.save_device_registration(device_id, datetime.now())
        print("✅ Device registration saved")
        
        # Save test barcode scan (use the required test barcode)
        print("🧪 Saving test barcode scan...")
        storage.save_test_barcode_scan(test_barcode)
        print("✅ Test barcode scan saved")
        
        # Save the actual barcode scan
        print("📦 Saving barcode scan...")
        storage.save_scan(device_id, scanned_barcode, 1)
        print("✅ Barcode scan saved")
        
        # Check registration status
        print("\n📊 Checking registration status...")
        registration_status = storage.is_device_registered()
        
        print(f"Device ready: {registration_status.get('device_ready', False)}")
        print(f"Test barcode scanned: {registration_status.get('test_barcode_scanned', False)}")
        print(f"Available devices: {registration_status.get('available_device_count', 0)}")
        
        if registration_status.get('device_ready', False):
            print("\n✅ DEVICE SUCCESSFULLY REGISTERED!")
            print("🎉 You can now scan regular barcodes")
            
            # Show recent scans
            recent_scans = storage.get_recent_scans(5)
            if recent_scans:
                print("\n📝 Recent scans:")
                for scan in recent_scans:
                    print(f"  - {scan['barcode']} (Device: {scan['device_id']})")
        else:
            print("\n⚠️  Registration incomplete - check database entries")
            
        return True
        
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def show_registration_status():
    """Show current registration status"""
    
    print("\n📊 CURRENT REGISTRATION STATUS:")
    print("=" * 35)
    
    try:
        from database.local_storage import LocalStorage
        storage = LocalStorage()
        
        # Get registered devices
        devices = storage.get_registered_devices()
        print(f"📱 Registered devices: {len(devices)}")
        for device in devices:
            print(f"  - {device['device_id']} (registered: {device['timestamp']})")
        
        # Get test barcode
        test_scan = storage.get_test_barcode_scan()
        if test_scan:
            print(f"🧪 Test barcode: {test_scan['barcode']} (scanned: {test_scan['timestamp']})")
        else:
            print("🧪 Test barcode: Not scanned")
        
        # Get recent scans
        recent_scans = storage.get_recent_scans(3)
        print(f"📦 Recent scans: {len(recent_scans)}")
        for scan in recent_scans:
            print(f"  - {scan['barcode']} from {scan['device_id']}")
            
    except Exception as e:
        print(f"❌ Status check error: {e}")

if __name__ == "__main__":
    print("🚀 Device Registration Helper")
    print("=" * 35)
    
    # Show current status
    show_registration_status()
    
    # Register device
    success = register_existing_device()
    
    if success:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Restart keyboard scanner: python3 keyboard_scanner.py")
        print(f"2. Scan any barcode - device should be recognized")
        print(f"3. No more 'Device not verified' messages")
    else:
        print(f"\n🔧 TROUBLESHOOTING:")
        print(f"1. Check database permissions")
        print(f"2. Verify import paths")
        print(f"3. Run with: python3 register_existing_scan.py")
