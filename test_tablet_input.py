#!/usr/bin/env python3
"""
Test tablet/barcode scanner input detection
"""

import evdev
import time
import sys

def test_tablet_input():
    """Test if tablet is sending barcode input"""
    
    print("🔍 Testing Tablet/Barcode Scanner Input")
    print("=" * 45)
    
    # Find input devices
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    
    print(f"📱 Found {len(devices)} input devices:")
    for device in devices:
        print(f"  - {device.path}: {device.name}")
    
    # Look for USB barcode scanner
    scanner_device = None
    for device in devices:
        if 'USB' in device.name and ('Adapter' in device.name or 'Device' in device.name):
            scanner_device = device
            print(f"🎯 Found barcode scanner: {device.path} - {device.name}")
            break
    
    if not scanner_device:
        print("❌ No USB barcode scanner device found")
        return False
    
    print(f"\n🔍 Monitoring {scanner_device.path} for input...")
    print("📱 Please scan a barcode now (waiting 30 seconds)...")
    
    # Monitor for input
    start_time = time.time()
    barcode_chars = []
    
    try:
        scanner_device.grab()  # Exclusive access
        
        for event in scanner_device.read_loop():
            if time.time() - start_time > 30:  # 30 second timeout
                break
                
            if event.type == evdev.ecodes.EV_KEY:
                key_event = evdev.categorize(event)
                if key_event.keystate == evdev.KeyEvent.key_down:
                    # Map key codes to characters
                    key_code = key_event.scancode
                    
                    # Basic key mapping
                    key_map = {
                        2: '1', 3: '2', 4: '3', 5: '4', 6: '5',
                        7: '6', 8: '7', 9: '8', 10: '9', 11: '0',
                        28: '\n'  # Enter key
                    }
                    
                    if key_code in key_map:
                        char = key_map[key_code]
                        if char == '\n':
                            # End of barcode
                            barcode = ''.join(barcode_chars)
                            print(f"✅ Barcode detected: {barcode}")
                            return True
                        else:
                            barcode_chars.append(char)
                            print(f"📝 Character: {char} (total: {''.join(barcode_chars)})")
    
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            scanner_device.ungrab()
        except:
            pass
    
    print("⏰ Test timeout - no barcode detected")
    return False

if __name__ == "__main__":
    success = test_tablet_input()
    if success:
        print("\n✅ Your tablet/scanner is working!")
        print("💡 Now scan a barcode in the main system to register device")
    else:
        print("\n❌ No input detected from tablet/scanner")
        print("🔧 Check USB connection and try scanning again")
