#!/usr/bin/env python3
"""
Enhanced POS Forwarding Test Script
Tests barcode forwarding with the example barcode "8053734093444"
Compatible with all Raspberry Pi models (Pi 1 through Pi 5)
"""

import sys
import os
import time
import logging

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.usb_hid_forwarder import get_hid_forwarder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    print("🚀 Enhanced POS Forwarding Test")
    print("=" * 50)
    
    # Get the enhanced HID forwarder
    hid_forwarder = get_hid_forwarder()
    
    # Test barcode from user's example
    test_barcode = "8053734093444"
    
    print(f"\n🧪 Testing POS forwarding with barcode: {test_barcode}")
    print("-" * 50)
    
    # Run comprehensive test
    results = hid_forwarder.test_barcode_forwarding(test_barcode)
    
    # Display detailed results
    print(f"\n📊 Detailed Test Results:")
    print("=" * 50)
    
    working_methods = []
    failed_methods = []
    
    for method, success in results.items():
        status = "✅ WORKING" if success else "❌ FAILED"
        print(f"{method:15} : {status}")
        
        if success:
            working_methods.append(method)
        else:
            failed_methods.append(method)
    
    print(f"\n📈 Summary:")
    print(f"✅ Working methods ({len(working_methods)}): {', '.join(working_methods) if working_methods else 'None'}")
    print(f"❌ Failed methods ({len(failed_methods)}): {', '.join(failed_methods) if failed_methods else 'None'}")
    
    # Test individual forwarding
    print(f"\n🔄 Testing individual barcode forwarding...")
    success = hid_forwarder.forward_barcode(test_barcode)
    
    if success:
        print(f"✅ Barcode {test_barcode} forwarded successfully!")
        print(f"💡 The barcode should now appear in your POS system")
    else:
        print(f"❌ Failed to forward barcode {test_barcode}")
        print(f"💡 Check the logs above for specific error details")
    
    # Check for file outputs
    print(f"\n📄 Checking file outputs...")
    file_locations = [
        '/tmp/pos_barcode.txt',
        '/tmp/latest_barcode.txt', 
        '/tmp/current_barcode.txt'
    ]
    
    for file_path in file_locations:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    if test_barcode in content:
                        print(f"✅ Found barcode in {file_path}")
                    else:
                        print(f"⚠️  File exists but barcode not found in {file_path}")
            except Exception as e:
                print(f"❌ Error reading {file_path}: {e}")
        else:
            print(f"❌ File not found: {file_path}")
    
    # Interactive test mode
    print(f"\n🎮 Interactive Test Mode")
    print("Enter barcodes to test (or 'quit' to exit):")
    
    while True:
        try:
            user_input = input("\nBarcode: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            if user_input:
                print(f"🔄 Forwarding: {user_input}")
                success = hid_forwarder.forward_barcode(user_input)
                
                if success:
                    print(f"✅ Successfully forwarded: {user_input}")
                else:
                    print(f"❌ Failed to forward: {user_input}")
            
        except KeyboardInterrupt:
            print(f"\n👋 Exiting...")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n🎉 Test completed!")

if __name__ == "__main__":
    main()
