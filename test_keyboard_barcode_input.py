#!/usr/bin/env python3
"""
Keyboard Barcode Input Test
Tests barcode scanning using keyboard input simulation
"""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from barcode_scanner_app import process_barcode_scan_auto

def test_dynamic_ean_scanning():
    """Test dynamic EAN scanning with different barcode numbers"""
    
    print("=" * 60)
    print("🧪 DYNAMIC EAN BARCODE TESTING")
    print("=" * 60)
    print("Testing different EAN numbers to simulate real barcode scanning...")
    print()
    
    # Test different EAN numbers to simulate real scanning
    test_barcodes = [
        "9780123456789",  # Book ISBN
        "0123456789012",  # UPC-A
        "1234567890128",  # EAN-13
        "12345678",       # EAN-8
        "5901234123457",  # Product EAN
        "8901030895559",  # Indian product
        "4006381333931",  # German product
        "3760020507350",  # French product
    ]
    
    print(f"🔄 Testing {len(test_barcodes)} different EAN numbers...")
    print()
    
    for i, barcode in enumerate(test_barcodes, 1):
        print(f"📦 Test {i}/{len(test_barcodes)}: Processing EAN {barcode}")
        print("-" * 40)
        
        try:
            # Process each barcode
            result = process_barcode_scan_auto(barcode)
            
            # Show result
            if "sent to IoT Hub successfully" in str(result):
                print(f"✅ SUCCESS: EAN {barcode} sent to IoT Hub")
            elif "saved locally" in str(result):
                print(f"⚠️  OFFLINE: EAN {barcode} saved locally")
            else:
                print(f"ℹ️  RESULT: {result}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        print()
        time.sleep(1)  # Small delay between tests
    
    print("=" * 60)
    print("✅ DYNAMIC EAN TESTING COMPLETED")
    print("=" * 60)
    print("📊 Results:")
    print("• Each EAN number was processed as a separate barcode scan")
    print("• Messages sent to IoT Hub with different EAN values")
    print("• Device registration handled automatically")
    print("• Check Azure IoT Hub for messages with different EAN numbers")

def test_manual_input():
    """Allow manual barcode input for testing"""
    
    print("\n" + "=" * 60)
    print("⌨️  MANUAL BARCODE INPUT TEST")
    print("=" * 60)
    print("Enter barcode numbers manually to test dynamic scanning:")
    print("(Type 'quit' to exit)")
    print()
    
    while True:
        try:
            barcode = input("📱 Enter barcode/EAN: ").strip()
            
            if barcode.lower() in ['quit', 'exit', 'q']:
                break
                
            if not barcode:
                continue
                
            print(f"🔄 Processing: {barcode}")
            result = process_barcode_scan_auto(barcode)
            
            if "sent to IoT Hub successfully" in str(result):
                print(f"✅ SUCCESS: Sent to IoT Hub")
            elif "saved locally" in str(result):
                print(f"⚠️  OFFLINE: Saved locally")
            else:
                print(f"ℹ️  RESULT: {result}")
            
            print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ ERROR: {e}")
            print()
    
    print("👋 Manual input test completed")

def main():
    print("🚀 Starting Keyboard Barcode Input Tests")
    print()
    
    # Test 1: Automated dynamic EAN testing
    test_dynamic_ean_scanning()
    
    # Test 2: Manual input (optional)
    try:
        response = input("\n🤔 Would you like to test manual barcode input? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            test_manual_input()
    except KeyboardInterrupt:
        pass
    
    print("\n🏁 All tests completed!")
    print("\n💡 Key Points:")
    print("• System processes any EAN number you provide")
    print("• Each different number creates a unique IoT Hub message")
    print("• No physical scanner needed - just provide EAN numbers")
    print("• Check IoT Hub for messages with device ID: pi-c1323007")

if __name__ == "__main__":
    main()
