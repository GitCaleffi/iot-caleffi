#!/usr/bin/env python3
"""
USB Device Selector for POS Integration
Helps identify and select USB devices to send barcode strings to
"""

import os
import subprocess
import glob
from pathlib import Path

def list_usb_devices():
    """List all connected USB devices"""
    print("🔌 Connected USB Devices:")
    print("=" * 50)
    
    try:
        # Get USB device list
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            for i, line in enumerate(lines, 1):
                print(f"{i:2d}. {line}")
        else:
            print("❌ Could not list USB devices")
    except Exception as e:
        print(f"❌ Error listing USB devices: {e}")

def list_hid_devices():
    """List HID (Human Interface Device) devices"""
    print("\n🖱️ HID Devices (Keyboards, Mice, etc.):")
    print("=" * 50)
    
    hid_devices = glob.glob('/dev/hidraw*')
    if hid_devices:
        for i, device in enumerate(sorted(hid_devices), 1):
            try:
                # Get device info
                device_path = Path(device)
                stat_info = device_path.stat()
                print(f"{i:2d}. {device}")
                
                # Try to get device name from udev
                try:
                    result = subprocess.run(['udevadm', 'info', '--name=' + device], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'ID_MODEL=' in line:
                                model = line.split('=')[1].strip('"')
                                print(f"    📱 Model: {model}")
                            elif 'ID_VENDOR=' in line:
                                vendor = line.split('=')[1].strip('"')
                                print(f"    🏢 Vendor: {vendor}")
                except:
                    pass
                    
            except Exception as e:
                print(f"    ❌ Error reading {device}: {e}")
    else:
        print("❌ No HID devices found")

def list_serial_devices():
    """List serial devices"""
    print("\n📡 Serial Devices:")
    print("=" * 50)
    
    serial_patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']
    serial_devices = []
    
    for pattern in serial_patterns:
        serial_devices.extend(glob.glob(pattern))
    
    if serial_devices:
        for i, device in enumerate(sorted(serial_devices), 1):
            print(f"{i:2d}. {device}")
            
            # Try to get device info
            try:
                result = subprocess.run(['udevadm', 'info', '--name=' + device], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'ID_MODEL=' in line:
                            model = line.split('=')[1].strip('"')
                            print(f"    📱 Model: {model}")
                        elif 'ID_VENDOR=' in line:
                            vendor = line.split('=')[1].strip('"')
                            print(f"    🏢 Vendor: {vendor}")
            except:
                pass
    else:
        print("❌ No serial devices found")

def test_hid_device(device_path):
    """Test sending data to a HID device"""
    print(f"\n🧪 Testing HID device: {device_path}")
    print("=" * 50)
    
    try:
        # Test if device is writable
        if os.access(device_path, os.W_OK):
            print("✅ Device is writable")
            
            # Try to send test data
            test_string = "TEST123\n"
            with open(device_path, 'wb') as f:
                f.write(test_string.encode())
            print(f"✅ Sent test string: {test_string.strip()}")
            print("   → Check if this appeared on connected device!")
            return True
        else:
            print("❌ Device is not writable (try with sudo)")
            return False
            
    except Exception as e:
        print(f"❌ Error testing device: {e}")
        return False

def test_serial_device(device_path, baud_rate=9600):
    """Test sending data to a serial device"""
    print(f"\n🧪 Testing Serial device: {device_path} @ {baud_rate} baud")
    print("=" * 50)
    
    try:
        import serial
        with serial.Serial(device_path, baud_rate, timeout=1) as ser:
            test_string = "SERIAL_TEST_123\r\n"
            ser.write(test_string.encode())
            print(f"✅ Sent test string: {test_string.strip()}")
            print("   → Check if this appeared on connected device!")
            return True
    except ImportError:
        print("❌ pyserial not installed. Install with: pip install pyserial")
        return False
    except Exception as e:
        print(f"❌ Error testing device: {e}")
        return False

def interactive_device_selection():
    """Interactive device selection and testing"""
    print("\n🎯 Interactive Device Selection")
    print("=" * 50)
    
    # Get all available devices
    hid_devices = sorted(glob.glob('/dev/hidraw*'))
    serial_devices = []
    for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']:
        serial_devices.extend(glob.glob(pattern))
    serial_devices = sorted(serial_devices)
    
    all_devices = []
    device_types = []
    
    # Add HID devices
    for device in hid_devices:
        all_devices.append(device)
        device_types.append('HID')
    
    # Add Serial devices
    for device in serial_devices:
        all_devices.append(device)
        device_types.append('SERIAL')
    
    if not all_devices:
        print("❌ No testable devices found")
        return
    
    print("Available devices for testing:")
    for i, (device, dev_type) in enumerate(zip(all_devices, device_types), 1):
        print(f"{i:2d}. [{dev_type:6}] {device}")
    
    try:
        choice = input(f"\nSelect device to test (1-{len(all_devices)}) or 'q' to quit: ")
        if choice.lower() == 'q':
            return
        
        device_index = int(choice) - 1
        if 0 <= device_index < len(all_devices):
            selected_device = all_devices[device_index]
            selected_type = device_types[device_index]
            
            print(f"\n🎯 Selected: {selected_device} ({selected_type})")
            
            if selected_type == 'HID':
                success = test_hid_device(selected_device)
            else:  # SERIAL
                success = test_serial_device(selected_device)
            
            if success:
                print(f"\n✅ Device {selected_device} is working!")
                print("💡 To use this device in your barcode scanner:")
                print(f"   - Device path: {selected_device}")
                print(f"   - Device type: {selected_type}")
                
                # Generate code snippet
                if selected_type == 'HID':
                    print(f"\n📝 Code to send barcode to this device:")
                    print(f"   with open('{selected_device}', 'wb') as f:")
                    print(f"       f.write(barcode.encode() + b'\\n')")
                else:
                    print(f"\n📝 Code to send barcode to this device:")
                    print(f"   import serial")
                    print(f"   with serial.Serial('{selected_device}', 9600) as ser:")
                    print(f"       ser.write(barcode.encode() + b'\\r\\n')")
            else:
                print(f"\n❌ Device {selected_device} test failed")
        else:
            print("❌ Invalid selection")
            
    except ValueError:
        print("❌ Invalid input")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

def main():
    print("🔌 USB Device Selector for POS Integration")
    print("=" * 60)
    print("This tool helps you identify and test USB devices for barcode forwarding")
    print()
    
    # List all devices
    list_usb_devices()
    list_hid_devices()
    list_serial_devices()
    
    # Interactive selection
    interactive_device_selection()

if __name__ == "__main__":
    main()
