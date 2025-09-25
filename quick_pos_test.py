#!/usr/bin/env python3
"""
Quick POS forwarding test with device ID 7079fa7ab32e
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from utils.usb_hid_forwarder import get_hid_forwarder
import subprocess

def test_pos_with_device():
    """Test POS forwarding with specific device"""
    device_id = "7079fa7ab32e"
    test_barcode = "8906044234994"  # From your previous scan
    
    print(f"🧪 Testing POS forwarding for device: {device_id}")
    print(f"📦 Test barcode: {test_barcode}")
    
    # Get HID forwarder
    forwarder = get_hid_forwarder()
    
    # Test forwarding
    print(f"\n🚀 Forwarding barcode {test_barcode}...")
    success = forwarder.forward_barcode(test_barcode)
    
    if success:
        print("✅ POS forwarding completed")
        
        # Check clipboard
        try:
            result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                  capture_output=True, text=True, timeout=2)
            clipboard_content = result.stdout.strip()
            
            if clipboard_content == test_barcode:
                print(f"✅ SUCCESS: Barcode {test_barcode} is in clipboard!")
                print(f"📋 Your POS system can now read: {clipboard_content}")
                return True
            else:
                print(f"⚠️  Clipboard content: '{clipboard_content}'")
                return False
                
        except Exception as e:
            print(f"❌ Clipboard check failed: {e}")
            # Try alternative method
            try:
                result = subprocess.run(['xsel', '--clipboard', '--output'], 
                                      capture_output=True, text=True, timeout=2)
                clipboard_content = result.stdout.strip()
                if clipboard_content == test_barcode:
                    print(f"✅ SUCCESS: Barcode {test_barcode} is in clipboard (via xsel)!")
                    return True
            except:
                pass
            return False
    else:
        print("❌ POS forwarding failed")
        return False

if __name__ == "__main__":
    success = test_pos_with_device()
    if success:
        print("\n🎉 POS forwarding is WORKING!")
        print("💡 Your barcode scanner can now send barcodes to POS systems via clipboard")
    else:
        print("\n❌ POS forwarding needs fixing")
