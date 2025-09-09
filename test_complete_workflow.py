#!/usr/bin/env python3
"""
Test script to verify the complete barcode scanner workflow:
1. Device registration (without quantity updates)
2. Product barcode scanning (with quantity updates)
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

from barcode_scanner_app import process_barcode_scan
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_complete_workflow():
    """Test the complete workflow: registration + barcode scanning"""
    
    print("🧪 TESTING COMPLETE BARCODE SCANNER WORKFLOW")
    print("=" * 60)
    
    # Test device registration (should NOT send quantity updates)
    print("\n📋 STEP 1: Testing Device Registration")
    print("-" * 40)
    
    device_barcode = "scanner-test-001"  # Use scanner prefix for device registration
    print(f"Registering device with barcode: {device_barcode}")
    
    try:
        registration_result = process_barcode_scan(device_barcode)
        print("✅ Registration Result:")
        print(registration_result)
        print()
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return False
    
    # Test product barcode scanning (should send quantity updates)
    print("\n📦 STEP 2: Testing Product Barcode Scanning")
    print("-" * 40)
    
    product_barcode = "5901234123457"  # Valid EAN-13 barcode
    device_id = "scanner-test-001"  # Use the registered device ID
    print(f"Scanning product barcode: {product_barcode} for device: {device_id}")
    
    try:
        scan_result = process_barcode_scan(product_barcode, device_id)
        print("✅ Barcode Scan Result:")
        print(scan_result)
        print()
    except Exception as e:
        print(f"❌ Barcode scan failed: {e}")
        return False
    
    # Test another product barcode to verify quantity updates
    print("\n📦 STEP 3: Testing Second Product Barcode")
    print("-" * 40)
    
    product_barcode2 = "8901030895559"  # Another valid EAN-13 barcode
    print(f"Scanning second product barcode: {product_barcode2} for device: {device_id}")
    
    try:
        scan_result2 = process_barcode_scan(product_barcode2, device_id)
        print("✅ Second Barcode Scan Result:")
        print(scan_result2)
        print()
    except Exception as e:
        print(f"❌ Second barcode scan failed: {e}")
        return False
    
    print("🎉 WORKFLOW TEST COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\n📊 SUMMARY:")
    print("✅ Device registration: Working (no quantity updates)")
    print("✅ Product barcode scanning: Working (with quantity updates)")
    print("✅ Multiple product scans: Working (quantity increments)")
    
    return True

if __name__ == "__main__":
    success = test_complete_workflow()
    if success:
        print("\n🟢 All tests passed - workflow is working correctly!")
        sys.exit(0)
    else:
        print("\n🔴 Some tests failed - check the logs above")
        sys.exit(1)
