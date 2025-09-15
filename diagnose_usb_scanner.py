#!/usr/bin/env python3
"""
USB Scanner Diagnostic Tool
- Tests all available HID devices
- Shows raw HID data
- Helps identify correct device and mapping
"""

import sys
import os
import time
from datetime import datetime

def find_all_input_devices():
    """Find all possible input devices"""
    devices = []
    
    # Check HID raw devices
    for i in range(10):
        device_path = f"/dev/hidraw{i}"
        if os.path.exists(device_path):
            devices.append(('hidraw', device_path))
    
    # Check input event devices
    for i in range(20):
        device_path = f"/dev/input/event{i}"
        if os.path.exists(device_path):
            devices.append(('input', device_path))
    
    return devices

def test_raw_hid_data(device_path, timeout=10):
    """Read and display raw HID data"""
    print(f"\n🔍 Testing {device_path}")
    print("📱 Scan a barcode now (waiting 10 seconds)...")
    
    try:
        with open(device_path, 'rb') as fp:
            start_time = time.time()
            raw_data = []
            
            while time.time() - start_time < timeout:
                try:
                    buffer = fp.read(8)
                    if buffer and any(b != 0 for b in buffer):
                        raw_data.append(buffer)
                        print(f"Raw bytes: {[hex(b) for b in buffer]}")
                        
                        # Check for Enter key (usually indicates end of barcode)
                        if 40 in buffer:  # Enter key
                            break
                            
                except Exception as e:
                    break
            
            if raw_data:
                print(f"✅ Got {len(raw_data)} data packets from {device_path}")
                return raw_data
            else:
                print(f"⚠️ No data received from {device_path}")
                return None
                
    except Exception as e:
        print(f"❌ Error reading {device_path}: {e}")
        return None

def analyze_hid_data(raw_data):
    """Analyze raw HID data to understand the format"""
    if not raw_data:
        return
    
    print("\n📊 HID Data Analysis:")
    print("=" * 40)
    
    all_bytes = []
    for packet in raw_data:
        for byte_val in packet:
            if byte_val != 0:
                all_bytes.append(byte_val)
    
    print(f"Non-zero bytes: {all_bytes}")
    print(f"Hex values: {[hex(b) for b in all_bytes]}")
    
    # Check for common patterns
    if 40 in all_bytes:
        print("✅ Found Enter key (40) - typical for barcode scanners")
    
    if 2 in all_bytes:
        print("✅ Found Shift key (2) - scanner uses shifted characters")
    
    # Check for number range (30-39 = keys 1-0)
    numbers = [b for b in all_bytes if 30 <= b <= 39]
    if numbers:
        print(f"✅ Found number keys: {numbers} -> {''.join([str(b-29) if b != 39 else '0' for b in numbers])}")
    
    # Check for letter range (4-29 = keys a-z)
    letters = [b for b in all_bytes if 4 <= b <= 29]
    if letters:
        letter_chars = [chr(ord('a') + b - 4) for b in letters]
        print(f"✅ Found letter keys: {letters} -> {''.join(letter_chars)}")

def test_evdev_approach():
    """Test using evdev library as alternative"""
    try:
        import evdev
        from evdev import InputDevice, ecodes
        
        print("\n🔍 Testing evdev approach...")
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        for device in devices:
            print(f"📱 Device: {device.name} at {device.path}")
            
            # Check capabilities
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                if ecodes.KEY_A in keys and ecodes.KEY_ENTER in keys:
                    print(f"✅ Keyboard-like device found: {device.name}")
                    return device
        
        return None
        
    except ImportError:
        print("⚠️ evdev not available")
        return None

def main():
    """Main diagnostic function"""
    print("🔧 USB Scanner Diagnostic Tool")
    print("=" * 50)
    
    # Check permissions
    if os.geteuid() != 0:
        print("⚠️ Running without root - some devices may not be accessible")
    
    # Find all devices
    devices = find_all_input_devices()
    print(f"\n📱 Found {len(devices)} input devices:")
    for dev_type, path in devices:
        print(f"  {dev_type}: {path}")
    
    # Test each HID device
    print(f"\n🧪 Testing HID devices...")
    for dev_type, device_path in devices:
        if dev_type == 'hidraw':
            raw_data = test_raw_hid_data(device_path)
            if raw_data:
                analyze_hid_data(raw_data)
                print(f"\n✅ {device_path} appears to be your barcode scanner!")
                break
    
    # Test evdev approach
    evdev_device = test_evdev_approach()
    if evdev_device:
        print(f"💡 Alternative: Try evdev with {evdev_device.name}")
    
    print(f"\n📋 Recommendations:")
    print(f"1. If you got clean number/letter data above, that's your correct device")
    print(f"2. Try different /dev/hidraw* devices if the first one doesn't work")
    print(f"3. Make sure scanner is in 'keyboard emulation' mode")
    print(f"4. Some scanners need specific configuration to work properly")

if __name__ == '__main__':
    main()
