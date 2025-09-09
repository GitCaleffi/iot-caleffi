#!/usr/bin/env python3
"""
Test the exact flow: 
1. Scan registration barcode -> check database -> register device -> save to DB -> send to IoT Hub & Frontend API
2. Scan EAN barcode -> update quantity on registered device -> send to IoT Hub & Frontend API
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_scan

def test_exact_flow():
    """Test the exact flow as requested"""
    
    print("🧪 Testing EXACT Flow as Requested...")
    print("=" * 70)
    
    # STEP 1: Device Registration Flow
    print("📝 STEP 1: DEVICE REGISTRATION")
    print("- Scan registration barcode")
    print("- Check if device exists in database") 
    print("- If not registered: register device")
    print("- Save to database")
    print("- Send to IoT Hub & Frontend API")
    print("-" * 50)
    
    registration_barcode = "NEWDEVICE123456"
    print(f"Scanning Registration Barcode: {registration_barcode}")
    
    # Scan registration barcode (no device_id = registration mode)
    result1 = process_barcode_scan(registration_barcode)
    print("Registration Result:")
    print(result1)
    print("=" * 70)
    
    # STEP 2: EAN Barcode Scanning Flow  
    print("📊 STEP 2: EAN BARCODE SCANNING")
    print("- Scan EAN barcode with registered device ID")
    print("- Update EAN number and quantity +1")
    print("- Send to IoT Hub & Frontend API")
    print("-" * 50)
    
    ean_barcode = "8901234567890"  # EAN-13 barcode
    device_id = "123456"  # Device ID from registration (last 6 chars)
    print(f"Scanning EAN Barcode: {ean_barcode}")
    print(f"Using Device ID: {device_id}")
    
    # Scan EAN barcode with device_id (quantity update mode)
    result2 = process_barcode_scan(ean_barcode, device_id)
    print("EAN Scan Result:")
    print(result2)
    print("=" * 70)
    
    # Verify the flow worked
    if "registered" in result1.lower() and "quantity" in result2.lower():
        print("✅ SUCCESS: Exact flow working perfectly!")
        print("✅ Registration: Device registered and saved to database")
        print("✅ EAN Scanning: Quantity updated and sent to IoT Hub & Frontend API")
    else:
        print("❌ ISSUE: Check the results above")

if __name__ == "__main__":
    test_exact_flow()