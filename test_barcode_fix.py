#!/usr/bin/env python3
"""
Test script to verify barcode scanner fixes
"""
import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from barcode_scanner_app import process_barcode_scan_auto
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_barcode_scanning():
    """Test the fixed barcode scanning functionality"""
    print("🧪 Testing barcode scanner fixes...")
    print("=" * 60)
    
    # Test barcode
    test_barcode = "1234567890123"
    
    try:
        print(f"📱 Testing barcode: {test_barcode}")
        result = process_barcode_scan_auto(test_barcode)
        
        if result:
            print("✅ Barcode scanning test PASSED")
            print("✅ IoT Hub messaging should now work correctly")
        else:
            print("❌ Barcode scanning test FAILED")
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_barcode_scanning()
