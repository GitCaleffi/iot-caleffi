#!/usr/bin/env python3
"""
Multi-Approach USB Scanner Test
- Tests multiple methods to capture scanner input
- Works with different scanner types and configurations
"""

import sys
import os
import time
import threading
from datetime import datetime

try:
    import evdev
    from evdev import InputDevice, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

class MultiApproachScanner:
    def __init__(self):
        self.running = False
        self.scan_count = 0
        
    def test_all_input_devices(self):
        """Test all available input devices"""
        if not EVDEV_AVAILABLE:
            print("❌ evdev not available")
            return
            
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        print("🔍 Testing all input devices:")
        for i, device in enumerate(devices):
            print(f"\n{i+1}. Testing: {device.name}")
            
            # Test this device for 5 seconds
            success = self.test_single_device(device, timeout=5)
            if success:
                print(f"✅ Scanner working on: {device.name}")
                return device
            else:
                print(f"⚠️ No response from: {device.name}")
        
        return None
    
    def test_single_device(self, device, timeout=5):
        """Test a single device for scanner input"""
        try:
            print(f"   📱 Monitoring {device.name} for {timeout}s...")
            print(f"   🔍 Scan a barcode now!")
            
            start_time = time.time()
            barcode_buffer = ""
            
            # Set device to non-blocking mode
            device.grab()
            
            while time.time() - start_time < timeout:
                try:
                    events = device.read()
                    for event in events:
                        if event.type == ecodes.EV_KEY and event.value == 1:
                            key_code = event.code
                            
                            # Convert key codes to characters
                            if ecodes.KEY_1 <= key_code <= ecodes.KEY_9:
                                barcode_buffer += str(key_code - ecodes.KEY_1 + 1)
                                print(f"   Got digit: {key_code - ecodes.KEY_1 + 1}")
                            elif key_code == ecodes.KEY_0:
                                barcode_buffer += "0"
                                print(f"   Got digit: 0")
                            elif ecodes.KEY_A <= key_code <= ecodes.KEY_Z:
                                char = chr(ord('a') + key_code - ecodes.KEY_A)
                                barcode_buffer += char
                                print(f"   Got letter: {char}")
                            elif key_code == ecodes.KEY_ENTER:
                                if barcode_buffer.strip():
                                    print(f"   ✅ Complete barcode: {barcode_buffer}")
                                    device.ungrab()
                                    return True
                                barcode_buffer = ""
                            
                            # Show any key activity
                            if barcode_buffer:
                                print(f"   Buffer: {barcode_buffer}")
                                
                except BlockingIOError:
                    time.sleep(0.1)
                    continue
                except Exception as e:
                    break
            
            device.ungrab()
            return len(barcode_buffer) > 0
            
        except Exception as e:
            print(f"   ❌ Error testing device: {e}")
            try:
                device.ungrab()
            except:
                pass
            return False
    
    def test_raw_hid_method(self):
        """Test raw HID device method"""
        print("\n🔧 Testing raw HID method...")
        
        # Find HID devices
        hid_devices = []
        for i in range(10):
            device_path = f"/dev/hidraw{i}"
            if os.path.exists(device_path):
                hid_devices.append(device_path)
        
        if not hid_devices:
            print("❌ No HID devices found")
            return False
        
        print(f"📱 Found HID devices: {hid_devices}")
        
        for device_path in hid_devices:
            print(f"\nTesting {device_path}...")
            if self.test_raw_hid_device(device_path):
                return True
        
        return False
    
    def test_raw_hid_device(self, device_path):
        """Test a single raw HID device"""
        try:
            with open(device_path, 'rb') as fp:
                print(f"   📱 Monitoring {device_path} for 5 seconds...")
                print(f"   🔍 Scan a barcode now!")
                
                start_time = time.time()
                got_data = False
                
                while time.time() - start_time < 5:
                    try:
                        buffer = fp.read(8)
                        if buffer and any(b != 0 for b in buffer):
                            got_data = True
                            non_zero = [b for b in buffer if b != 0]
                            print(f"   Got data: {non_zero}")
                            
                            # Check for Enter key (end of barcode)
                            if 40 in buffer:
                                print(f"   ✅ End of barcode detected")
                                return True
                                
                    except Exception:
                        time.sleep(0.1)
                        continue
                
                return got_data
                
        except PermissionError:
            print(f"   ❌ Permission denied: {device_path}")
            return False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    
    def test_keyboard_input_method(self):
        """Test standard keyboard input method"""
        print("\n⌨️ Testing keyboard input method...")
        print("🔍 Scan a barcode (should appear as typed text):")
        print("Press Enter after scanning, or type 'skip' to skip this test")
        
        try:
            user_input = input("Scan here: ")
            
            if user_input.strip().lower() == 'skip':
                return False
            elif user_input.strip():
                print(f"✅ Received: {user_input}")
                return True
            else:
                print("⚠️ No input received")
                return False
                
        except KeyboardInterrupt:
            print("\n⚠️ Test skipped")
            return False
    
    def run_comprehensive_test(self):
        """Run all scanner detection methods"""
        print("🧪 COMPREHENSIVE USB SCANNER TEST")
        print("=" * 50)
        print("Testing multiple methods to detect your scanner...")
        print("=" * 50)
        
        methods = [
            ("Standard Keyboard Input", self.test_keyboard_input_method),
            ("evdev Input Devices", self.test_all_input_devices),
            ("Raw HID Devices", self.test_raw_hid_method)
        ]
        
        for method_name, method_func in methods:
            print(f"\n🔍 Method: {method_name}")
            print("-" * 30)
            
            try:
                result = method_func()
                if result:
                    print(f"✅ SUCCESS: {method_name} works with your scanner!")
                    return True
                else:
                    print(f"❌ FAILED: {method_name} didn't detect scanner")
            except Exception as e:
                print(f"❌ ERROR in {method_name}: {e}")
        
        print(f"\n❌ No working method found")
        print(f"\n💡 Troubleshooting suggestions:")
        print(f"1. Make sure USB scanner is properly connected")
        print(f"2. Check if scanner needs configuration (scan setup barcodes)")
        print(f"3. Try different USB ports")
        print(f"4. Check scanner manual for keyboard emulation mode")
        print(f"5. Some scanners need drivers or specific software")
        
        return False

def main():
    """Main function"""
    scanner = MultiApproachScanner()
    
    # Check if running with proper permissions
    print(f"🔧 Running as: {'root' if os.geteuid() == 0 else 'user'}")
    
    success = scanner.run_comprehensive_test()
    
    if success:
        print(f"\n🎉 Scanner detection successful!")
    else:
        print(f"\n❌ Scanner detection failed")
        print(f"💡 Try running with: sudo python3 multi_approach_scanner.py")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
