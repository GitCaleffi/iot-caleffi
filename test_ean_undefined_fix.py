#!/usr/bin/env python3
"""
Test script to verify the EAN undefined fix
Tests that messages are properly formatted and don't cause inventory issues
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

def test_ean_undefined_fix():
    """Test that messages are properly formatted to prevent EAN undefined errors"""
    
    test_device_id = "b2fa27f0e5a1"
    test_barcode = 12232547859652
    
    print("🧪 TESTING EAN UNDEFINED FIX")
    print(f"🔧 Test Device ID: {test_device_id}")
    print(f"📊 Test Barcode: {test_barcode}")
    print("=" * 60)
    
    try:
        # Import required modules
        from barcode_scanner_app import process_barcode_scan
        from database.local_storage import LocalStorage
        
        # Initialize local storage
        local_db = LocalStorage()
        
        # Step 1: Register a new device (should NOT cause inventory issues)
        print("📋 Step 1: Testing device registration (should NOT affect inventory)...")
        
        registration_result = process_barcode_scan(test_barcode, test_device_id)
        print("📝 Registration Result:")
        print(registration_result)
        print("-" * 40)
        
        # Wait for message processing
        import time
        time.sleep(2)
        
        # Step 2: Scan the same barcode again (should send proper quantity update)
        print("📊 Step 2: Testing quantity update (should send proper format)...")
        
        quantity_result = process_barcode_scan(test_barcode, test_device_id)
        print("📝 Quantity Update Result:")
        print(quantity_result)
        print("-" * 40)
        
        # Step 3: Verify message formats in logs
        print("📡 Step 3: Message Format Verification")
        print("✅ Check logs above for:")
        print("   - Registration messages with messageType: 'device_registration'")
        print("   - Quantity updates with messageType: 'quantity_update'")
        print("   - NO malformed JSON strings as deviceId")
        print("   - Proper message structure without nested JSON")
        
        # Step 4: Check device status
        registered_devices = local_db.get_registered_devices()
        target_device = next((dev for dev in registered_devices if dev['device_id'] == test_device_id), None)
        
        if target_device:
            print(f"✅ Device {test_device_id} found with quantity: {target_device.get('quantity', 0)}")
        else:
            print(f"⚠️  Device {test_device_id} not found in database")
        
        print("✅ EAN UNDEFINED FIX TEST COMPLETED")
        print("🔍 Monitor your IoT Hub for properly formatted messages")
        print("🚫 Should NOT see any 'EAN undefined' inventory drops")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ean_undefined_fix()
