#!/usr/bin/env python3
"""
Fixed USB Barcode Scanner Test Script
- Works with Python 3
- Handles permissions properly
- Tests multiple HID devices
- No external API dependencies
"""

import sys
import os
import time
from datetime import datetime



def barcode_reader(device_path):
    """Read barcode from HID device - Python 3 compatible"""
    
    # HID key mapping for normal keys
    hid = {4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j', 14: 'k', 15: 'l', 16: 'm',
           17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y',
           29: 'z', 30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0', 44: ' ',
           45: '-', 46: '=', 47: '[', 48: ']', 49: '\\', 51: ';', 52: '\'', 53: '~', 54: ',', 55: '.', 56: '/'}

    # HID key mapping for shifted keys
    hid2 = {4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J', 14: 'K', 15: 'L', 16: 'M',
            17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S', 23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y',
            29: 'Z', 30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')', 44: ' ',
            45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<', 55: '>', 56: '?'}

    try:
        with open(device_path, 'rb') as fp:
            print(f"📱 Reading from {device_path}")
            print("🔍 Scan a barcode now...")
            print("Press Ctrl+C to stop\n")
            
            ss = ""
            shift = False
            done = False

            while not done:
                # Get the character from the HID
                buffer = fp.read(8)
                
                for byte_val in buffer:
                    # Python 3: byte_val is already an int
                    c = byte_val if isinstance(byte_val, int) else ord(byte_val)
                    
                    if c > 0:
                        # 40 is carriage return which signifies we are done
                        if c == 40:
                            done = True
                            break

                        # Handle shift key
                        if c == 2:
                            shift = True
                        else:
                            # Use appropriate character mapping
                            if shift:
                                if c in hid2:
                                    ss += hid2[c]
                                shift = False
                            else:
                                if c in hid:
                                    ss += hid[c]
            
            return ss.strip()
            
    except Exception as e:
        print(f"❌ Error reading from {device_path}: {e}")
        return None

def display_barcode_info(barcode):
    """Display information about the scanned barcode"""
    if not barcode:
        return
        
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 60)
    print("📊 BARCODE SCANNED SUCCESSFULLY")
    print("=" * 60)
    print(f"📱 Barcode: {barcode}")
    print(f"📏 Length: {len(barcode)} characters")
    print(f"🕒 Time: {timestamp}")
    print(f"🔢 Type: {detect_barcode_type(barcode)}")
    print("=" * 60)

def detect_barcode_type(barcode):
    """Detect barcode type based on length and format"""
    length = len(barcode)
    
    if length == 8 and barcode.isdigit():
        return "EAN-8"
    elif length == 13 and barcode.isdigit():
        return "EAN-13"
    elif length == 12 and barcode.isdigit():
        return "UPC-A"
    elif length in [6, 7, 8] and barcode.isdigit():
        return "UPC-E"
    elif 6 <= length <= 20:
        if barcode.isalnum():
            return "Code 128/Code 39"
        else:
            return "Mixed format"
    else:
        return "Unknown format"

def main():
    """Main function"""
    print("🚀 USB Barcode Scanner Test (Fixed Version)")
    print("=" * 50)
    
    # Check if running as root
    if os.geteuid() != 0:
        print("⚠️ Not running as root - you may need sudo for HID device access")
    
    # Find and test HID devices
    device = test_device_permissions()
    
    if not device:
        print("\n❌ No accessible HID devices found")
        print("💡 Try running with: sudo python3 usb_scanner_fixed.py")
        print("💡 Make sure your USB barcode scanner is connected")
        return False
    
    print(f"\n✅ Using device: {device}")
    
    try:
        scan_count = 0
        while True:
            print(f"\n🔍 Waiting for barcode scan #{scan_count + 1}...")
            barcode = barcode_reader(device)
            
            if barcode:
                scan_count += 1
                display_barcode_info(barcode)
            else:
                print("⚠️ No barcode data received")
                
    except KeyboardInterrupt:
        print(f"\n\n👋 Stopped after {scan_count} successful scans")
        print("✅ Test completed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
