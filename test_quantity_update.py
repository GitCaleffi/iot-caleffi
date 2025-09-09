#!/usr/bin/env python3
"""
Test script to verify quantity updates work correctly for real-time barcode scanning
Tests with barcode 1122365214528 and device ID 1b058165dd09
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

import json
from datetime import datetime, timezone
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_quantity_update():
    """Test quantity update functionality"""
    
    # Test parameters from user
    test_barcode = "1122365214528"
    test_device_id = "1b058165dd09"
    
    print("🧪 TESTING QUANTITY UPDATE FUNCTIONALITY")
    print(f"📊 Test Barcode: {test_barcode}")
    print(f"🔧 Test Device ID: {test_device_id}")
    print("=" * 60)
    
    try:
        # Import required modules
        from barcode_scanner_app import process_barcode_scan
        from database.local_storage import LocalStorage
        
        # Initialize local storage
        local_db = LocalStorage()
        
        # Step 1: Check if device exists (should be registered first)
        print("📋 Step 1: Checking device registration status...")
        registered_devices = local_db.get_registered_devices()
        device_exists = any(device['device_id'] == test_device_id for device in registered_devices)
        
        if not device_exists:
            print(f"⚠️  Device {test_device_id} not found in database")
            print("🔧 Registering device first...")
            
            # Register device first (this should NOT send quantity update)
            result = process_barcode_scan(test_barcode, test_device_id)
            print("📝 Registration Result:")
            print(result)
            print("-" * 40)
            
            # Wait a moment
            import time
            time.sleep(2)
        else:
            print(f"✅ Device {test_device_id} already registered")
        
        # Step 2: Now scan the same barcode again (this SHOULD send quantity update)
        print("📊 Step 2: Scanning barcode for quantity update...")
        print(f"🔍 Scanning barcode: {test_barcode}")
        
        result = process_barcode_scan(test_barcode, test_device_id)
        print("📝 Quantity Update Result:")
        print(result)
        print("-" * 40)
        
        # Step 3: Verify the quantity was updated
        print("📈 Step 3: Verifying quantity update...")
        updated_devices = local_db.get_registered_devices()
        target_device = next((dev for dev in updated_devices if dev['device_id'] == test_device_id), None)
        
        if target_device:
            current_quantity = target_device.get('quantity', 0)
            print(f"✅ Current quantity for device {test_device_id}: {current_quantity}")
        else:
            print(f"❌ Device {test_device_id} not found after update")
        
        # Step 4: Check recent scans
        print("📋 Step 4: Checking recent barcode scans...")
        recent_scans = local_db.get_recent_scans(limit=5)
        
        print("Recent scans:")
        for i, scan in enumerate(recent_scans, 1):
            print(f"  {i}. Barcode: {scan.get('barcode', 'N/A')}")
            print(f"     Device: {scan.get('device_id', 'N/A')}")
            print(f"     Time: {scan.get('timestamp', 'N/A')}")
            print(f"     Quantity: {scan.get('quantity', 'N/A')}")
            print()
        
        print("✅ QUANTITY UPDATE TEST COMPLETED")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quantity_update()
