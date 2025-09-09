#!/usr/bin/env python3
"""
Test Device Registration Script
Tests the process_barcode_scan function with barcode 84b772dc334a
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'src'))

# Import required modules
from src.barcode_scanner_app import process_barcode_scan
from src.database.local_storage import LocalStorage

def test_device_registration():
    """Test device registration with barcode 84b772dc334a"""
    
    test_barcode = "84b772dc334a"
    
    print("🧪 Testing Device Registration")
    print("=" * 50)
    print(f"📱 Test Barcode: {test_barcode}")
    print(f"🆔 Expected Device ID: {test_barcode} (barcode-based)")
    print()
    
    # Check database state before test
    print("📊 Database State Before Test:")
    local_db = LocalStorage()
    
    try:
        registered_devices = local_db.get_registered_devices()
        print(f"  • Registered devices: {len(registered_devices)}")
        
        if registered_devices:
            for device in registered_devices:
                print(f"    - {device['device_id']} (quantity: {device['quantity']})")
        else:
            print("    - No registered devices found")
    except Exception as e:
        print(f"  • Error checking database: {e}")
    
    print()
    print("🚀 Starting Registration Test...")
    print("-" * 30)
    
    try:
        # Call the process_barcode_scan function
        result = process_barcode_scan(test_barcode)
        
        print("✅ Function executed successfully!")
        print()
        print("📋 Result:")
        print(result)
        print()
        
        # Check database state after test
        print("📊 Database State After Test:")
        registered_devices = local_db.get_registered_devices()
        print(f"  • Registered devices: {len(registered_devices)}")
        
        if registered_devices:
            for device in registered_devices:
                print(f"    - Device ID: {device['device_id']}")
                print(f"      Barcode: {device['barcode']}")
                print(f"      Quantity: {device['quantity']}")
                print(f"      Registered: {device['registered_at']}")
                print(f"      Last Updated: {device['last_updated']}")
                print()
        
        # Verify the specific device was registered
        target_device = next((dev for dev in registered_devices if dev['device_id'] == test_barcode), None)
        
        if target_device:
            print("🎉 SUCCESS: Device registration verified!")
            print(f"  • Device ID: {target_device['device_id']}")
            print(f"  • Quantity: {target_device['quantity']}")
            print(f"  • Registration time: {target_device['registered_at']}")
        else:
            print("❌ FAILED: Device not found in database after registration")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Main test function"""
    print("🔬 Device Registration Test Suite")
    print("=" * 50)
    
    success = test_device_registration()
    
    print()
    print("=" * 50)
    if success:
        print("✅ All tests completed successfully!")
    else:
        print("❌ Tests failed!")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
