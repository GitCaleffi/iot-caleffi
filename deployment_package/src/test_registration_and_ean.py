#!/usr/bin/env python3
"""
Test the new registration and EAN scanning flow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_scan

def test_registration_and_ean():
    """Test device registration and EAN scanning separately"""
    
    print("🧪 Testing Registration and EAN Scanning Flow...")
    print("=" * 60)
    
    # Step 1: Register device (no device_id provided = registration)
    print("📝 STEP 1: Device Registration")
    registration_barcode = "REG12345678"
    print(f"Registration Barcode: {registration_barcode}")
    print("-" * 40)
    
    result1 = process_barcode_scan(registration_barcode)
    print("Result:")
    print(result1)
    print("=" * 60)
    
    # Step 2: Scan EAN barcode (with device_id = quantity update)
    print("📊 STEP 2: EAN Barcode Scanning")
    ean_barcode = "1234567890123"
    device_id = "device-12345678"  # Generated from registration barcode
    print(f"EAN Barcode: {ean_barcode}")
    print(f"Device ID: {device_id}")
    print("-" * 40)
    
    result2 = process_barcode_scan(ean_barcode, device_id)
    print("Result:")
    print(result2)
    print("=" * 60)
    
    # Step 3: Scan another EAN barcode (should increment quantity)
    print("📊 STEP 3: Second EAN Barcode Scan")
    ean_barcode2 = "9876543210987"
    print(f"EAN Barcode: {ean_barcode2}")
    print(f"Device ID: {device_id}")
    print("-" * 40)
    
    result3 = process_barcode_scan(ean_barcode2, device_id)
    print("Result:")
    print(result3)

if __name__ == "__main__":
    test_registration_and_ean()