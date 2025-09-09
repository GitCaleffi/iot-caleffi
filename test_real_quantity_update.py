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

def test_real_quantity_update():
    """Test quantity update functionality with proper device registration check"""
    
    # Test parameters from user
    test_barcode = "1122365214528"
    test_device_id = "1b058165dd09"
    
    print("🧪 TESTING REAL-TIME QUANTITY UPDATE")
    print(f"📊 Test Barcode: {test_barcode}")
    print(f"🔧 Test Device ID: {test_device_id}")
    print("=" * 60)
    
    try:
        # Import required modules
        from barcode_scanner_app import process_barcode_scan
        from database.local_storage import LocalStorage
        
        # Initialize local storage
        local_db = LocalStorage()
        
        # Step 1: Ensure device is registered first
        print("📋 Step 1: Ensuring device is registered...")
        registered_devices = local_db.get_registered_devices()
        device_exists = any(device['device_id'] == test_device_id for device in registered_devices)
        
        if not device_exists:
            print(f"⚠️  Device {test_device_id} not registered. Registering now...")
            
            # Register device first with a different barcode to avoid confusion
            registration_result = process_barcode_scan("REGISTRATION_BARCODE", test_device_id)
            print("📝 Registration completed")
            print("-" * 40)
            
            # Wait a moment for registration to complete
            import time
            time.sleep(3)
            
            # Verify registration
            registered_devices = local_db.get_registered_devices()
            device_exists = any(device['device_id'] == test_device_id for device in registered_devices)
            
            if device_exists:
                print(f"✅ Device {test_device_id} successfully registered")
            else:
                print(f"❌ Device {test_device_id} registration failed")
                return
        else:
            print(f"✅ Device {test_device_id} already registered")
        
        # Get current quantity before update
        target_device = next((dev for dev in registered_devices if dev['device_id'] == test_device_id), None)
        initial_quantity = target_device.get('quantity', 0) if target_device else 0
        print(f"📊 Initial quantity: {initial_quantity}")
        
        # Step 2: Now scan the barcode for quantity update
        print(f"📊 Step 2: Scanning barcode {test_barcode} for quantity update...")
        
        result = process_barcode_scan(test_barcode, test_device_id)
        print("📝 Scan Result:")
        print(result)
        print("-" * 40)
        
        # Step 3: Verify the quantity was updated
        print("📈 Step 3: Verifying quantity update...")
        updated_devices = local_db.get_registered_devices()
        updated_device = next((dev for dev in updated_devices if dev['device_id'] == test_device_id), None)
        
        if updated_device:
            final_quantity = updated_device.get('quantity', 0)
            print(f"✅ Final quantity for device {test_device_id}: {final_quantity}")
            
            if final_quantity > initial_quantity:
                print(f"🎉 SUCCESS: Quantity increased from {initial_quantity} to {final_quantity}")
            else:
                print(f"⚠️  WARNING: Quantity did not increase (still {final_quantity})")
        else:
            print(f"❌ Device {test_device_id} not found after scan")
        
        # Step 4: Check if quantity update message was sent to IoT Hub
        print("📡 Step 4: Checking IoT Hub message logs...")
        print("Look for 'quantity_update' messageType in the logs above")
        
        print("✅ QUANTITY UPDATE TEST COMPLETED")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_quantity_update()
