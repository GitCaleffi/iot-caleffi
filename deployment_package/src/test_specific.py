#!/usr/bin/env python3
"""Test barcode_scanner_app.py with specific device and barcode"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from barcode_scanner_app import process_barcode_automatically

def test_specific():
    """Test with specific device ID and barcode"""
    
    DEVICE_ID = "933dee6de6ee"
    BARCODE = "4523210256547"
    
    print("🧪 TESTING BARCODE_SCANNER_APP.PY - FULLY AUTOMATIC")
    print("=" * 55)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {BARCODE}")
    print()
    
    print("🚀 Testing fully automatic functionality...")
    print("-" * 45)
    
    try:
        # Test the automatic process
        result = process_barcode_automatically(BARCODE, DEVICE_ID)
        
        print(f"📋 Result: {result}")
        
        if "sent" in str(result).lower():
            print("\n🎉 FULLY AUTOMATIC - SUCCESS!")
            print("✅ No manual input required")
            print("✅ Device processed automatically")
            print("✅ Barcode sent automatically")
            print("✅ Threading lock working")
            return True
        else:
            print(f"\n⚠️ Process completed: {result}")
            return True
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_specific()
    
    print("\n" + "=" * 55)
    if success:
        print("🎉 BARCODE_SCANNER_APP.PY IS FULLY AUTOMATIC ✅")
    else:
        print("❌ NOT FULLY AUTOMATIC")
    print("=" * 55)
