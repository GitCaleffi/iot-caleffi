#!/usr/bin/env python3
"""Test with a valid EAN-13 barcode"""

import sys
import os
import json
import requests
from datetime import datetime

def test_with_valid_ean():
    """Test with a known valid EAN-13 barcode"""
    
    DEVICE_ID = "149f33d4a830"
    # Using a valid EAN-13 barcode (Coca-Cola)
    VALID_EAN13 = "5449000000996"  # Valid EAN-13 with correct check digit
    
    print("🧪 TESTING WITH VALID EAN-13 BARCODE")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {VALID_EAN13} (Valid EAN-13)")
    print()
    
    # Test different payload formats
    payloads_to_test = [
        {
            "name": "Format 1: Full payload",
            "data": {
                "scannedBarcode": VALID_EAN13,
                "deviceId": DEVICE_ID,
                "quantity": 1,
                "timestamp": datetime.now().isoformat(),
                "messageType": "barcode_scan"
            }
        },
        {
            "name": "Format 2: Simple payload",
            "data": {
                "scannedBarcode": VALID_EAN13,
                "deviceId": DEVICE_ID
            }
        },
        {
            "name": "Format 3: Just barcode",
            "data": {
                "scannedBarcode": VALID_EAN13
            }
        },
        {
            "name": "Format 4: Registration format",
            "data": {
                "deviceId": DEVICE_ID,
                "barcode": VALID_EAN13
            }
        }
    ]
    
    api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
    
    for payload_info in payloads_to_test:
        print(f"🧪 Testing {payload_info['name']}...")
        print(f"📤 Payload: {json.dumps(payload_info['data'], indent=2)}")
        
        try:
            response = requests.post(
                api_url,
                json=payload_info['data'],
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            
            print(f"📊 Response: {response.status_code}")
            print(f"📋 Body: {response.text}")
            
            if response.status_code == 200:
                print("✅ SUCCESS!")
                return True
            else:
                print("❌ Failed")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("-" * 30)
    
    print("❌ All payload formats failed")
    return False

if __name__ == "__main__":
    print("🚀 Starting valid EAN-13 test...")
    success = test_with_valid_ean()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 VALID EAN-13 WORKED! ✅")
    else:
        print("❌ EVEN VALID EAN-13 FAILED")
        print("🔧 API might have different requirements")
    print("=" * 50)