#!/usr/bin/env python3
"""
Optimized POS Forwarder - Only forwards to working devices
Eliminates excessive serial port scanning and I/O errors
"""

import os
import sys
import glob
import time
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OptimizedPOSForwarder:
    def __init__(self):
        self.working_devices = self._detect_working_devices()
        self.setup_hid_gadget()
        
    def _detect_working_devices(self) -> Dict:
        """Detect only working devices - skip broken ones"""
        logger.info("🔍 Scanning for working POS devices...")
        
        devices = {
            'serial_ports': [],
            'hid_devices': [],
            'network_terminals': []
        }
        
        # 1. Test serial devices - only add working ones
        if SERIAL_AVAILABLE:
            # Only test common working serial ports, not all 32
            test_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1', 
                         '/dev/ttyS0', '/dev/ttyS1', '/dev/ttyS4']  # Common working ports
            
            for port in test_ports:
                if os.path.exists(port) and self._test_serial_port(port):
                    devices['serial_ports'].append(port)
        
        # 2. Test HID devices - only add working ones
        hid_devices = glob.glob('/dev/hidraw*')
        for hid_dev in hid_devices:
            if self._test_hid_device(hid_dev):
                devices['hid_devices'].append(hid_dev)
        
        # 3. Skip network scanning for now (too slow)
        
        logger.info(f"📊 Working devices found:")
        logger.info(f"  📡 Serial ports: {len(devices['serial_ports'])} - {devices['serial_ports']}")
        logger.info(f"  🖱️ HID devices: {len(devices['hid_devices'])} - {devices['hid_devices']}")
        
        return devices
    
    def _test_serial_port(self, port: str) -> bool:
        """Quick test if serial port is working"""
        try:
            with serial.Serial(port, 9600, timeout=0.5) as ser:
                # If we can open it without error, it's working
                return True
        except Exception as e:
            # Skip ports that give I/O errors
            if "Input/output error" in str(e):
                return False
            return False
    
    def _test_hid_device(self, hid_device: str) -> bool:
        """Quick test if HID device is working"""
        try:
            # Try to open for writing with a small test
            with open(hid_device, 'wb') as hid:
                # Try to write a small test byte
                hid.write(b'\x00')
                return True
        except Exception as e:
            # Skip devices that give broken pipe or permission errors
            if any(err in str(e) for err in ["Broken pipe", "Permission denied", "Operation not permitted"]):
                return False
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
        
        return False  # Skip setup for now
    
    def forward_to_working_devices(self, barcode: str) -> Dict[str, bool]:
        """Forward barcode only to pre-tested working devices"""
        logger.info(f"📤 Forwarding barcode {barcode} to {len(self.working_devices['serial_ports']) + len(self.working_devices['hid_devices'])} working devices...")
        
        results = {}
        
        # 1. USB HID Keyboard emulation
        if os.path.exists('/dev/hidg0'):
            results['USB_HID'] = self._forward_via_hid_keyboard(barcode)
        
        # 2. Only forward to working serial ports
        for port in self.working_devices['serial_ports']:
            results[f'SERIAL_{port}'] = self._forward_via_serial_port(barcode, port)
        
        # 3. Only forward to working HID devices
        for hid_dev in self.working_devices['hid_devices']:
            results[f'HID_{hid_dev}'] = self._forward_via_hid_device(barcode, hid_dev)
        
        # Summary
        successful = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]
        
        logger.info(f"📊 Forwarding results:")
        if successful:
            logger.info(f"  ✅ Successful: {', '.join(successful)}")
        if failed:
            logger.info(f"  ❌ Failed: {', '.join(failed)}")
        
        return results
    
    def _forward_via_hid_keyboard(self, barcode: str) -> bool:
        """Forward barcode via USB HID keyboard emulation"""
        try:
            logger.info("⌨️ Forwarding via USB HID keyboard...")
            
            with open('/dev/hidg0', 'wb') as hid:
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
        try:
            logger.info(f"📡 Forwarding to serial port {port}...")
            
            with serial.Serial(port, 9600, timeout=1) as ser:
                # Send barcode with carriage return
                ser.write(f"{barcode}\r\n".encode())
                ser.flush()
                time.sleep(0.1)
            
            logger.info(f"✅ Serial port {port} forwarding successful")
            return True
            
        except Exception as e:
            logger.error(f"❌ Serial port {port} forwarding failed: {e}")
            return False
    
    def _forward_via_hid_device(self, barcode: str, hid_device: str) -> bool:
        """Forward barcode to HID device"""
        try:
            logger.info(f"🖱️ Forwarding to HID device {hid_device}...")
            
            with open(hid_device, 'wb') as hid:
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

# Global instance
_optimized_forwarder = None

def get_optimized_forwarder():
    """Get global optimized forwarder instance"""
    global _optimized_forwarder
    if _optimized_forwarder is None:
        _optimized_forwarder = OptimizedPOSForwarder()
    return _optimized_forwarder

def main():
    """Test the optimized forwarder"""
    print("🚀 Optimized POS Forwarder - Working Devices Only")
    print("=" * 50)
    
    forwarder = OptimizedPOSForwarder()
    
    test_barcode = input("Enter test barcode (or press Enter for default): ").strip()
    if not test_barcode:
        test_barcode = "1234567890123"
    
    results = forwarder.forward_to_working_devices(test_barcode)
    
    print(f"\n🎯 Results for barcode: {test_barcode}")
    for method, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {method}: {status}")

if __name__ == "__main__":
    main()
