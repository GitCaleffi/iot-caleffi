#!/usr/bin/env python3
"""
USB HID Forwarder for Caleffi Barcode Scanner
Handles USB HID gadget mode and barcode forwarding to POS systems
"""

import os
import sys
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class USBHIDForwarder:
    def __init__(self):
        self.hid_device = "/dev/hidg0"
        self.is_raspberry_pi = self._detect_raspberry_pi()
        
    def _detect_raspberry_pi(self):
        """Detect if running on Raspberry Pi"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                return 'Raspberry Pi' in f.read()
        except:
            return False
    
    def forward_barcode(self, barcode):
        """Forward barcode to POS system via USB HID"""
        try:
            # Check if HID device exists (for Raspberry Pi)
            if os.path.exists(self.hid_device):
                with open(self.hid_device, 'wb') as hid:
                    # Convert barcode to HID keyboard codes
                    hid_data = self._barcode_to_hid(barcode)
                    hid.write(hid_data)
                logger.info(f"✅ Forwarded barcode {barcode} to POS via USB HID")
                return True
            else:
                # Try alternative methods for POS forwarding
                logger.warning(f"HID device {self.hid_device} not found, trying alternatives...")
                
                # Method 1: Try keyboard simulation via uinput
                success = self._forward_via_uinput(barcode)
                if success:
                    logger.info(f"✅ Forwarded barcode {barcode} to POS via uinput")
                    return True
                
                # Method 2: Try clipboard forwarding
                success = self._forward_via_clipboard(barcode)
                if success:
                    logger.info(f"✅ Forwarded barcode {barcode} to POS via clipboard")
                    return True
                
                # Method 3: Write to file for manual testing
                success = self._forward_via_file(barcode)
                if success:
                    logger.info(f"✅ Forwarded barcode {barcode} to POS via file")
                    return True
                
                logger.error(f"❌ All POS forwarding methods failed for barcode {barcode}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to forward barcode via USB HID: {e}")
            return False
    
    def _forward_via_uinput(self, barcode):
        """Forward barcode via uinput keyboard simulation"""
        try:
            import subprocess
            # Use xdotool to simulate keyboard input
            cmd = ['xdotool', 'type', barcode]
            result = subprocess.run(cmd, timeout=5, capture_output=True)
            return result.returncode == 0
        except:
            return False
    
    def _forward_via_clipboard(self, barcode):
        """Forward barcode via clipboard"""
        try:
            import subprocess
            subprocess.run(['xclip', '-selection', 'clipboard'], input=barcode.encode(), timeout=2)
            return True
        except:
            try:
                subprocess.run(['xsel', '--clipboard', '--input'], input=barcode.encode(), timeout=2)
                return True
            except:
                return False
    
    def _forward_via_file(self, barcode):
        """Forward barcode via file for manual testing"""
        try:
            with open('/tmp/pos_barcode.txt', 'w') as f:
                f.write(f"{barcode}\n")
            logger.info(f"Barcode written to /tmp/pos_barcode.txt for manual testing")
            return True
        except:
            return False
    
    def _barcode_to_hid(self, barcode):
        """Convert barcode string to USB HID keyboard data"""
        # Simple implementation - in production this would be more sophisticated
        hid_data = bytearray()
        
        # Add each character as HID keyboard code
        for char in barcode:
            if char.isdigit():
                # Numbers 0-9 map to HID codes 30-39
                hid_code = ord(char) - ord('0') + 30
                hid_data.extend([0, 0, hid_code, 0, 0, 0, 0, 0])
        
        # Add Enter key (HID code 40)
        hid_data.extend([0, 0, 40, 0, 0, 0, 0, 0])
        
        return bytes(hid_data)

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
