#!/usr/bin/env python3
"""
Simple USB Barcode Scanner using evdev
- Uses evdev library (more reliable than direct HID access)
- Better device detection and key mapping
- Cleaner barcode output
"""

import sys
import time
from datetime import datetime

try:
    import evdev
    from evdev import InputDevice, ecodes
except ImportError:
    print("Installing evdev...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, ecodes

def find_scanner_device():
    """Find USB barcode scanner using evdev"""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    
    print("🔍 Available input devices:")
    for i, device in enumerate(devices):
        print(f"  {i+1}. {device.name} ({device.path})")
    
    # Look for scanner-like devices
    for device in devices:
        name = device.name.lower()
        
        # Check for scanner keywords
        scanner_words = ['barcode', 'scanner', 'honeywell', 'symbol', 'datalogic', 'zebra', 'pos']
        if any(word in name for word in scanner_words):
            print(f"✅ Found scanner by name: {device.name}")
            return device
        
        # Check for keyboard-like capabilities
        caps = device.capabilities()
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            # Must have letters, numbers, and Enter
            has_letters = any(ecodes.KEY_A + i in keys for i in range(26))
            has_numbers = any(ecodes.KEY_1 + i in keys for i in range(10))
            has_enter = ecodes.KEY_ENTER in keys
            
            if has_letters and has_numbers and has_enter:
                print(f"✅ Found keyboard device (possible scanner): {device.name}")
                return device
    
    print("❌ No suitable scanner device found")
    return None

def read_barcode_evdev(device):
    """Read barcode using evdev (cleaner approach)"""
    print(f"📱 Reading from: {device.name}")
    print("🔍 Scan a barcode now...")
    print("Press Ctrl+C to stop\n")
    
    barcode = ""
    
    try:
        for event in device.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:  # Key press
                key_code = event.code
                
                # Convert key codes to characters
                if ecodes.KEY_0 <= key_code <= ecodes.KEY_9:
                    if key_code == ecodes.KEY_0:
                        barcode += "0"
                    else:
                        barcode += str(key_code - ecodes.KEY_0)
                
                elif ecodes.KEY_A <= key_code <= ecodes.KEY_Z:
                    barcode += chr(ord('a') + key_code - ecodes.KEY_A)
                
                elif key_code == ecodes.KEY_ENTER:
                    # Barcode complete
                    if barcode.strip():
                        return barcode.strip()
                    barcode = ""
                
                elif key_code == ecodes.KEY_SPACE:
                    barcode += " "
                elif key_code == ecodes.KEY_MINUS:
                    barcode += "-"
                elif key_code == ecodes.KEY_DOT:
                    barcode += "."
                elif key_code == ecodes.KEY_SLASH:
                    barcode += "/"
                
    except Exception as e:
        print(f"❌ Error reading barcode: {e}")
        return None

def display_barcode_result(barcode, scan_number):
    """Display barcode scan results"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 60)
    print(f"📊 SCAN #{scan_number} SUCCESSFUL")
    print("=" * 60)
    print(f"📱 Barcode: {barcode}")
    print(f"📏 Length: {len(barcode)} characters")
    print(f"🕒 Time: {timestamp}")
    print(f"🔢 Format: {detect_barcode_format(barcode)}")
    print("=" * 60)

def detect_barcode_format(barcode):
    """Detect barcode format"""
    length = len(barcode)
    
    if length == 13 and barcode.isdigit():
        return "EAN-13"
    elif length == 12 and barcode.isdigit():
        return "UPC-A"
    elif length == 8 and barcode.isdigit():
        return "EAN-8"
    elif length in [6, 7] and barcode.isdigit():
        return "UPC-E"
    elif barcode.isdigit():
        return f"Numeric ({length} digits)"
    elif barcode.isalnum():
        return f"Alphanumeric ({length} chars)"
    else:
        return f"Mixed format ({length} chars)"

def main():
    """Main function"""
    print("🚀 Simple USB Barcode Scanner (evdev)")
    print("=" * 50)
    
    # Find scanner device
    device = find_scanner_device()
    if not device:
        print("\n💡 Tips:")
        print("1. Make sure USB scanner is connected")
        print("2. Scanner should be in 'keyboard emulation' mode")
        print("3. Try running with sudo if permission issues")
        return False
    
    print(f"\n✅ Using device: {device.name}")
    
    scan_count = 0
    
    try:
        while True:
            print(f"\n🔍 Ready for scan #{scan_count + 1}...")
            barcode = read_barcode_evdev(device)
            
            if barcode:
                scan_count += 1
                display_barcode_result(barcode, scan_count)
            else:
                print("⚠️ No barcode received or scan cancelled")
                break
                
    except KeyboardInterrupt:
        print(f"\n\n👋 Stopped after {scan_count} successful scans")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False
    
    print("✅ Scanner test completed")
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
