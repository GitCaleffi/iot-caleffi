#!/usr/bin/env python3
"""
Test script for barcode scanning functionality
Tests the fixed HID barcode extraction and IoT Hub messaging
"""

import sys
import os
import logging
from datetime import datetime

# Add src directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_hid_barcode_extraction():
    """Test the fixed HID barcode extraction logic"""
    print("🔍 Testing HID Barcode Extraction...")
    
    from barcode_scanner_app import extract_barcode_from_hid_buffer
    
    # Test cases for different barcode formats
    test_cases = [
        # EAN-13 barcode: 1234567890123
        {
            'name': 'EAN-13 Barcode',
            'input': [30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 30, 31, 32, 40],  # 1234567890123 + ENTER
            'expected': '1234567890123'
        },
        # EAN-8 barcode: 12345678
        {
            'name': 'EAN-8 Barcode',
            'input': [30, 31, 32, 33, 34, 35, 36, 37, 40],  # 12345678 + ENTER
            'expected': '12345678'
        },
        # Code 128 alphanumeric: ABC123
        {
            'name': 'Code 128 Alphanumeric',
            'input': [4, 5, 6, 30, 31, 32, 40],  # ABC123 + ENTER
            'expected': 'abc123'
        }
    ]
    
    for test_case in test_cases:
        print(f"  Testing {test_case['name']}...")
        result = extract_barcode_from_hid_buffer(test_case['input'])
        
        if result == test_case['expected']:
            print(f"    ✅ PASS: Got '{result}'")
        else:
            print(f"    ❌ FAIL: Expected '{test_case['expected']}', got '{result}'")
    
    print()

def test_barcode_processing():
    """Test the complete barcode processing workflow"""
    print("📦 Testing Barcode Processing Workflow...")
    
    try:
        from barcode_scanner_app import process_barcode_scan_auto
        
        # Test with a valid EAN-13 barcode
        test_barcode = "1234567890123"
        print(f"  Processing test barcode: {test_barcode}")
        
        result = process_barcode_scan_auto(test_barcode)
        print(f"  Result: {result}")
        
        if "✅" in result:
            print("  ✅ Barcode processing successful!")
        elif "⚠️" in result:
            print("  ⚠️ Barcode processing partially successful (check logs)")
        else:
            print("  ❌ Barcode processing failed")
            
    except Exception as e:
        print(f"  ❌ Error during barcode processing: {e}")
    
    print()

def test_device_registration():
    """Test device auto-registration"""
    print("🆔 Testing Device Registration...")
    
    try:
        from barcode_scanner_app import get_local_mac_address, local_db
        
        # Get MAC address
        mac_address = get_local_mac_address()
        if mac_address:
            print(f"  MAC Address: {mac_address}")
            
            # Generate device ID
            device_id = f"scanner-{mac_address.replace(':', '')[-8:]}"
            print(f"  Generated Device ID: {device_id}")
            
            # Check if already registered
            existing_device = local_db.get_device_id()
            if existing_device:
                print(f"  ✅ Device already registered: {existing_device}")
            else:
                print("  ⚠️ No device registered yet - will auto-register on first scan")
        else:
            print("  ❌ Could not get MAC address")
            
    except Exception as e:
        print(f"  ❌ Error during device registration test: {e}")
    
    print()

def test_iot_hub_connection():
    """Test IoT Hub connection setup"""
    print("☁️ Testing IoT Hub Connection...")
    
    try:
        from utils.dynamic_registration_service import get_dynamic_registration_service
        
        registration_service = get_dynamic_registration_service()
        print("  ✅ Dynamic registration service loaded")
        
        # Test device ID
        test_device_id = "test-scanner-12345678"
        
        # Try to get connection string (this will register if needed)
        connection_string = registration_service.get_device_connection_string(test_device_id)
        
        if connection_string and "YOUR_DEVICE" not in connection_string:
            print(f"  ✅ Got valid connection string for {test_device_id}")
            print(f"  Connection string format: {connection_string[:50]}...")
        else:
            print("  ⚠️ No valid connection string available")
            
    except Exception as e:
        print(f"  ❌ Error during IoT Hub connection test: {e}")
    
    print()

def main():
    """Run all tests"""
    print("🚀 Starting Barcode Scanner Tests")
    print("=" * 50)
    
    test_hid_barcode_extraction()
    test_device_registration()
    test_iot_hub_connection()
    test_barcode_processing()
    
    print("=" * 50)
    print("🏁 Tests completed!")
    print()
    print("📋 Next Steps:")
    print("1. Connect your USB barcode scanner")
    print("2. Run: python3 src/barcode_scanner_app.py --usb-auto")
    print("3. Scan a barcode to test the complete workflow")
    print("4. Check IoT Hub for EAN update messages")

if __name__ == "__main__":
    main()
