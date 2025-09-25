#!/usr/bin/env python3
"""
Enhanced USB HID Forwarder for Caleffi Barcode Scanner
Compatible with all Raspberry Pi models (Pi 1 through Pi 5)
Handles USB HID gadget mode and barcode forwarding to POS systems
"""

import os
import sys
import time
import logging
import subprocess
import socket
import glob
from pathlib import Path
from typing import Optional, List, Dict

# Optional imports with fallbacks
try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    serial = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class USBHIDForwarder:
    def __init__(self):
        self.hid_device = "/dev/hidg0"
        self.is_raspberry_pi = self._detect_raspberry_pi()
        self.pi_model = self._detect_pi_model()
        self.available_methods = self._detect_available_methods()
        
        logger.info(f"🍓 Raspberry Pi detected: {self.is_raspberry_pi}")
        if self.is_raspberry_pi:
            logger.info(f"📱 Pi Model: {self.pi_model}")
            logger.info(f"🔧 Available POS methods: {', '.join(self.available_methods)}")
        
    def _detect_raspberry_pi(self):
        """Detect if running on Raspberry Pi"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                return 'Raspberry Pi' in cpuinfo or 'BCM' in cpuinfo
        except:
            return False
    
    def _detect_pi_model(self) -> str:
        """Detect specific Raspberry Pi model"""
        if not self.is_raspberry_pi:
            return "Not a Pi"
        
        try:
            # Check device tree model
            if os.path.exists('/proc/device-tree/model'):
                with open('/proc/device-tree/model', 'r') as f:
                    model = f.read().strip('\x00')
                    return model
            
            # Fallback to cpuinfo
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Model'):
                        return line.split(':', 1)[1].strip()
            
            return "Unknown Pi Model"
        except:
            return "Unknown Pi Model"
    
    def _detect_available_methods(self) -> List[str]:
        """Detect available POS forwarding methods"""
        methods = []
        
        # Check USB HID gadget support
        if os.path.exists('/sys/kernel/config/usb_gadget') or os.path.exists(self.hid_device):
            methods.append('USB_HID')
        
        # Check for serial ports (only if serial module is available)
        if SERIAL_AVAILABLE:
            serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*') + glob.glob('/dev/ttyS*')
            if serial_ports:
                methods.append('SERIAL')
        
        # Network is always available
        methods.append('NETWORK')
        
        # Check for clipboard tools
        if self._command_exists('xclip') or self._command_exists('xsel'):
            methods.append('CLIPBOARD')
        
        # KEYBOARD_SIM disabled to prevent feedback loop
        # if self._command_exists('xdotool'):
        #     methods.append('KEYBOARD_SIM')
        
        return methods
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH"""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except:
            return False
    
    def forward_barcode(self, barcode: str) -> bool:
        """Forward barcode to POS system using best available method"""
        logger.info(f"🚀 Attempting to forward barcode: {barcode}")
        
        # Try methods in order of preference
        # CRITICAL: KEYBOARD_SIM removed to prevent feedback loop
        methods_to_try = [
            ('USB_HID', self._forward_via_usb_hid),
            ('SERIAL', self._forward_via_serial),
            ('NETWORK', self._forward_via_network),
            ('CLIPBOARD', self._forward_via_clipboard),
            ('FILE', self._forward_via_file)
        ]
        
        for method_name, method_func in methods_to_try:
            if method_name in self.available_methods or method_name == 'FILE':  # FILE is always fallback
                try:
                    logger.info(f"🔄 Trying {method_name} method...")
                    success = method_func(barcode)
                    if success:
                        logger.info(f"✅ Successfully forwarded barcode {barcode} via {method_name}")
                        return True
                    else:
                        logger.warning(f"⚠️ {method_name} method failed, trying next...")
                except Exception as e:
                    logger.error(f"❌ {method_name} method error: {e}")
        
        logger.error(f"❌ All POS forwarding methods failed for barcode {barcode}")
        return False
    
    def _forward_via_usb_hid(self, barcode: str) -> bool:
        """Forward barcode via USB HID gadget"""
        try:
            if not os.path.exists(self.hid_device):
                logger.warning(f"HID device {self.hid_device} not found")
                return False
            
            with open(self.hid_device, 'wb') as hid:
                # Convert barcode to HID keyboard codes
                hid_data = self._barcode_to_hid(barcode)
                hid.write(hid_data)
                time.sleep(0.1)  # Small delay for reliability
            
            return True
        except Exception as e:
            logger.error(f"USB HID forwarding failed: {e}")
            return False
    
    def _forward_via_serial(self, barcode: str) -> bool:
        """Forward barcode via serial port"""
        if not SERIAL_AVAILABLE:
            logger.warning("Serial module not available - install with: pip install pyserial")
            return False
            
        try:
            # Find available serial ports
            serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            
            if not serial_ports:
                logger.warning("No serial ports found")
                return False
            
            for port in serial_ports:
                try:
                    with serial.Serial(port, 9600, timeout=1) as ser:
                        # Send barcode with carriage return
                        ser.write(f"{barcode}\r\n".encode())
                        ser.flush()
                        logger.info(f"📡 Sent barcode to serial port {port}")
                        return True
                except Exception as e:
                    logger.warning(f"Serial port {port} failed: {e}")
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Serial forwarding failed: {e}")
            return False
    
    def _forward_via_network(self, barcode: str) -> bool:
        """Forward barcode via network to POS system"""
        if not REQUESTS_AVAILABLE:
            logger.warning("Requests module not available - install with: pip install requests")
            return False
            
        try:
            # Common POS server ports and endpoints
            endpoints = [
                'http://localhost:8080/api/barcode',
                'http://192.168.1.100:8080/api/barcode',  # Common POS IP
                'http://192.168.1.10:8080/api/barcode',   # Another common POS IP
            ]
            
            for endpoint in endpoints:
                try:
                    response = requests.post(
                        endpoint, 
                        json={'barcode': barcode}, 
                        timeout=2
                    )
                    if response.status_code == 200:
                        logger.info(f"📤 Sent barcode to network POS at {endpoint}")
                        return True
                except:
                    continue
            
            return False
        except Exception as e:
            logger.error(f"Network forwarding failed: {e}")
            return False
    
    def _forward_via_keyboard_sim(self, barcode: str) -> bool:
        """Forward barcode via keyboard simulation"""
        try:
            # Get active window info for better debugging
            try:
                result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    window_name = result.stdout.strip()
                    logger.info(f"🎯 Active window: {window_name}")
            except:
                pass
            
            # Use xdotool to simulate keyboard input with delay for reliability
            logger.info(f"⌨️  Typing barcode: {barcode}")
            cmd = ['xdotool', 'type', '--delay', '50', barcode]
            result = subprocess.run(cmd, timeout=10, capture_output=True)
            
            if result.returncode == 0:
                # Wait a moment then send Enter key
                time.sleep(0.2)
                subprocess.run(['xdotool', 'key', 'Return'], timeout=5)
                logger.info("✅ Barcode typed successfully")
                return True
            else:
                logger.warning(f"xdotool type failed: {result.stderr.decode() if result.stderr else 'Unknown error'}")
            
            return False
        except subprocess.TimeoutExpired:
            logger.error("❌ Keyboard simulation timed out")
            return False
        except Exception as e:
            logger.error(f"Keyboard simulation failed: {e}")
            return False
    
    def _forward_via_uinput(self, barcode: str) -> bool:
        """Legacy method - now redirects to keyboard simulation"""
        return self._forward_via_keyboard_sim(barcode)
    
    def _forward_via_clipboard(self, barcode: str) -> bool:
        """Forward barcode via clipboard"""
        try:
            # Try xclip first
            result = subprocess.run(
                ['xclip', '-selection', 'clipboard'], 
                input=barcode.encode(), 
                timeout=2,
                capture_output=True
            )
            if result.returncode == 0:
                logger.info("📋 Barcode copied to clipboard (xclip)")
                return True
        except:
            pass
        
        try:
            # Try xsel as fallback
            result = subprocess.run(
                ['xsel', '--clipboard', '--input'], 
                input=barcode.encode(), 
                timeout=2,
                capture_output=True
            )
            if result.returncode == 0:
                logger.info("📋 Barcode copied to clipboard (xsel)")
                return True
        except:
            pass
        
        return False
    
    def _forward_via_file(self, barcode: str) -> bool:
        """Forward barcode via file for manual testing"""
        try:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Write to multiple locations for reliability
            file_locations = [
                '/tmp/pos_barcode.txt',
                '/tmp/latest_barcode.txt',
                '/var/log/pos_barcodes.log'
            ]
            
            for file_path in file_locations:
                try:
                    with open(file_path, 'a') as f:
                        f.write(f"{timestamp}: {barcode}\n")
                except:
                    continue
            
            # Also create a current barcode file
            with open('/tmp/current_barcode.txt', 'w') as f:
                f.write(barcode)
            
            logger.info(f"📄 Barcode {barcode} written to file locations")
            return True
        except Exception as e:
            logger.error(f"File forwarding failed: {e}")
            return False
    
    def _barcode_to_hid(self, barcode: str) -> bytes:
        """Convert barcode string to USB HID keyboard data"""
        hid_data = bytearray()
        
        # HID keyboard mapping for characters
        hid_map = {
            '0': 39, '1': 30, '2': 31, '3': 32, '4': 33,
            '5': 34, '6': 35, '7': 36, '8': 37, '9': 38,
            'a': 4, 'b': 5, 'c': 6, 'd': 7, 'e': 8, 'f': 9,
            'g': 10, 'h': 11, 'i': 12, 'j': 13, 'k': 14, 'l': 15,
            'm': 16, 'n': 17, 'o': 18, 'p': 19, 'q': 20, 'r': 21,
            's': 22, 't': 23, 'u': 24, 'v': 25, 'w': 26, 'x': 27,
            'y': 28, 'z': 29
        }
        
        # Convert each character
        for char in barcode.lower():
            if char in hid_map:
                hid_code = hid_map[char]
                # HID report: [modifier, reserved, keycode, 0, 0, 0, 0, 0]
                hid_data.extend([0, 0, hid_code, 0, 0, 0, 0, 0])
                # Key release
                hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])
        
        # Add Enter key (HID code 40)
        hid_data.extend([0, 0, 40, 0, 0, 0, 0, 0])  # Press Enter
        hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])   # Release Enter
        
        return bytes(hid_data)
    
    def test_barcode_forwarding(self, test_barcode: str = "8053734093444") -> Dict[str, bool]:
        """Test all available forwarding methods with a test barcode"""
        logger.info(f"🧪 Testing POS forwarding with barcode: {test_barcode}")
        
        results = {}
        
        methods_to_test = [
            ('USB_HID', self._forward_via_usb_hid),
            ('SERIAL', self._forward_via_serial),
            ('NETWORK', self._forward_via_network),
            ('KEYBOARD_SIM', self._forward_via_keyboard_sim),
            ('CLIPBOARD', self._forward_via_clipboard),
            ('FILE', self._forward_via_file)
        ]
        
        for method_name, method_func in methods_to_test:
            try:
                logger.info(f"Testing {method_name}...")
                success = method_func(test_barcode)
                results[method_name] = success
                status = "✅ PASS" if success else "❌ FAIL"
                logger.info(f"{method_name}: {status}")
            except Exception as e:
                results[method_name] = False
                logger.error(f"{method_name}: ❌ ERROR - {e}")
        
        # Summary
        working_methods = [k for k, v in results.items() if v]
        logger.info(f"\n📊 Test Results Summary:")
        logger.info(f"✅ Working methods: {', '.join(working_methods) if working_methods else 'None'}")
        logger.info(f"❌ Failed methods: {', '.join([k for k, v in results.items() if not v])}")
        
        return results

# Global instance
_hid_forwarder = None

def get_hid_forwarder():
    """Get global HID forwarder instance"""
    global _hid_forwarder
    if _hid_forwarder is None:
        _hid_forwarder = USBHIDForwarder()
    return _hid_forwarder

def start_hid_service():
    """Start HID forwarding service"""
    logger.info("HID forwarding service started")
    return True
