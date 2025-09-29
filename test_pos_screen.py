#!/usr/bin/env python3
"""
POS Screen Connection Tester
Test different methods to connect and display barcodes on POS screens
"""

import os
import sys
import time
import subprocess
import socket
from datetime import datetime

def print_header(title):
    print(f"\n{'='*50}")
    print(f"🖥️  {title}")
    print(f"{'='*50}")

def test_usb_hid():
    """Test USB HID gadget connection"""
    print_header("USB HID Gadget Test")
    
    hid_device = "/dev/hidg0"
    if os.path.exists(hid_device):
        print("✅ USB HID gadget found!")
        test_barcode = f"HID_TEST_{int(time.time())}"
        try:
            # Send test barcode to HID device
            with open(hid_device, 'w') as f:
                f.write(test_barcode + '\n')
            print(f"✅ Sent test barcode: {test_barcode}")
            print("   → Check if this appeared on your POS screen!")
            return True
        except Exception as e:
            print(f"❌ Failed to send to HID: {e}")
            return False
    else:
        print("❌ USB HID gadget not available")
        print("   → Run setup_pi_pos_system.sh on Raspberry Pi first")
        return False

def test_serial_ports():
    """Test serial port connections"""
    print_header("Serial Port Test")
    
    # Common serial ports
    serial_ports = [
        "/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyUSB2",
        "/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyACM2", 
        "/dev/ttyS0", "/dev/ttyS1"
    ]
    
    working_ports = []
    for port in serial_ports:
        if os.path.exists(port):
            print(f"📡 Testing {port}...")
            test_barcode = f"SERIAL_TEST_{int(time.time())}"
            try:
                # Try different baud rates
                for baud in [9600, 19200, 115200]:
                    try:
                        import serial
                        with serial.Serial(port, baud, timeout=1) as ser:
                            ser.write((test_barcode + '\r\n').encode())
                            print(f"✅ Sent to {port} at {baud} baud: {test_barcode}")
                            working_ports.append(f"{port}@{baud}")
                            break
                    except ImportError:
                        # Fallback without pyserial
                        with open(port, 'w') as f:
                            f.write(test_barcode + '\n')
                        print(f"✅ Sent to {port}: {test_barcode}")
                        working_ports.append(port)
                        break
                    except Exception:
                        continue
            except Exception as e:
                print(f"❌ Failed to send to {port}: {e}")
    
    if working_ports:
        print(f"✅ Working serial ports: {', '.join(working_ports)}")
        print("   → Check if test data appeared on connected devices!")
    else:
        print("❌ No working serial ports found")
    
    return len(working_ports) > 0

def test_network_pos():
    """Test network POS connections"""
    print_header("Network POS Test")
    
    # Common POS IP ranges and ports
    ip_ranges = [
        "192.168.1.{}",
        "192.168.0.{}",
        "10.0.0.{}"
    ]
    
    common_ports = [8080, 9100, 23, 80, 443]
    found_devices = []
    
    print("🔍 Scanning for network devices...")
    
    for ip_template in ip_ranges:
        for i in range(100, 111):  # Scan .100 to .110
            ip = ip_template.format(i)
            
            # Quick ping test
            try:
                result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                                      capture_output=True, timeout=2)
                if result.returncode == 0:
                    print(f"📍 Found device: {ip}")
                    
                    # Test common POS ports
                    for port in common_ports:
                        try:
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(1)
                            result = sock.connect_ex((ip, port))
                            if result == 0:
                                print(f"   ✅ Port {port} open")
                                found_devices.append(f"{ip}:{port}")
                                
                                # Try sending test data
                                try:
                                    test_data = f"NETWORK_TEST_{int(time.time())}\n"
                                    sock.send(test_data.encode())
                                    print(f"   📤 Sent test data to {ip}:{port}")
                                except:
                                    pass
                            sock.close()
                        except:
                            continue
            except:
                continue
    
    if found_devices:
        print(f"✅ Found network devices: {', '.join(found_devices)}")
    else:
        print("❌ No network POS devices found")
    
    return len(found_devices) > 0

def test_file_output():
    """Test file-based output"""
    print_header("File Output Test")
    
    test_files = [
        "/tmp/pos_barcode.txt",
        "/tmp/latest_barcode.txt", 
        "/tmp/current_barcode.txt"
    ]
    
    test_barcode = f"FILE_TEST_{int(time.time())}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    working_files = []
    for file_path in test_files:
        try:
            with open(file_path, 'w') as f:
                f.write(f"{timestamp}: {test_barcode}\n")
            print(f"✅ Written to: {file_path}")
            working_files.append(file_path)
        except Exception as e:
            print(f"❌ Failed to write {file_path}: {e}")
    
    if working_files:
        print("📄 File contents:")
        for file_path in working_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    print(f"   {file_path}: {content}")
            except:
                pass
    
    return len(working_files) > 0

def main():
    print("🖥️ POS Screen Connection Tester")
    print("=" * 50)
    print("This script tests different ways to send barcodes to POS screens")
    print()
    
    # Test all methods
    results = {
        "USB HID": test_usb_hid(),
        "Serial Ports": test_serial_ports(), 
        "Network POS": test_network_pos(),
        "File Output": test_file_output()
    }
    
    # Summary
    print_header("Test Summary")
    working_methods = []
    for method, success in results.items():
        status = "✅ WORKING" if success else "❌ FAILED"
        print(f"{method:15}: {status}")
        if success:
            working_methods.append(method)
    
    print(f"\n🎯 Working methods: {len(working_methods)}/4")
    
    if working_methods:
        print("\n🎉 SUCCESS! Your POS connection options:")
        for method in working_methods:
            print(f"   ✅ {method}")
        
        print("\n📋 Next steps:")
        print("1. Connect your POS device using one of the working methods")
        print("2. Run your barcode scanner: python3 keyboard_scanner.py")
        print("3. Scan barcodes - they should appear on your POS screen!")
    else:
        print("\n⚠️  No working POS connections found")
        print("📋 Setup required:")
        print("1. For USB HID: Run setup_pi_pos_system.sh on Raspberry Pi")
        print("2. For Serial: Connect POS device to Pi serial/USB port")
        print("3. For Network: Ensure POS device is on same network")

if __name__ == "__main__":
    main()
