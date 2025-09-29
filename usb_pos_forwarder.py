#!/usr/bin/env python3
"""
USB POS Forwarder - Sends barcodes to configured USB device
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

class USBPOSForwarder:
    def __init__(self, config_file="pos_device_config.json"):
        self.config = self.load_config(config_file)
        self.device_path = None
        self.device_type = None
        
        if self.config and self.config.get("pos_forwarding", {}).get("enabled"):
            device_info = self.config["pos_forwarding"]["primary_device"]
            self.device_path = device_info["path"]
            self.device_type = device_info["type"]
            logger.info(f"USB POS Forwarder initialized: {self.device_path} ({self.device_type})")
        else:
            logger.warning("USB POS Forwarder not configured")
    
    def load_config(self, config_file):
        """Load POS device configuration"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config {config_file}: {e}")
        return None
    
    def send_barcode(self, barcode):
        """Send barcode to configured USB device"""
        if not self.device_path or not os.path.exists(self.device_path):
            logger.warning(f"USB POS device not available: {self.device_path}")
            return False
        
        try:
            if self.device_type == "hid":
                return self.send_to_hid(barcode)
            elif self.device_type == "serial":
                return self.send_to_serial(barcode)
            else:
                logger.error(f"Unknown device type: {self.device_type}")
                return False
        except Exception as e:
            logger.error(f"Failed to send barcode to USB POS: {e}")
            return False
    
    def send_to_hid(self, barcode):
        """Send barcode to HID device"""
        try:
            with open(self.device_path, 'w') as f:
                f.write(barcode + '\n')
            logger.info(f"✅ Sent barcode to HID device {self.device_path}: {barcode}")
            return True
        except Exception as e:
            logger.error(f"HID send failed: {e}")
            return False
    
    def send_to_serial(self, barcode):
        """Send barcode to Serial device"""
        try:
            import serial
            baud_rate = self.config["pos_forwarding"]["primary_device"].get("baud_rate", 9600)
            with serial.Serial(self.device_path, baud_rate, timeout=1) as ser:
                ser.write((barcode + '\r\n').encode())
            logger.info(f"✅ Sent barcode to Serial device {self.device_path}: {barcode}")
            return True
        except ImportError:
            logger.error("pyserial not installed. Install with: pip install pyserial")
            return False
        except Exception as e:
            logger.error(f"Serial send failed: {e}")
            return False
    
    def test_connection(self):
        """Test connection to USB POS device"""
        test_barcode = "TEST_CONNECTION_123"
        success = self.send_barcode(test_barcode)
        if success:
            print(f"✅ USB POS connection test successful!")
            print(f"   → Check if '{test_barcode}' appeared on your POS device")
        else:
            print(f"❌ USB POS connection test failed")
        return success

# Create global instance
usb_pos_forwarder = USBPOSForwarder()

def send_barcode_to_usb_pos(barcode):
    """Convenience function to send barcode to USB POS"""
    return usb_pos_forwarder.send_barcode(barcode)

if __name__ == "__main__":
    # Test the forwarder
    forwarder = USBPOSForwarder()
    forwarder.test_connection()
