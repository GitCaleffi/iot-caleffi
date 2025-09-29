#!/usr/bin/env python3
"""
POS Connection Checker
Check if POS systems are connected and working
"""

import os
import sys
import time
import subprocess
import socket
import glob
from pathlib import Path

def check_usb_devices():
    """Check USB connected devices for POS systems"""
    print("🔌 Checking USB Devices...")
    print("=" * 40)
    
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            pos_devices = []
            
            for line in lines:
                print(f"📱 {line}")
                # Look for potential POS devices
                if any(keyword in line.lower() for keyword in ['pos', 'terminal', 'display', 'printer', 'cash', 'register']):
                    pos_devices.append(line)
            
            if pos_devices:
                print(f"\n✅ Found {len(pos_devices)} potential POS device(s):")
                for device in pos_devices:
                    print(f"   🎯 {device}")
            else:
                print("\n⚠️ No obvious POS devices detected")
                
            return len(lines) > 0
        else:
            print("❌ Could not list USB devices")
            return False
    except Exception as e:
        print(f"❌ Error checking USB: {e}")
        return False

def check_hid_devices():
    """Check HID devices (keyboards, mice, POS terminals)"""
    print("\n🖱️ Checking HID Devices...")
    print("=" * 40)
    
    hid_devices = glob.glob('/dev/hidraw*')
    if hid_devices:
        print(f"✅ Found {len(hid_devices)} HID device(s):")
        for i, device in enumerate(sorted(hid_devices), 1):
            print(f"   {i}. {device}")
            
            # Test if device is writable
            try:
                if os.access(device, os.W_OK):
                    print(f"      ✅ Writable (can send data)")
                else:
                    print(f"      ⚠️ Not writable (need sudo)")
            except:
                print(f"      ❌ Cannot access")
        
        return True
    else:
        print("❌ No HID devices found")
        return False

def check_serial_devices():
    """Check serial devices for POS communication"""
    print("\n📡 Checking Serial Devices...")
    print("=" * 40)
    
    serial_patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']
    serial_devices = []
    
    for pattern in serial_patterns:
        serial_devices.extend(glob.glob(pattern))
    
    if serial_devices:
        print(f"✅ Found {len(serial_devices)} serial device(s):")
        for i, device in enumerate(sorted(serial_devices), 1):
            print(f"   {i}. {device}")
            
            # Test if device exists and is accessible
            try:
                if os.path.exists(device):
                    if os.access(device, os.R_OK | os.W_OK):
                        print(f"      ✅ Accessible")
                    else:
                        print(f"      ⚠️ Need permissions")
                else:
                    print(f"      ❌ Device not found")
            except:
                print(f"      ❌ Cannot access")
        
        return True
    else:
        print("❌ No serial devices found")
        return False

def check_network_pos():
    """Check for network-connected POS systems"""
    print("\n🌐 Checking Network POS Systems...")
    print("=" * 40)
    
    # Get local IP to determine network range
    try:
        # Connect to a remote server to get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        print(f"📍 Local IP: {local_ip}")
        
        # Determine network range
        ip_parts = local_ip.split('.')
        network_base = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}."
        
        print(f"🔍 Scanning network: {network_base}x")
        
        # Common POS ports
        pos_ports = [80, 443, 8080, 9100, 23, 3000, 5000, 8000]
        found_devices = []
        
        # Quick scan of common POS IP ranges
        for i in [100, 101, 102, 110, 111, 200, 201]:
            test_ip = f"{network_base}{i}"
            
            for port in pos_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    result = sock.connect_ex((test_ip, port))
                    if result == 0:
                        found_devices.append(f"{test_ip}:{port}")
                        print(f"   ✅ Found: {test_ip}:{port}")
                    sock.close()
                except:
                    pass
        
        if found_devices:
            print(f"\n✅ Found {len(found_devices)} network device(s)")
            return True
        else:
            print("\n⚠️ No network POS devices found")
            return False
            
    except Exception as e:
        print(f"❌ Network scan failed: {e}")
        return False

