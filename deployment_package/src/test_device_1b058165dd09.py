#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_automatically

def test_device_flow():
    device_id = "1b058165dd09"
    test_barcode = "4523210256547"
    
    print(f"🧪 Testing device {device_id} with barcode {test_barcode}")
    print("=" * 50)
    
    try:
        result = process_barcode_automatically(test_barcode, device_id)
        print(f"✅ Test completed successfully")
        return result
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_device_flow()
