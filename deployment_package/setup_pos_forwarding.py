#!/usr/bin/env python3
"""
POS Device Setup and Detection Script
Automatically detects attached devices and configures barcode forwarding
"""

import os
import sys
import glob
import time
import subprocess
from pathlib import Path

def detect_attached_devices():
    """Detect all attached USB devices that could be POS terminals"""
    print("🔍 Detecting attached devices...")
    
    devices = {
        'serial_ports': [],
        'usb_devices': [],
        'hid_devices': [],
        'network_devices': []
    }
    
    # 1. Serial ports (USB-to-Serial, direct serial)
    serial_patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']
    for pattern in serial_patterns:
        devices['serial_ports'].extend(glob.glob(pattern))
    
    # 2. USB devices
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            usb_lines = result.stdout.strip().split('\n')
            devices['usb_devices'] = [line for line in usb_lines if line.strip()]
    except:
        pass
    
    # 3. HID devices
    hid_patterns = ['/dev/hidraw*', '/dev/input/event*']
    for pattern in hid_patterns:
        devices['hid_devices'].extend(glob.glob(pattern))
    
    # 4. Network devices (scan for common POS IPs)
    common_pos_ips = [
        '192.168.1.100', '192.168.1.10', '192.168.1.20',
        '192.168.0.100', '192.168.0.10', '10.0.0.100'
    ]
    
    for ip in common_pos_ips:
        try:
            result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0:
                devices['network_devices'].append(ip)
        except:
            continue
    
    return devices

def setup_usb_hid_gadget():
    """Setup USB HID gadget mode for Pi to act as keyboard"""
    print("🔧 Setting up USB HID gadget mode...")
    
    # Check if we're on Raspberry Pi
    try:
        with open('/proc/cpuinfo', 'r') as f:
            if 'Raspberry Pi' not in f.read():
                print("⚠️ Not on Raspberry Pi - USB HID gadget not available")
                return False
    except:
        print("⚠️ Cannot detect Pi hardware")
        return False
    
    # Check if USB gadget is already configured
    if os.path.exists('/dev/hidg0'):
        print("✅ USB HID gadget already configured")
        return True
    
    # Create setup script
    setup_script = """#!/bin/bash
# USB HID Gadget Setup for Raspberry Pi
echo "Setting up USB HID gadget..."

# Load required modules
modprobe libcomposite

# Create gadget directory
cd /sys/kernel/config/usb_gadget/
mkdir -p g1
cd g1

# Configure gadget
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice # v1.0.0
echo 0x0200 > bcdUSB    # USB2

# Create strings
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Caleffi" > strings/0x409/manufacturer
echo "Barcode Scanner HID" > strings/0x409/product

# Create configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: ECM network" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Create HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# HID report descriptor for keyboard
echo -ne '\\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0' > functions/hid.usb0/report_desc

# Link function to configuration
ln -s functions/hid.usb0 configs/c.1/

# Enable gadget
ls /sys/class/udc > UDC

echo "USB HID gadget setup complete"
"""
    
    # Write and execute setup script
    script_path = '/tmp/setup_hid_gadget.sh'
    with open(script_path, 'w') as f:
        f.write(setup_script)
    
    os.chmod(script_path, 0o755)
    
    try:
        result = subprocess.run(['sudo', script_path], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ USB HID gadget setup successful")
            return True
        else:
            print(f"❌ USB HID gadget setup failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error setting up USB HID gadget: {e}")
        return False

def test_serial_forwarding(devices):
    """Test serial port forwarding to attached devices"""
    print("📡 Testing serial port forwarding...")
    
    if not devices['serial_ports']:
        print("⚠️ No serial ports found")
        return False
    
    try:
        import serial
    except ImportError:
        print("❌ PySerial not installed. Install with: pip install pyserial")
        return False
    
    working_ports = []
    test_barcode = "TEST123456789"
    
    for port in devices['serial_ports']:
        try:
            print(f"  Testing {port}...")
            with serial.Serial(port, 9600, timeout=2) as ser:
                ser.write(f"{test_barcode}\r\n".encode())
                ser.flush()
                print(f"  ✅ {port} - Barcode sent successfully")
                working_ports.append(port)
        except Exception as e:
            print(f"  ❌ {port} - Failed: {e}")
    
    return working_ports

def create_pos_config(devices, working_ports):
    """Create POS configuration file"""
    config = {
        'detected_devices': devices,
        'working_serial_ports': working_ports,
        'forwarding_methods': [],
        'setup_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Determine available methods
    if os.path.exists('/dev/hidg0'):
        config['forwarding_methods'].append('USB_HID')
    
    if working_ports:
        config['forwarding_methods'].append('SERIAL')
    
    if devices['network_devices']:
        config['forwarding_methods'].append('NETWORK')
    
    # Always available
    config['forwarding_methods'].extend(['CLIPBOARD', 'FILE'])
    
    # Write config
    import json
    config_path = '/tmp/pos_device_config.json'
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"📄 POS configuration saved to: {config_path}")
    return config

def main():
    print("🔧 POS Device Setup and Configuration")
    print("=" * 50)
    
    # 1. Detect attached devices
    devices = detect_attached_devices()
    
    print("\n📊 Device Detection Results:")
    print(f"📡 Serial Ports: {len(devices['serial_ports'])}")
    for port in devices['serial_ports']:
        print(f"  - {port}")
    
    print(f"🔌 USB Devices: {len(devices['usb_devices'])}")
    for device in devices['usb_devices'][:5]:  # Show first 5
        print(f"  - {device}")
    
    print(f"🖱️ HID Devices: {len(devices['hid_devices'])}")
    for device in devices['hid_devices'][:5]:  # Show first 5
        print(f"  - {device}")
    
    print(f"🌐 Network Devices: {len(devices['network_devices'])}")
    for device in devices['network_devices']:
        print(f"  - {device}")
    
    # 2. Setup USB HID gadget if on Pi
    print("\n🔧 USB HID Gadget Setup:")
    hid_success = setup_usb_hid_gadget()
    
    # 3. Test serial forwarding
    print("\n📡 Serial Port Testing:")
    working_ports = test_serial_forwarding(devices)
    
    # 4. Create configuration
    print("\n📄 Configuration Generation:")
    config = create_pos_config(devices, working_ports)
    
    # 5. Summary and recommendations
    print("\n🎯 Setup Summary:")
    print(f"✅ Available forwarding methods: {', '.join(config['forwarding_methods'])}")
    
    if 'USB_HID' in config['forwarding_methods']:
        print("🔌 USB HID: Ready - Pi can act as keyboard to attached device")
    
    if working_ports:
        print(f"📡 Serial: {len(working_ports)} working port(s) - Direct serial communication")
    
    if devices['network_devices']:
        print(f"🌐 Network: {len(devices['network_devices'])} POS device(s) found on network")
    
    print("\n📋 Next Steps:")
    print("1. Connect your POS device/terminal to Raspberry Pi")
    print("2. Restart barcode scanner service")
    print("3. Scan barcodes - they will be forwarded to attached device")
    
    if 'USB_HID' in config['forwarding_methods']:
        print("4. USB HID: Barcodes will appear as keyboard input on attached device")
    
    if working_ports:
        print("5. Serial: Barcodes will be sent via serial to attached device")
    
    print("\n🔧 To test POS forwarding:")
    print("python3 -c \"from src.utils.usb_hid_forwarder import get_hid_forwarder; get_hid_forwarder().test_barcode_forwarding()\"")

if __name__ == "__main__":
    main()
