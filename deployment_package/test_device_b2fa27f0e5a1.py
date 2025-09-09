#!/usr/bin/env python3
"""
Test device registration and barcode scanning for device ID b2fa27f0e5a1
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from barcode_scanner_app import process_barcode_scan
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_device_registration():
    """Test device registration and scanning for b2fa27f0e5a1"""
    
    print("🧪 Testing Device Registration: b2fa27f0e5a1")
    print("=" * 60)
    
    try:
        # Test device ID
        device_id = "b2fa27f0e5a1"
        
        print(f"📱 Testing device registration: {device_id}")
        
        # Process the device registration
        result = process_barcode_scan(device_id)
        
        if result:
            print("✅ Device registration processed successfully!")
            print(f"📊 Result: {result}")
            
            # Test a follow-up scan to verify device is registered
            print(f"\n🔄 Testing follow-up scan with same device...")
            result2 = process_barcode_scan(device_id)
            
            if result2:
                print("✅ Follow-up scan processed successfully!")
                print(f"📊 Result: {result2}")
            else:
                print("❌ Follow-up scan failed")
                
        else:
            print("❌ Device registration failed")
            
    except Exception as e:
        print(f"❌ Error during device registration test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_device_registration()
