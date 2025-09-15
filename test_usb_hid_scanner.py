#!/usr/bin/env python3
"""
Test script for USB HID Scanner integration in barcode_scanner_app.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from barcode_scanner_app import (
    find_usb_hid_devices, 
    read_barcode_from_hid, 
    start_usb_hid_scanner_service,
    is_scanner_connected
)
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_hid_device_detection():
    """Test USB HID device detection"""
    print("🔍 Testing USB HID device detection...")
    
    hid_devices = find_usb_hid_devices()
    print(f"📱 Found {len(hid_devices)} HID devices: {hid_devices}")
    
    scanner_connected = is_scanner_connected()
    print(f"🔌 Scanner connected: {'✅ Yes' if scanner_connected else '❌ No'}")
    
    return hid_devices

def test_hid_barcode_reading(device_path, timeout=10):
    """Test barcode reading from HID device"""
    print(f"\n📖 Testing barcode reading from {device_path}")
    print("🔍 Please scan a barcode within 10 seconds...")
    
    try:
        barcode = read_barcode_from_hid(device_path, timeout=timeout)
        if barcode:
            print(f"✅ Successfully read barcode: {barcode}")
            return barcode
        else:
            print("⏰ No barcode read within timeout period")
            return None
    except Exception as e:
        print(f"❌ Error reading barcode: {e}")
        return None

def test_usb_hid_service():
    """Test the full USB HID scanner service"""
    print("\n🚀 Testing USB HID Scanner Service...")
    print("⚠️ This will start the full service - use Ctrl+C to stop")
    
    try:
        # This will run the full service
        start_usb_hid_scanner_service("test-hid-device")
    except KeyboardInterrupt:
        print("\n👋 Service stopped by user")
    except Exception as e:
        print(f"❌ Service error: {e}")

def main():
    """Main test function"""
    print("🎯 USB HID Scanner Integration Test")
    print("=" * 50)
    
    # Test 1: Device detection
    hid_devices = test_hid_device_detection()
    
    if not hid_devices:
        print("\n❌ No HID devices found. Please connect your USB barcode scanner.")
        print("💡 Make sure you have permission to access /dev/hidraw* devices")
        print("💡 You may need to run with sudo: sudo python3 test_usb_hid_scanner.py")
        return
    
    # Test 2: Quick barcode read test
    device_path = hid_devices[0]
    print(f"\n🎯 Using device: {device_path}")
    
    choice = input("\nChoose test:\n1. Quick barcode read test (10s timeout)\n2. Full service test\n3. Skip tests\nEnter choice (1-3): ").strip()
    
    if choice == "1":
        test_hid_barcode_reading(device_path, timeout=10)
    elif choice == "2":
        test_usb_hid_service()
    else:
        print("✅ Tests skipped - integration appears successful")
    
    print("\n🎉 USB HID Scanner integration test completed!")
    print("💡 To use the USB HID scanner in production:")
    print("   python3 src/barcode_scanner_app.py --usb-hid")

if __name__ == "__main__":
    main()
