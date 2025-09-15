#!/usr/bin/env python3
"""
Raspberry Pi USB Scanner Test
- Specifically designed for Pi USB scanner issues
- Tests direct device access and permissions
"""

import sys
import os
import time
import select

try:
    import evdev
    from evdev import InputDevice, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

def test_device_permissions():
    """Check device permissions and access"""
    print("🔍 Checking device permissions...")
    
    # Check input devices
    input_devices = []
    try:
        for path in evdev.list_devices():
            device = evdev.InputDevice(path)
            print(f"  📱 {device.name} - {path}")
            input_devices.append((device.name, path))
    except Exception as e:
        print(f"❌ Error listing devices: {e}")
    
    # Check HID devices
    hid_devices = []
    for i in range(10):
        hid_path = f"/dev/hidraw{i}"
        if os.path.exists(hid_path):
            try:
                with open(hid_path, 'rb') as f:
                    hid_devices.append(hid_path)
                    print(f"  ✅ Can access {hid_path}")
            except PermissionError:
                print(f"  ❌ Permission denied: {hid_path}")
            except Exception as e:
                print(f"  ⚠️ Error with {hid_path}: {e}")
    
    return input_devices, hid_devices

def test_scanner_direct_input():
    """Test scanner as direct keyboard input"""
    print("\n⌨️ Testing direct keyboard input...")
    print("🔍 Point scanner at barcode and pull trigger")
    print("If working, barcode should appear as you type")
    print("Type 'test' and press Enter, or scan a barcode:")
    
    try:
        # Use select to check if input is available
        if select.select([sys.stdin], [], [], 10):  # 10 second timeout
            barcode = input().strip()
            if barcode and barcode != 'test':
                print(f"✅ Scanner input detected: {barcode}")
                return True
            elif barcode == 'test':
                print("⚠️ Manual input detected, not scanner")
                return False
        else:
            print("⏰ Timeout - no input detected")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_usb_adapter_device():
    """Specifically test the USB Adapter device"""
    if not EVDEV_AVAILABLE:
        print("❌ evdev not available")
        return False
    
    print("\n🔍 Looking for USB Adapter device...")
    
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    usb_adapter = None
    
    for device in devices:
        if "USB Adapter" in device.name:
            usb_adapter = device
            print(f"✅ Found: {device.name}")
            break
    
    if not usb_adapter:
        print("❌ USB Adapter device not found")
        return False
    
    print(f"📱 Testing {usb_adapter.name}...")
    print("🔍 Scan a barcode now (10 second timeout)...")
    
    try:
        # Grab the device exclusively
        usb_adapter.grab()
        
        start_time = time.time()
        barcode_buffer = ""
        got_input = False
        
        while time.time() - start_time < 10:
            try:
                # Read events with timeout
                events = usb_adapter.read()
                
                for event in events:
                    got_input = True
                    print(f"Event: type={event.type}, code={event.code}, value={event.value}")
                    
                    if event.type == ecodes.EV_KEY and event.value == 1:
                        key_code = event.code
                        
                        # Map key codes
                        if ecodes.KEY_1 <= key_code <= ecodes.KEY_9:
                            digit = str(key_code - ecodes.KEY_1 + 1)
                            barcode_buffer += digit
                            print(f"Digit: {digit}")
                        elif key_code == ecodes.KEY_0:
                            barcode_buffer += "0"
                            print(f"Digit: 0")
                        elif ecodes.KEY_A <= key_code <= ecodes.KEY_Z:
                            letter = chr(ord('a') + key_code - ecodes.KEY_A)
                            barcode_buffer += letter
                            print(f"Letter: {letter}")
                        elif key_code == ecodes.KEY_ENTER:
                            print(f"Enter key - barcode complete")
                            if barcode_buffer:
                                print(f"✅ Complete barcode: {barcode_buffer}")
                                usb_adapter.ungrab()
                                return True
                        
                        print(f"Current buffer: {barcode_buffer}")
                        
            except BlockingIOError:
                time.sleep(0.1)
                continue
            except Exception as e:
                print(f"Read error: {e}")
                break
        
        usb_adapter.ungrab()
        
        if got_input:
            print(f"⚠️ Got input events but no complete barcode")
            if barcode_buffer:
                print(f"Partial buffer: {barcode_buffer}")
            return True
        else:
            print(f"❌ No input events detected")
            return False
            
    except Exception as e:
        print(f"❌ Error testing USB Adapter: {e}")
        try:
            usb_adapter.ungrab()
        except:
            pass
        return False

def check_scanner_configuration():
    """Check common scanner configuration issues"""
    print("\n🔧 Scanner Configuration Check:")
    print("=" * 40)
    
    print("💡 Common USB scanner issues on Raspberry Pi:")
    print("1. Scanner not in keyboard emulation mode")
    print("2. Scanner needs configuration barcode scan")
    print("3. USB power issues (try powered USB hub)")
    print("4. Driver/permission issues")
    print("5. Scanner in wrong mode (HID vs Serial)")
    
    print("\n📋 Try these steps:")
    print("1. Unplug and reconnect USB scanner")
    print("2. Try different USB port")
    print("3. Check scanner manual for setup barcodes")
    print("4. Scan 'Enable Keyboard Mode' barcode if available")
    print("5. Check if scanner LED lights up when scanning")

def main():
    """Main test function"""
    print("🧪 RASPBERRY PI USB SCANNER TEST")
    print("=" * 50)
    
    # Check permissions
    if os.geteuid() == 0:
        print("✅ Running as root - full device access")
    else:
        print("⚠️ Running as user - may need sudo for some tests")
    
    # Test device permissions
    input_devices, hid_devices = test_device_permissions()
    
    # Test direct keyboard input
    keyboard_works = test_direct_input()
    
    # Test USB Adapter device specifically
    usb_adapter_works = test_usb_adapter_device()
    
    # Show configuration help
    check_scanner_configuration()
    
    print(f"\n📊 TEST RESULTS:")
    print(f"=" * 30)
    print(f"Direct keyboard input: {'✅' if keyboard_works else '❌'}")
    print(f"USB Adapter device: {'✅' if usb_adapter_works else '❌'}")
    print(f"Input devices found: {len(input_devices)}")
    print(f"HID devices accessible: {len(hid_devices)}")
    
    if keyboard_works or usb_adapter_works:
        print(f"\n🎉 Scanner is working!")
        return True
    else:
        print(f"\n❌ Scanner not responding")
        print(f"💡 Try the configuration steps above")
        return False

def test_direct_input():
    """Simple direct input test"""
    print("\n⌨️ Direct Input Test")
    print("Scan a barcode or type 'skip':")
    
    try:
        result = input("Input: ").strip()
        if result and result != 'skip':
            print(f"✅ Got input: {result}")
            return True
        return False
    except:
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
