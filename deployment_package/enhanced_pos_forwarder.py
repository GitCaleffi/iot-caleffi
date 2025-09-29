#!/usr/bin/env python3
"""
Enhanced POS Forwarder for Attached Devices
Specifically designed to forward barcodes to devices attached to Raspberry Pi
"""

import os
import sys
import glob
import time
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

# Add the src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedPOSForwarder:
    def __init__(self):
        self.attached_devices = self._detect_attached_devices()
        self.setup_hid_gadget()
        
    def _detect_attached_devices(self) -> Dict:
        """Detect all devices attached to Raspberry Pi"""
        logger.info("🔍 Scanning for attached POS devices...")
        
        devices = {
            'serial_ports': [],
            'usb_keyboards': [],
            'hid_devices': [],
            'network_terminals': []
        }
        
        # 1. Serial devices (most common for POS terminals)
        serial_patterns = ['/dev/ttyUSB*', '/dev/ttyACM*', '/dev/ttyS*']
        for pattern in serial_patterns:
            ports = glob.glob(pattern)
            devices['serial_ports'].extend(ports)
            
        # 2. USB HID devices
        hid_patterns = ['/dev/hidraw*']
        for pattern in hid_patterns:
            hid_devices = glob.glob(pattern)
            devices['hid_devices'].extend(hid_devices)
        
        # 3. USB keyboards/input devices
        try:
            result = subprocess.run(['ls', '/dev/input/by-id/'], capture_output=True, text=True)
            if result.returncode == 0:
                usb_devices = [line for line in result.stdout.split('\n') 
                             if 'usb' in line.lower() and ('keyboard' in line.lower() or 'kbd' in line.lower())]
                devices['usb_keyboards'] = usb_devices
        except:
            pass
        
        # 4. Network-connected POS terminals
        devices['network_terminals'] = self._scan_network_pos()
        
        logger.info(f"📊 Detected devices:")
        logger.info(f"  📡 Serial ports: {len(devices['serial_ports'])}")
        logger.info(f"  ⌨️ USB keyboards: {len(devices['usb_keyboards'])}")
        logger.info(f"  🖱️ HID devices: {len(devices['hid_devices'])}")
        logger.info(f"  🌐 Network terminals: {len(devices['network_terminals'])}")
        
        return devices
    
    def _scan_network_pos(self) -> List[str]:
        """Scan for network-connected POS terminals"""
        pos_ips = []
        
        # Common POS terminal IP ranges
        ip_ranges = [
            '192.168.1.{}',
            '192.168.0.{}',
            '10.0.0.{}'
        ]
        
        # Common POS terminal IPs
        common_ips = [10, 20, 100, 101, 150, 200]
        
        for ip_template in ip_ranges:
            for ip_suffix in common_ips:
                ip = ip_template.format(ip_suffix)
                try:
                    # Quick ping test
                    result = subprocess.run(['ping', '-c', '1', '-W', '1', ip], 
                                          capture_output=True, timeout=2)
                    if result.returncode == 0:
                        # Test if it responds to common POS ports
                        if self._test_pos_ports(ip):
                            pos_ips.append(ip)
                except:
                    continue
        
        return pos_ips
    
    def _test_pos_ports(self, ip: str) -> bool:
        """Test if IP responds to common POS ports"""
        import socket
        
        common_ports = [8080, 9100, 515, 631, 80, 443]
        
        for port in common_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, port))
                sock.close()
                if result == 0:
                    return True
            except:
                continue
        
        return False
    
    def setup_hid_gadget(self) -> bool:
        """Setup USB HID gadget for keyboard emulation"""
        if os.path.exists('/dev/hidg0'):
            logger.info("✅ USB HID gadget already configured")
            return True
        
        # Check if we're on Raspberry Pi
        try:
            with open('/proc/cpuinfo', 'r') as f:
                if 'Raspberry Pi' not in f.read():
                    logger.warning("⚠️ Not on Raspberry Pi - USB HID gadget not available")
                    return False
        except:
            return False
        
        logger.info("🔧 Setting up USB HID gadget...")
        
        # Create setup script
        setup_commands = [
            'modprobe libcomposite',
            'cd /sys/kernel/config/usb_gadget/',
            'mkdir -p g1 && cd g1',
            'echo 0x1d6b > idVendor',
            'echo 0x0104 > idProduct',
            'echo 0x0100 > bcdDevice',
            'echo 0x0200 > bcdUSB',
            'mkdir -p strings/0x409',
            'echo "fedcba9876543210" > strings/0x409/serialnumber',
            'echo "Caleffi" > strings/0x409/manufacturer',
            'echo "Barcode Scanner" > strings/0x409/product',
            'mkdir -p configs/c.1/strings/0x409',
            'echo "Config 1: HID Keyboard" > configs/c.1/strings/0x409/configuration',
            'echo 250 > configs/c.1/MaxPower',
            'mkdir -p functions/hid.usb0',
            'echo 1 > functions/hid.usb0/protocol',
            'echo 1 > functions/hid.usb0/subclass',
            'echo 8 > functions/hid.usb0/report_length',
            'echo -ne "\\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0" > functions/hid.usb0/report_desc',
            'ln -s functions/hid.usb0 configs/c.1/',
            'ls /sys/class/udc > UDC'
        ]
        
        script_content = '#!/bin/bash\n' + '\n'.join(setup_commands)
        
        try:
            with open('/tmp/setup_hid.sh', 'w') as f:
                f.write(script_content)
            
            os.chmod('/tmp/setup_hid.sh', 0o755)
            
            result = subprocess.run(['sudo', '/tmp/setup_hid.sh'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists('/dev/hidg0'):
                logger.info("✅ USB HID gadget setup successful")
                return True
            else:
                logger.error(f"❌ USB HID setup failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error setting up USB HID: {e}")
            return False
    
    def forward_to_attached_devices(self, barcode: str) -> Dict[str, bool]:
        """Forward barcode to all attached devices"""
        logger.info(f"📤 Forwarding barcode {barcode} to attached devices...")
        
        results = {}
        
        # 1. USB HID Keyboard emulation (most reliable for POS terminals)
        if os.path.exists('/dev/hidg0'):
            results['USB_HID'] = self._forward_via_hid_keyboard(barcode)
        
        # 2. Serial port forwarding
        for port in self.attached_devices['serial_ports']:
            results[f'SERIAL_{port}'] = self._forward_via_serial_port(barcode, port)
        
        # 3. Network POS terminals
        for ip in self.attached_devices['network_terminals']:
            results[f'NETWORK_{ip}'] = self._forward_via_network_pos(barcode, ip)
        
        # 4. Direct HID device communication
        for hid_dev in self.attached_devices['hid_devices']:
            results[f'HID_{hid_dev}'] = self._forward_via_hid_device(barcode, hid_dev)
        
        # Summary
        successful = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]
        
        logger.info(f"📊 Forwarding results:")
        logger.info(f"  ✅ Successful: {', '.join(successful) if successful else 'None'}")
        logger.info(f"  ❌ Failed: {', '.join(failed) if failed else 'None'}")
        
        return results
    
    def _forward_via_hid_keyboard(self, barcode: str) -> bool:
        """Forward barcode via USB HID keyboard emulation"""
        try:
            logger.info("⌨️ Forwarding via USB HID keyboard...")
            
            with open('/dev/hidg0', 'wb') as hid:
                # Convert barcode to HID keyboard data
                hid_data = self._barcode_to_hid_data(barcode)
                hid.write(hid_data)
                time.sleep(0.1)
            
            logger.info("✅ USB HID keyboard forwarding successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ USB HID keyboard forwarding failed: {e}")
            return False
    
    def _forward_via_serial_port(self, barcode: str, port: str) -> bool:
        """Forward barcode via serial port"""
        if not SERIAL_AVAILABLE:
            logger.warning("❌ PySerial not available")
            return False
        
        try:
            logger.info(f"📡 Forwarding to serial port {port}...")
            
            with serial.Serial(port, 9600, timeout=2) as ser:
                # Try different formats that POS terminals expect
                formats = [
                    f"{barcode}\r\n",      # Standard format
                    f"{barcode}\n",        # Linux format
                    f"{barcode}\r",        # Mac format
                    f"SCAN:{barcode}\r\n", # Some POS systems expect prefix
                ]
                
                for fmt in formats:
                    ser.write(fmt.encode())
                    ser.flush()
                    time.sleep(0.1)
            
            logger.info(f"✅ Serial port {port} forwarding successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Serial port {port} forwarding failed: {e}")
            return False
    
    def _forward_via_network_pos(self, barcode: str, ip: str) -> bool:
        """Forward barcode to network POS terminal"""
        try:
            import requests
        except ImportError:
            logger.warning("❌ Requests module not available")
            return False
        
        try:
            logger.info(f"🌐 Forwarding to network POS {ip}...")
            
            # Try common POS API endpoints
            endpoints = [
                f'http://{ip}:8080/api/barcode',
                f'http://{ip}:8080/barcode',
                f'http://{ip}/api/scan',
                f'http://{ip}/scan',
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        endpoint,
                        json={'barcode': barcode, 'timestamp': time.time()},
                        timeout=3
                    )
                    if response.status_code == 200:
                        logger.info(f"✅ Network POS {ip} forwarding successful")
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Network POS {ip} forwarding failed: {e}")
            return False
    
    def _forward_via_hid_device(self, barcode: str, hid_device: str) -> bool:
        """Forward barcode to HID device"""
        try:
            logger.info(f"🖱️ Forwarding to HID device {hid_device}...")
            
            # Try to write barcode data to HID device
            with open(hid_device, 'wb') as hid:
                # Simple barcode data format
                data = f"{barcode}\n".encode()
                hid.write(data)
            
            logger.info(f"✅ HID device {hid_device} forwarding successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ HID device {hid_device} forwarding failed: {e}")
            return False
    
    def _barcode_to_hid_data(self, barcode: str) -> bytes:
        """Convert barcode to USB HID keyboard data"""
        hid_data = bytearray()
        
        # HID keyboard scan codes
        hid_map = {
            '0': 39, '1': 30, '2': 31, '3': 32, '4': 33,
            '5': 34, '6': 35, '7': 36, '8': 37, '9': 38,
            'a': 4, 'b': 5, 'c': 6, 'd': 7, 'e': 8, 'f': 9,
            'g': 10, 'h': 11, 'i': 12, 'j': 13, 'k': 14, 'l': 15,
            'm': 16, 'n': 17, 'o': 18, 'p': 19, 'q': 20, 'r': 21,
            's': 22, 't': 23, 'u': 24, 'v': 25, 'w': 26, 'x': 27,
            'y': 28, 'z': 29
        }
        
        # Convert each character to HID data
        for char in barcode.lower():
            if char in hid_map:
                scan_code = hid_map[char]
                # HID report: [modifier, reserved, keycode, 0, 0, 0, 0, 0]
                hid_data.extend([0, 0, scan_code, 0, 0, 0, 0, 0])  # Key press
                hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])          # Key release
        
        # Add Enter key (scan code 40)
        hid_data.extend([0, 0, 40, 0, 0, 0, 0, 0])  # Enter press
        hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])   # Enter release
        
        return bytes(hid_data)
    
    def test_all_methods(self, test_barcode: str = "TEST123456789") -> Dict[str, bool]:
        """Test all forwarding methods with a test barcode"""
        logger.info(f"🧪 Testing all POS forwarding methods with: {test_barcode}")
        
        results = self.forward_to_attached_devices(test_barcode)
        
        # Summary
        total_methods = len(results)
        successful_methods = sum(1 for success in results.values() if success)
        
        logger.info(f"\n📊 Test Summary:")
        logger.info(f"  Total methods tested: {total_methods}")
        logger.info(f"  Successful: {successful_methods}")
        logger.info(f"  Failed: {total_methods - successful_methods}")
        
        return results

def main():
    """Main function for testing"""
    print("🔧 Enhanced POS Forwarder for Attached Devices")
    print("=" * 50)
    
    forwarder = EnhancedPOSForwarder()
    
    # Test with a sample barcode
    test_barcode = input("Enter test barcode (or press Enter for default): ").strip()
    if not test_barcode:
        test_barcode = "1234567890123"
    
    results = forwarder.test_all_methods(test_barcode)
    
    print(f"\n🎯 Results for barcode: {test_barcode}")
    for method, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {method}: {status}")

if __name__ == "__main__":
    main()
