#!/usr/bin/env python3
"""
Test quantity update to verify IoT Hub connection string is working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_scan

def test_quantity_update():
    """Test quantity update with a known device"""
    
    # Test with a simple barcode and device ID
    test_barcode = "1234567890125"
    test_device_id = "0ba242e597f5"
    
    print(f"🧪 Testing quantity update...")
    print(f"📱 Barcode: {test_barcode}")
    print(f"🆔 Device ID: {test_device_id}")
    print("-" * 50)
    
    # Process the barcode scan (this will either register new device or update quantity)
    result = process_barcode_scan(test_barcode, test_device_id)
    
    print("📊 Result:")
    print(result)
    print("-" * 50)
    
    if "✅" in result:
        print("✅ SUCCESS: IoT Hub connection string is working!")
    else:
        print("❌ FAILED: Check IoT Hub connection string")

if __name__ == "__main__":
    test_quantity_update()