def check_display_outputs():
    """Check display outputs for HDMI/external displays"""
    print("\n🖥️ Checking Display Outputs...")
    print("=" * 40)
    
    try:
        result = subprocess.run(['xrandr'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            displays = []
            
            for line in lines:
                if ' connected' in line:
                    display_name = line.split()[0]
                    status = "connected"
                    if '*' in line:
                        status += " (active)"
                    displays.append((display_name, status))
                    print(f"   📺 {display_name}: {status}")
            
            if len(displays) > 1:
                print(f"\n✅ Found {len(displays)} display(s) - external display available")
                return True
            else:
                print(f"\n⚠️ Only 1 display found - no external display")
                return False
        else:
            print("❌ Could not check displays")
            return False
    except Exception as e:
        print(f"❌ Display check failed: {e}")
        return False

def test_pos_connections():
    """Test actual POS connections"""
    print("\n🧪 Testing POS Connections...")
    print("=" * 40)
    
    test_results = {}
    
    # Test USB HID
    print("Testing USB HID connection...")
    try:
        from usb_pos_forwarder import send_barcode_to_usb_pos
        success = send_barcode_to_usb_pos("TEST_CONNECTION_123")
        test_results['USB_HID'] = success
        print(f"   USB HID: {'✅ Working' if success else '❌ Failed'}")
    except ImportError:
        test_results['USB_HID'] = False
        print("   USB HID: ⚠️ Not configured")
    except Exception as e:
        test_results['USB_HID'] = False
        print(f"   USB HID: ❌ Error - {e}")
    
    # Test HID devices directly
    hid_devices = glob.glob('/dev/hidraw*')
    if hid_devices:
        print("Testing direct HID device access...")
        for device in hid_devices[:2]:  # Test first 2 devices
            try:
                with open(device, 'w') as f:
                    f.write("TEST_HID_123\n")
                print(f"   {device}: ✅ Write successful")
                test_results[f'HID_{device}'] = True
            except Exception as e:
                print(f"   {device}: ❌ Write failed - {e}")
                test_results[f'HID_{device}'] = False
    
    # Test serial devices
    serial_devices = []
    for pattern in ['/dev/ttyUSB*', '/dev/ttyACM*']:
        serial_devices.extend(glob.glob(pattern))
    
    if serial_devices:
        print("Testing serial device access...")
        for device in serial_devices[:2]:  # Test first 2 devices
            try:
                # Try to open serial device
                import serial
                with serial.Serial(device, 9600, timeout=1) as ser:
                    ser.write(b"TEST_SERIAL_123\r\n")
                print(f"   {device}: ✅ Serial write successful")
                test_results[f'SERIAL_{device}'] = True
            except ImportError:
                print(f"   {device}: ⚠️ pyserial not installed")
                test_results[f'SERIAL_{device}'] = False
            except Exception as e:
                print(f"   {device}: ❌ Serial failed - {e}")
                test_results[f'SERIAL_{device}'] = False
    
    return test_results

def generate_pos_report():
    """Generate comprehensive POS connection report"""
    print("\n📊 POS Connection Report")
    print("=" * 60)
    
    # Run all checks
    usb_ok = check_usb_devices()
    hid_ok = check_hid_devices()
    serial_ok = check_serial_devices()
    network_ok = check_network_pos()
    display_ok = check_display_outputs()
    
    # Test connections
    test_results = test_pos_connections()
    
    # Summary
    print(f"\n🎯 Connection Summary:")
    print(f"   USB Devices: {'✅' if usb_ok else '❌'}")
    print(f"   HID Devices: {'✅' if hid_ok else '❌'}")
    print(f"   Serial Devices: {'✅' if serial_ok else '❌'}")
    print(f"   Network POS: {'✅' if network_ok else '❌'}")
    print(f"   External Display: {'✅' if display_ok else '❌'}")
    
    print(f"\n🧪 Test Results:")
    for test_name, result in test_results.items():
        print(f"   {test_name}: {'✅' if result else '❌'}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if hid_ok:
        print("   ✅ USB HID connection available - use usb_pos_forwarder.py")
    
    if display_ok:
        print("   ✅ External display available - use hdmi_pos_display.py")
    
    if serial_ok:
        print("   ✅ Serial connection available - configure serial POS")
    
    if network_ok:
        print("   ✅ Network devices found - try network_pos.py")
    
    if not any([hid_ok, serial_ok, network_ok, display_ok]):
        print("   ⚠️ No POS connections detected")
        print("   💡 Try connecting POS device via USB or check network")
    
    # Working connections count
    working_connections = sum([usb_ok, hid_ok, serial_ok, network_ok, display_ok])
    working_tests = sum(test_results.values())
    
    print(f"\n📈 Status: {working_connections}/5 connection types available")
    print(f"📈 Tests: {working_tests}/{len(test_results)} tests passed")
    
    if working_connections >= 2:
        print("🎉 Multiple POS connection options available!")
    elif working_connections == 1:
        print("✅ At least one POS connection method available")
    else:
        print("⚠️ No POS connections detected - check hardware")

def main():
    print("🔍 POS Connection Checker")
    print("=" * 60)
    print("Checking all available POS connection methods...\n")
    
    generate_pos_report()
    
    print(f"\n📋 Next Steps:")
    print("1. Connect your POS device via USB, serial, or network")
    print("2. Run: python3 keyboard_scanner.py")
    print("3. Scan barcodes to test POS integration")
    print("4. Check POS device for barcode display")

if __name__ == "__main__":
    main()
