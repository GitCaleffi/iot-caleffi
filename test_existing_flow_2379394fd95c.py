#!/usr/bin/env python3
"""
Test the existing barcode_scanner_app.py flow with device ID 2379394fd95c
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "deployment_package" / "src"))

# Import the existing functions
from barcode_scanner_app import process_barcode_scan

def test_device_registration_flow():
    """Test device registration flow with 2379394fd95c"""
    print("🔄 Testing Device Registration Flow")
    print("=" * 50)
    
    # Test 1: Register device 2379394fd95c
    device_id = "2379394fd95c"
    print(f"\n1. Testing device registration with: {device_id}")
    
    # The existing app expects device registration to be detected automatically
    # or can use REG prefix format
    registration_result = process_barcode_scan(device_id)
    print("Registration Result:")
    print(registration_result)
    
    return device_id

def test_ean_barcode_scanning_flow(device_id):
    """Test EAN barcode scanning flow"""
    print(f"\n🔄 Testing EAN Barcode Scanning Flow")
    print("=" * 50)
    
    # Test 2: Scan EAN barcode with registered device
    ean_barcode = "1234567890123"
    print(f"\n2. Testing EAN barcode scan: {ean_barcode}")
    
    # For product barcode scanning, we need to provide device_id
    scan_result = process_barcode_scan(ean_barcode, device_id)
    print("EAN Scan Result:")
    print(scan_result)
    
    # Test 3: Scan another EAN barcode
    ean_barcode2 = "9876543210987"
    print(f"\n3. Testing another EAN barcode: {ean_barcode2}")
    
    scan_result2 = process_barcode_scan(ean_barcode2, device_id)
    print("Second EAN Scan Result:")
    print(scan_result2)

def main():
    """Main test function"""
    print("🧪 Testing Existing barcode_scanner_app.py Flow")
    print("Device ID from image: 2379394fd95c")
    print("=" * 60)
    
    try:
        # Test device registration
        device_id = test_device_registration_flow()
        
        # Test EAN barcode scanning
        test_ean_barcode_scanning_flow(device_id)
        
        print(f"\n✅ Flow Test Completed!")
        print(f"📊 Check the logs and database for detailed results")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
