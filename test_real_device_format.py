#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
import json

def test_real_device_format():
    """Test registration with real device ID format"""
    
    print("🔍 **Real Device Format Registration Test**")
    print("=" * 50)
    
    # Use a real device ID format (12 hex characters)
    test_device_id = "a1b2c3d4e5f6"  # Real device format
    
    print(f"📱 Testing with real device format: {test_device_id}")
    print("-" * 30)
    
    print(f"\n🔍 Scanning device barcode: {test_device_id}")
    
    # Test registration
    registration_result = process_barcode_scan(test_device_id, test_device_id)
    
    print(f"\n📋 **Registration Result:**")
    print(registration_result)
    
    print(f"\n🎯 **Expected Results:**")
    print(f"✅ Frontend API: Should return 200 OK (valid device format)")
    print(f"✅ IoT Hub: Should send registration message successfully")
    print(f"✅ Local DB: Should save device with quantity 0")
    
    return True

if __name__ == "__main__":
    try:
        test_real_device_format()
        print(f"\n🏁 Real device format test completed!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
