#!/usr/bin/env python3
"""
Simple test for registration and EAN scanning with correct device ID
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_scan

def test_simple_flow():
    """Test with correct device ID format"""
    
    print("🧪 Testing Simple Registration and EAN Flow...")
    print("=" * 50)
    
    # Step 1: Register device
    print("📝 STEP 1: Device Registration")
    registration_barcode = "REG12345678"
    result1 = process_barcode_scan(registration_barcode)
    print(f"Registration Result: {result1[:200]}...")
    print()
    
    # Step 2: Scan EAN with correct device ID (from registration result)
    print("📊 STEP 2: EAN Barcode Scanning")
    ean_barcode = "1234567890123"
    device_id = "12345678"  # Use the actual registered device ID
    print(f"EAN Barcode: {ean_barcode}")
    print(f"Device ID: {device_id}")
    
    result2 = process_barcode_scan(ean_barcode, device_id)
    print(f"EAN Scan Result: {result2[:200]}...")
    
    if "✅" in result2:
        print("\n✅ SUCCESS: EAN scanning with quantity update working!")
    else:
        print("\n❌ FAILED: EAN scanning not working")

if __name__ == "__main__":
    test_simple_flow()