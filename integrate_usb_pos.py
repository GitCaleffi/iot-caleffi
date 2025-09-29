#!/usr/bin/env python3
"""
Integrate USB POS Device with Barcode Scanner
Updates the barcode scanner to send barcodes to the configured USB device
"""

import json
import os
import sys
from pathlib import Path

def create_usb_pos_forwarder():
    """Create a USB POS forwarder class"""
    
    forwarder_code = '''#!/usr/bin/env python3
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
                f.write(barcode + '\\n')
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
                ser.write((barcode + '\\r\\n').encode())
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
'''
    
    # Write the forwarder to a file
    with open("usb_pos_forwarder.py", "w") as f:
        f.write(forwarder_code)
    
    print("✅ Created usb_pos_forwarder.py")
    return "usb_pos_forwarder.py"

def create_pos_config():
    """Create a sample POS configuration based on your setup"""
    config = {
        "pos_forwarding": {
            "enabled": True,
            "primary_device": {
                "path": "/dev/hidraw0",
                "type": "hid",
                "baud_rate": None
            },
            "methods": {
                "hid": True,
                "serial": False,
                "network": False,
                "file": True
            }
        }
    }
    
    with open("pos_device_config.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("✅ Created pos_device_config.json")
    return "pos_device_config.json"

def update_keyboard_scanner():
    """Update keyboard_scanner.py to use USB POS forwarding"""
    
    # Read the current keyboard scanner
    scanner_file = "keyboard_scanner.py"
    if not os.path.exists(scanner_file):
        print(f"❌ {scanner_file} not found")
        return False
    
    # Create a backup
    backup_file = f"{scanner_file}.backup"
    if not os.path.exists(backup_file):
        os.system(f"cp {scanner_file} {backup_file}")
        print(f"✅ Created backup: {backup_file}")
    
    # Add USB POS integration
    integration_code = '''
# USB POS Integration
try:
    from usb_pos_forwarder import send_barcode_to_usb_pos
    USB_POS_AVAILABLE = True
    print("✅ USB POS forwarder loaded")
except ImportError:
    USB_POS_AVAILABLE = False
    print("⚠️ USB POS forwarder not available")

def send_to_usb_pos(barcode):
    """Send barcode to USB POS device"""
    if USB_POS_AVAILABLE:
        try:
            success = send_barcode_to_usb_pos(barcode)
            if success:
                print(f"✅ Sent to USB POS: {barcode}")
                return True
            else:
                print(f"❌ Failed to send to USB POS: {barcode}")
                return False
        except Exception as e:
            print(f"❌ USB POS error: {e}")
            return False
    else:
        print("⚠️ USB POS not available")
        return False
'''
    
    print("📝 Integration code ready")
    print("💡 To integrate with your keyboard scanner:")
    print("1. Add the USB POS forwarder import")
    print("2. Call send_to_usb_pos(barcode) after successful barcode scan")
    print("3. Test with: python3 keyboard_scanner.py")
    
    return True

def test_integration():
    """Test the USB POS integration"""
    print("\n🧪 Testing USB POS Integration")
    print("=" * 40)
    
    try:
        # Import the forwarder
        sys.path.insert(0, '.')
        from usb_pos_forwarder import USBPOSForwarder
        
        # Create and test forwarder
        forwarder = USBPOSForwarder()
        success = forwarder.test_connection()
        
        if success:
            print("\n🎉 USB POS integration is working!")
            print("📋 Your barcode scanner can now send barcodes to your POS device")
        else:
            print("\n⚠️ USB POS integration needs configuration")
            print("📋 Make sure your POS device is connected and configured")
            
        return success
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    print("🔌 USB POS Integration Setup")
    print("=" * 40)
    print("This will integrate USB POS forwarding with your barcode scanner")
    print()
    
    # Create necessary files
    forwarder_file = create_usb_pos_forwarder()
    config_file = create_pos_config()
    
    # Update scanner integration
    update_keyboard_scanner()
    
    # Test the integration
    test_integration()
    
    print(f"\n🎯 Integration Complete!")
    print(f"📁 Files created:")
    print(f"   - {forwarder_file}")
    print(f"   - {config_file}")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Copy these files to your Raspberry Pi")
    print(f"2. Update your keyboard_scanner.py to call send_to_usb_pos(barcode)")
    print(f"3. Test with: python3 keyboard_scanner.py")
    print(f"4. Scan barcodes - they should appear on your POS device!")
    
    print(f"\n💻 Add this to your barcode processing function:")
    print(f"   from usb_pos_forwarder import send_barcode_to_usb_pos")
    print(f"   send_barcode_to_usb_pos(barcode)  # After successful scan")

if __name__ == "__main__":
    main()
