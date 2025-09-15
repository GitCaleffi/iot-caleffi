#!/usr/bin/env python3
"""
Quick USB Scanner Test - Minimal version for fast testing
"""

import sys
import time

try:
    import evdev
    from evdev import InputDevice, ecodes
except ImportError:
    print("Installing evdev...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, ecodes

def find_scanner():
    """Find USB scanner device"""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    
    print("🔍 Available USB devices:")
    for i, device in enumerate(devices):
        print(f"  {i+1}. {device.name}")
        
        # Check for scanner keywords or keyboard capabilities
        name = device.name.lower()
        scanner_words = ['barcode', 'scanner', 'honeywell', 'symbol', 'datalogic', 'zebra', 'hid']
        
        if any(word in name for word in scanner_words):
            print(f"✅ Scanner found: {device.name}")
            return device
            
        # Check keyboard capabilities
        caps = device.capabilities()
        if ecodes.EV_KEY in caps:
            keys = caps[ecodes.EV_KEY]
            if ecodes.KEY_A in keys and ecodes.KEY_ENTER in keys:
                print(f"✅ Keyboard-like device (possible scanner): {device.name}")
                return device
    
    return None

def test_scanner():
    """Test scanner input"""
    scanner = find_scanner()
    
    if not scanner:
        print("❌ No scanner found")
        return
    
    print(f"\n📱 Testing scanner: {scanner.name}")
    print("🔍 Scan a barcode now...")
    print("Press Ctrl+C to stop\n")
    
    barcode = ""
    
    try:
        for event in scanner.read_loop():
            if event.type == ecodes.EV_KEY and event.value == 1:
                key = event.code
                
                # Convert key codes to characters
                if ecodes.KEY_1 <= key <= ecodes.KEY_9:
                    barcode += str(key - ecodes.KEY_1 + 1)
                elif key == ecodes.KEY_0:
                    barcode += "0"
                elif ecodes.KEY_A <= key <= ecodes.KEY_Z:
                    barcode += chr(ord('a') + key - ecodes.KEY_A)
                elif key == ecodes.KEY_ENTER:
                    if barcode:
                        print(f"✅ SCANNED: {barcode}")
                        print(f"📏 Length: {len(barcode)}")
                        barcode = ""
                elif key == ecodes.KEY_SPACE:
                    barcode += " "
                elif key == ecodes.KEY_MINUS:
                    barcode += "-"
                    
    except KeyboardInterrupt:
        print("\n👋 Test stopped")

if __name__ == "__main__":
    print("🧪 Quick USB Scanner Test")
    print("=" * 30)
    test_scanner()
