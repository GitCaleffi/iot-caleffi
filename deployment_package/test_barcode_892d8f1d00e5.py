#!/usr/bin/env python3
"""
Test barcode scanning for device 892d8f1d00e5 from the user's image
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

def test_barcode_scanning():
    """Test barcode scanning with the specific barcode from user's image"""
    
    print("🧪 Testing barcode scanning for device: 892d8f1d00e5")
    print("=" * 60)
    
    try:
        # Test barcode from the image
        test_barcode = "892d8f1d00e5"
        
        print(f"📱 Testing barcode scan: {test_barcode}")
        
        # Process the barcode scan
        result = process_barcode_scan(test_barcode)
        
        if result:
            print("✅ Barcode scan processed successfully!")
            print(f"📊 Result: {result}")
        else:
            print("❌ Barcode scan failed")
            
    except Exception as e:
        print(f"❌ Error during barcode scanning test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_barcode_scanning()
