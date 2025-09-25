#!/usr/bin/env python3
"""
Manual barcode test script for Caleffi Barcode Scanner
"""

import sys
import os

# Add the src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from keyboard_scanner import process_barcode_with_device
from utils.usb_hid_forwarder import get_hid_forwarder

def test_pos_forwarding():
    """Test POS forwarding directly"""
    device_id = "56d19958e6e7"  # Updated device ID
    test_barcode = "8053734093444"  # Your test barcode
    
    print(f"🧪 Testing POS forwarding for barcode: {test_barcode}")
    print(f"📱 Device ID: {device_id}")
    
    # Test HID forwarder directly
    forwarder = get_hid_forwarder()
    success = forwarder.forward_barcode(test_barcode)
    
    if success:
        print(f"✅ POS forwarding successful!")
        
        # Check if file was created
        if os.path.exists('/tmp/pos_barcode.txt'):
            with open('/tmp/pos_barcode.txt', 'r') as f:
                content = f.read().strip()
            print(f"📄 Barcode written to file: {content}")
        
        return True
    else:
        print(f"❌ POS forwarding failed!")
        return False

def test_full_barcode_processing():
    """Test full barcode processing pipeline"""
    device_id = "56d19958e6e7"
    test_barcode = "8053734093444"
    
    print(f"\n🔄 Testing full barcode processing...")
    result = process_barcode_with_device(test_barcode, device_id)
    print(f"📋 Processing result: {result}")

def manual_barcode_input():
    """Allow manual barcode input for testing"""
    print("📱 Manual Barcode Input Test")
    print("=" * 50)
    print("This lets you test IoT Hub integration by typing barcodes manually")
    print("Perfect for testing while configuring your physical scanner")
    print()
    
    scan_count = 0
    
    try:
        while True:
            print(f"\n🔍 Scan #{scan_count + 1}")
            barcode = input("Enter barcode (or 'quit' to exit): ").strip()
            
            if barcode.lower() in ['quit', 'exit', 'q']:
                break
                
            if not barcode:
                print("⚠️ Empty barcode, try again")
                continue
            
            print(f"📦 Processing barcode: {barcode}")
            print("-" * 30)
            
            try:
                # Process the barcode through the full system
                result = process_barcode_scan_auto(barcode)
                
                if result:
                    scan_count += 1
                    print("✅ SUCCESS: Barcode processed and sent to IoT Hub!")
                    print(f"📊 Total successful scans: {scan_count}")
                else:
                    print("❌ FAILED: Barcode processing failed")
                    
            except Exception as e:
                print(f"❌ ERROR: {e}")
                logger.error(f"Barcode processing error: {e}")
                
    except KeyboardInterrupt:
        print(f"\n🛑 Stopped by user")
    
    print(f"\n📊 Session Summary:")
    print(f"   • Total successful scans: {scan_count}")
    print(f"   • IoT Hub integration: {'✅ Working' if scan_count > 0 else '❌ Issues detected'}")

def test_common_barcodes():
    """Test with some common barcode formats"""
    print("\n🧪 Testing Common Barcode Formats")
    print("=" * 40)
    
    test_barcodes = [
        ("1234567890123", "EAN-13 Test"),
        ("123456789012", "UPC-A Test"), 
        ("12345678", "EAN-8 Test"),
        ("ABC123DEF456", "Code 128 Test")
    ]
    
    for barcode, description in test_barcodes:
        print(f"\n🔍 Testing {description}: {barcode}")
        try:
            result = process_barcode_scan_auto(barcode)
            status = "✅ SUCCESS" if result else "❌ FAILED"
            print(f"   Result: {status}")
        except Exception as e:
            print(f"   Result: ❌ ERROR - {e}")

def main():
    print("🚀 Manual Barcode Testing Tool")
    print("=" * 50)
    print("Use this to test IoT Hub integration while setting up your physical scanner")
    print()
    
    choice = input("Choose test mode:\n1. Manual input\n2. Auto-test common formats\n3. Both\nChoice (1-3): ").strip()
    
    if choice == "1":
        manual_barcode_input()
    elif choice == "2":
        test_common_barcodes()
    elif choice == "3":
        test_common_barcodes()
        manual_barcode_input()
    else:
        print("Invalid choice, starting manual input mode...")
        manual_barcode_input()

if __name__ == "__main__":
    main()
