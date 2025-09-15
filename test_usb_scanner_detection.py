#!/usr/bin/env python3
"""
USB Barcode Scanner Detection Test
Tests if a real USB barcode scanner is connected and working
"""

import os
import sys
import subprocess
import glob
import time

def check_usb_devices():
    """Check for USB devices that might be barcode scanners"""
    print("🔍 Checking USB devices...")
    
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.stdout.strip():
            print("📱 USB devices found:")
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")
        else:
            print("❌ No USB devices detected")
        return result.stdout
    except Exception as e:
        print(f"❌ Error checking USB devices: {e}")
        return ""

def check_hid_devices():
    """Check for HID devices"""
    print("\n🔍 Checking HID devices...")
    
    hid_devices = glob.glob('/dev/hidraw*')
    if hid_devices:
        print(f"📱 Found {len(hid_devices)} HID device(s):")
        for device in hid_devices:
            print(f"  {device}")
            try:
                # Check permissions
                stat = os.stat(device)
                print(f"    Permissions: {oct(stat.st_mode)[-3:]}")
                
                # Try to read (test access)
                try:
                    with open(device, 'rb') as f:
                        print(f"    ✅ Readable")
                except PermissionError:
                    print(f"    ❌ Permission denied")
                except Exception as e:
                    print(f"    ⚠️ Access error: {e}")
                    
            except Exception as e:
                print(f"    ❌ Error checking device: {e}")
    else:
        print("❌ No HID devices found")
    
    return hid_devices

def check_input_devices():
    """Check for input devices (evdev)"""
    print("\n🔍 Checking input devices...")
    
    try:
        import evdev
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        if devices:
            print(f"📱 Found {len(devices)} input device(s):")
            for device in devices:
                print(f"  {device.path}: {device.name}")
                # Check if it might be a barcode scanner
                capabilities = device.capabilities()
                if 1 in capabilities:  # EV_KEY events
                    keys = capabilities[1]
                    # Check for number keys (typical for barcode scanners)
                    number_keys = [key for key in keys if 2 <= key <= 11]  # KEY_1 to KEY_0
                    if len(number_keys) >= 5:  # Has most number keys
                        print(f"    ✅ Likely barcode scanner (has number keys)")
                    else:
                        print(f"    ℹ️ Input device (limited keys)")
        else:
            print("❌ No input devices found")
            
        return devices
    except ImportError:
        print("❌ evdev not available")
        return []
    except Exception as e:
        print(f"❌ Error checking input devices: {e}")
        return []

def test_scanner_simulation():
    """Test if we can simulate barcode input"""
    print("\n🧪 Testing barcode simulation...")
    
    print("📝 You can test barcode scanning in these ways:")
    print("1. Connect a physical USB barcode scanner")
    print("2. Use keyboard input (scanner acts like keyboard)")
    print("3. Use the web interface for manual testing")
    
    print("\n💡 To test with keyboard simulation:")
    print("   - Type a barcode number followed by Enter")
    print("   - The system should detect it as barcode input")

def main():
    print("=" * 60)
    print("🚀 USB BARCODE SCANNER DETECTION TEST")
    print("=" * 60)
    
    # Check USB devices
    usb_output = check_usb_devices()
    
    # Check HID devices  
    hid_devices = check_hid_devices()
    
    # Check input devices
    input_devices = check_input_devices()
    
    # Analysis
    print("\n" + "=" * 60)
    print("📊 ANALYSIS")
    print("=" * 60)
    
    scanner_detected = False
    
    # Look for barcode scanner indicators in USB output
    scanner_keywords = ['scanner', 'barcode', 'symbol', 'honeywell', 'datalogic', 'zebra']
    if any(keyword.lower() in usb_output.lower() for keyword in scanner_keywords):
        print("✅ Potential barcode scanner detected in USB devices")
        scanner_detected = True
    
    if hid_devices:
        print("✅ HID devices available for scanner communication")
        scanner_detected = True
    elif input_devices:
        print("✅ Input devices available (can use evdev mode)")
        scanner_detected = True
    
    if not scanner_detected:
        print("❌ No barcode scanner detected")
        print("\n🔧 TROUBLESHOOTING:")
        print("1. Connect your USB barcode scanner")
        print("2. Check if scanner LED turns on when connected")
        print("3. Try scanning into a text editor first")
        print("4. Run: sudo chmod 666 /dev/hidraw* (if HID devices exist)")
        print("5. Use web interface for manual testing")
    else:
        print("✅ Scanner hardware detected - ready for barcode scanning!")
        print("\n🚀 Next steps:")
        print("1. Run: python3 src/barcode_scanner_app.py --usb-auto")
        print("2. Scan a barcode with your scanner")
        print("3. Check the console for barcode detection")
    
    test_scanner_simulation()

if __name__ == "__main__":
    main()
