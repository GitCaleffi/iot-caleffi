#!/usr/bin/env python3
"""
Configure USB POS Device for Barcode Scanner
Helps configure which USB device to send barcodes to
"""

import json
import os
import glob
from pathlib import Path

def get_available_devices():
    """Get all available USB devices for POS forwarding"""
    devices = {
        'hid': sorted(glob.glob('/dev/hidraw*')),
        'serial': []
    }
    
    # Add serial devices
    for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']:
        devices['serial'].extend(glob.glob(pattern))
    devices['serial'] = sorted(devices['serial'])
    
    return devices

def create_pos_config(selected_device, device_type):
    """Create POS configuration for the barcode scanner"""
    config = {
        "pos_forwarding": {
            "enabled": True,
            "primary_device": {
                "path": selected_device,
                "type": device_type,
                "baud_rate": 9600 if device_type == "serial" else None
            },
            "methods": {
                "hid": device_type == "hid",
                "serial": device_type == "serial",
                "network": False,
                "file": True
            }
        }
    }
    
    # Save to config file
    config_path = "pos_device_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ POS configuration saved to: {config_path}")
    return config_path

def test_device_connection(device_path, device_type):
    """Test connection to selected device"""
    print(f"\n🧪 Testing connection to {device_path}...")
    
    try:
        if device_type == "hid":
            # Test HID device
            test_data = "USB_TEST_123\n"
            with open(device_path, 'w') as f:
                f.write(test_data)
            print("✅ HID test successful!")
            print("   → Check if 'USB_TEST_123' appeared on your POS device")
            
        elif device_type == "serial":
            # Test serial device
            try:
                import serial
                with serial.Serial(device_path, 9600, timeout=1) as ser:
                    test_data = "SERIAL_TEST_123\r\n"
                    ser.write(test_data.encode())
                print("✅ Serial test successful!")
                print("   → Check if 'SERIAL_TEST_123' appeared on your POS device")
            except ImportError:
                print("❌ pyserial not installed. Install with: pip install pyserial")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("🔌 Configure USB POS Device")
    print("=" * 40)
    print("This will help you select which USB device to send barcodes to")
    print()
    
    # Get available devices
    devices = get_available_devices()
    all_devices = []
    device_info = []
    
    # List HID devices
    if devices['hid']:
        print("🖱️ Available HID Devices (Keyboards, Mice, POS terminals):")
        for i, device in enumerate(devices['hid'], 1):
            print(f"  {len(all_devices) + 1}. {device}")
            all_devices.append(device)
            device_info.append(('hid', device))
    
    # List Serial devices  
    if devices['serial']:
        print("\n📡 Available Serial Devices:")
        for i, device in enumerate(devices['serial'], 1):
            print(f"  {len(all_devices) + 1}. {device}")
            all_devices.append(device)
            device_info.append(('serial', device))
    
    if not all_devices:
        print("❌ No USB devices found for POS forwarding")
        print("💡 Make sure your POS device is connected via USB")
        return
    
    print(f"\n🎯 Found {len(all_devices)} device(s)")
    
    # Device selection
    try:
        choice = input(f"\nSelect device (1-{len(all_devices)}) or 'q' to quit: ")
        if choice.lower() == 'q':
            return
        
        device_index = int(choice) - 1
        if 0 <= device_index < len(all_devices):
            device_type, selected_device = device_info[device_index]
            
            print(f"\n✅ Selected: {selected_device} ({device_type.upper()})")
            
            # Test the device
            if test_device_connection(selected_device, device_type):
                # Create configuration
                config_path = create_pos_config(selected_device, device_type)
                
                print(f"\n🎉 Configuration Complete!")
                print(f"📁 Config file: {config_path}")
                print(f"🔌 POS Device: {selected_device}")
                print(f"📱 Device Type: {device_type.upper()}")
                
                print(f"\n📋 Next Steps:")
                print(f"1. Copy this config to your Raspberry Pi")
                print(f"2. Update your barcode scanner to use this device")
                print(f"3. Test with: python3 keyboard_scanner.py")
                
                # Show integration code
                print(f"\n💻 Integration Code:")
                if device_type == "hid":
                    print(f"   # Send barcode to HID device")
                    print(f"   with open('{selected_device}', 'w') as f:")
                    print(f"       f.write(barcode + '\\n')")
                else:
                    print(f"   # Send barcode to Serial device")
                    print(f"   import serial")
                    print(f"   with serial.Serial('{selected_device}', 9600) as ser:")
                    print(f"       ser.write(barcode.encode() + b'\\r\\n')")
            
        else:
            print("❌ Invalid selection")
            
    except ValueError:
        print("❌ Please enter a valid number")
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
