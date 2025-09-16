#!/usr/bin/env python3
"""
Simple USB Barcode Scanner - Direct HID input detection
"""
import sys
import os
import time
import threading
from datetime import datetime

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from barcode_scanner_app import process_barcode_scan_auto

# HID key mapping for barcode scanners
HID_KEY_MAP = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j',
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's', 23: 't',
    24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: '\n',  # Enter key - indicates end of barcode
    44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\', 51: ';', 52: "'", 53: '`',
    54: ',', 55: '.', 56: '/'
}

def find_usb_scanner():
    """Find available HID devices for barcode scanning"""
    devices = []
    for i in range(10):
        device_path = f'/dev/hidraw{i}'
        if os.path.exists(device_path):
            try:
                # Test if we can read from device
                with open(device_path, 'rb') as f:
                    devices.append(device_path)
                    print(f"✅ Found HID device: {device_path}")
            except PermissionError:
                print(f"⚠️ Permission denied: {device_path} (try with sudo)")
                devices.append(device_path)  # Add anyway, will handle permission later
            except Exception as e:
                continue
    return devices

def read_barcode_from_hid(device_path):
    """Read barcode from HID device using simple byte-by-byte processing"""
    print(f"📱 Starting barcode scanner on: {device_path}")
    print("🔍 Ready to scan barcodes...")
    
    try:
        with open(device_path, 'rb') as device:
            barcode = ""
            
            while True:
                try:
                    # Read 8 bytes at a time (standard HID report size)
                    data = device.read(8)
                    if not data:
                        continue
                    
                    # Process each byte
                    for byte in data:
                        if isinstance(byte, str):
                            byte = ord(byte)
                        
                        # Skip modifier keys and empty bytes
                        if byte == 0 or byte == 1 or byte == 2:
                            continue
                        
                        # Check if it's a valid key
                        if byte in HID_KEY_MAP:
                            char = HID_KEY_MAP[byte]
                            
                            if char == '\n':  # Enter key - barcode complete
                                if barcode.strip():
                                    print(f"\n📦 BARCODE SCANNED: {barcode}")
                                    print("=" * 50)
                                    
                                    # Process the barcode
                                    try:
                                        result = process_barcode_scan_auto(barcode.strip())
                                        if result:
                                            print("✅ Barcode sent to IoT Hub successfully!")
                                        else:
                                            print("❌ Failed to send barcode to IoT Hub")
                                    except Exception as e:
                                        print(f"❌ Error processing barcode: {e}")
                                    
                                    print("\n🔍 Ready for next barcode...")
                                    barcode = ""  # Reset for next barcode
                            else:
                                barcode += char
                                print(f"Scanning: {barcode}", end='\r')
                                
                except Exception as e:
                    if "Resource temporarily unavailable" not in str(e):
                        print(f"Read error: {e}")
                    time.sleep(0.01)  # Small delay to prevent CPU spinning
                    
    except PermissionError:
        print(f"❌ Permission denied accessing {device_path}")
        print("💡 Try running with: sudo python3 simple_usb_scanner.py")
    except Exception as e:
        print(f"❌ Error reading from device: {e}")

def main():
    print("🚀 Simple USB Barcode Scanner")
    print("=" * 50)
    
    # Find USB scanners
    devices = find_usb_scanner()
    
    if not devices:
        print("❌ No HID devices found")
        print("💡 Make sure your USB barcode scanner is connected")
        return
    
    # Use the first available device
    device_path = devices[0]
    print(f"🎯 Using device: {device_path}")
    
    try:
        read_barcode_from_hid(device_path)
    except KeyboardInterrupt:
        print("\n🛑 Scanner stopped by user")

if __name__ == "__main__":
    main()
