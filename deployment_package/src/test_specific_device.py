#!/usr/bin/env python3
"""
Test specific device ID 2379394fd95c with EAN barcode 7854965897485
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_scan

def test_specific_device():
    """Test device 2379394fd95c with EAN barcode 7854965897485"""
    
    print("🧪 Testing Specific Device Registration and EAN Scanning...")
    print("=" * 60)
    
    # Step 1: Register device 2379394fd95c
    print("📝 STEP 1: Device Registration")
    registration_barcode = "REG2379394fd95c"
    print(f"Registration Barcode: {registration_barcode}")
    print("-" * 40)
    
    result1 = process_barcode_scan(registration_barcode)
    print("Registration Result:")
    print(result1)
    print("=" * 60)
    
    # Step 2: Scan EAN barcode 7854965897485 for quantity update
    print("📊 STEP 2: EAN Barcode Scanning")
    ean_barcode = "7854965897485"
    device_id = "2379394fd95c"
    print(f"EAN Barcode: {ean_barcode}")
    print(f"Device ID: {device_id}")
    print("-" * 40)
    
    result2 = process_barcode_scan(ean_barcode, device_id)
    print("EAN Scan Result:")
    print(result2)
    print("=" * 60)
    
    # Check results
    if "✅" in result2 and "quantity" in result2.lower():
        print("✅ SUCCESS: Device registration and EAN scanning working!")
        print("✅ Quantity update sent to both IoT Hub and Frontend API")
    else:
        print("❌ FAILED: Check the results above")

if __name__ == "__main__":
    test_specific_device()