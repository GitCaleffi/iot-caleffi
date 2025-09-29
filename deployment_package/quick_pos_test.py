#!/usr/bin/env python3
"""
Quick POS Test - Simple test to check if POS forwarding works
"""

import os
import sys
import time
from pathlib import Path

def quick_test():
    print("⚡ Quick POS Forwarding Test")
    print("=" * 30)
    
    # Test 1: Basic file forwarding (always works)
    print("1️⃣ Testing file forwarding...")
    try:
        test_barcode = "QUICKTEST123"
        with open('/tmp/pos_test.txt', 'w') as f:
            f.write(f"Test barcode: {test_barcode}\n")
        print("✅ File forwarding: WORKING")
    except Exception as e:
        print(f"❌ File forwarding: FAILED - {e}")
    
    # Test 2: Check for attached devices
    print("\n2️⃣ Checking for attached devices...")
    
    # Serial devices
    import glob
    serial_devices = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    print(f"📡 Serial devices: {len(serial_devices)}")
    for device in serial_devices:
        print(f"  - {device}")
    
    # USB devices
    try:
        import subprocess
        result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            usb_count = len([line for line in result.stdout.split('\n') if line.strip()])
            print(f"🔌 USB devices: {usb_count}")
        else:
            print("🔌 USB devices: Cannot detect")
    except:
        print("🔌 USB devices: Cannot detect")
    
    # Test 3: Check clipboard forwarding
    print("\n3️⃣ Testing clipboard forwarding...")
    try:
        import subprocess
        test_text = "CLIPBOARD_TEST_123"
        
        # Try xsel
        result = subprocess.run(['xsel', '--clipboard', '--input'], 
                              input=test_text.encode(), timeout=2, capture_output=True)
        if result.returncode == 0:
            print("✅ Clipboard (xsel): WORKING")
        else:
            # Try xclip
            result = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                  input=test_text.encode(), timeout=2, capture_output=True)
            if result.returncode == 0:
                print("✅ Clipboard (xclip): WORKING")
            else:
                print("❌ Clipboard: NOT WORKING")
    except Exception as e:
        print(f"❌ Clipboard: FAILED - {e}")
    
    # Test 4: Test enhanced forwarder if available
    print("\n4️⃣ Testing enhanced POS forwarder...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from enhanced_pos_forwarder import EnhancedPOSForwarder
        
        forwarder = EnhancedPOSForwarder()
        test_barcode = "ENHANCED_TEST_456"
        
        # Just test device detection, not actual forwarding
        devices = forwarder.attached_devices
        total_devices = (len(devices['serial_ports']) + 
                        len(devices['usb_keyboards']) + 
                        len(devices['hid_devices']) + 
                        len(devices['network_terminals']))
        
        print(f"✅ Enhanced forwarder: LOADED")
        print(f"📊 Total devices detected: {total_devices}")
        
        if total_devices > 0:
            print("🎯 POS forwarding should work!")
        else:
            print("⚠️ No POS devices detected")
            
    except ImportError:
        print("❌ Enhanced forwarder: NOT AVAILABLE")
    except Exception as e:
        print(f"❌ Enhanced forwarder: ERROR - {e}")
    
    # Test 5: Test standard forwarder
    print("\n5️⃣ Testing standard forwarder...")
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'src'))
        from utils.usb_hid_forwarder import USBHIDForwarder
        
        forwarder = USBHIDForwarder()
        methods = forwarder.available_methods
        print(f"✅ Standard forwarder: LOADED")
        print(f"📊 Available methods: {', '.join(methods)}")
        
    except ImportError:
        print("❌ Standard forwarder: NOT AVAILABLE")
    except Exception as e:
        print(f"❌ Standard forwarder: ERROR - {e}")
    
    print("\n" + "=" * 30)
    print("🎯 QUICK TEST COMPLETE")
    print("=" * 30)
    
    # Simple recommendations
    if serial_devices:
        print("✅ Serial devices found - POS forwarding via serial should work")
    
    if os.path.exists('/tmp/pos_test.txt'):
        print("✅ File forwarding works - barcodes will be saved to files")
    
    print("\n📋 To test with real barcode:")
    print("  python3 test_pos_locally.py")
    
    print("\n📋 To test on Raspberry Pi:")
    print("  1. Copy enhanced_pos_forwarder.py to Pi")
    print("  2. Run: python3 enhanced_pos_forwarder.py")

if __name__ == "__main__":
    quick_test()
