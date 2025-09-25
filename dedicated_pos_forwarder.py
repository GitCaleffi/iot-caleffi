#!/usr/bin/env python3
"""
Dedicated POS Forwarder - Separate from terminal input to avoid feedback loops
Forwards barcodes to external POS systems without interfering with scanner input
"""

import subprocess
import time
import logging
import os
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DedicatedPOSForwarder:
    def __init__(self):
        self.available_methods = self._detect_methods()
        logger.info("🎯 Dedicated POS Forwarder initialized")
        logger.info(f"🔧 Available methods: {', '.join(self.available_methods)}")
    
    def _detect_methods(self):
        methods = []
        
        # Check for serial ports (USB-to-Serial adapters)
        serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        if serial_ports:
            methods.append('SERIAL')
        
        # Check for clipboard tools
        if self._command_exists('xclip') or self._command_exists('xsel'):
            methods.append('CLIPBOARD')
        
        # Always available
        methods.append('FILE')
        
        return methods
    
    def _command_exists(self, command):
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except:
            return False
    
    def forward_to_pos_terminal(self, barcode):
        """Forward barcode to POS terminal without keyboard simulation"""
        logger.info(f"🎯 Dedicated POS forwarding: {barcode}")
        
        # Try methods that don't interfere with terminal input
        methods = [
            ('SERIAL', self._forward_via_serial),
            ('CLIPBOARD', self._forward_via_clipboard),
            ('FILE', self._forward_via_file)
        ]
        
        for method_name, method_func in methods:
            if method_name in self.available_methods:
                try:
                    logger.info(f"🔄 Trying {method_name}...")
                    success = method_func(barcode)
                    if success:
                        logger.info(f"✅ POS forwarded via {method_name}")
                        return True
                    else:
                        logger.warning(f"⚠️  {method_name} failed, trying next...")
                except Exception as e:
                    logger.error(f"❌ {method_name} error: {e}")
        
        logger.error("❌ All POS forwarding methods failed")
        return False
    
    def _forward_via_serial(self, barcode):
        """Forward via USB-to-Serial adapter to POS terminal"""
        try:
            import serial
            serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            
            for port in serial_ports:
                try:
                    with serial.Serial(port, 9600, timeout=1) as ser:
                        # Send barcode with carriage return
                        ser.write(f"{barcode}\r\n".encode())
                        ser.flush()
                        logger.info(f"📡 Sent to POS via serial port {port}")
                        return True
                except Exception as e:
                    logger.warning(f"Serial port {port} failed: {e}")
                    continue
            return False
        except ImportError:
            logger.warning("Serial module not available")
            return False
        except Exception as e:
            logger.error(f"Serial forwarding failed: {e}")
            return False
    
    def _forward_via_clipboard(self, barcode):
        """Copy barcode to clipboard for manual paste into POS"""
        try:
            # Try xclip first
            result = subprocess.run(['xclip', '-selection', 'clipboard'], 
                                  input=barcode.encode(), timeout=2)
            if result.returncode == 0:
                logger.info("📋 Copied to clipboard - paste into POS terminal")
                return True
        except:
            pass
        
        try:
            # Try xsel as fallback
            result = subprocess.run(['xsel', '--clipboard', '--input'], 
                                  input=barcode.encode(), timeout=2)
            if result.returncode == 0:
                logger.info("📋 Copied to clipboard (xsel) - paste into POS terminal")
                return True
        except:
            pass
        
        return False
    
    def _forward_via_file(self, barcode):
        """Write barcode to file for POS system to read"""
        try:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            
            # Write to POS-specific files
            pos_files = [
                '/tmp/pos_terminal_input.txt',
                '/tmp/current_pos_barcode.txt',
                '/var/log/pos_barcodes.log'
            ]
            
            for file_path in pos_files:
                try:
                    with open(file_path, 'a') as f:
                        f.write(f"{timestamp}: {barcode}\n")
                except:
                    continue
            
            # Current barcode for POS to read
            with open('/tmp/current_pos_barcode.txt', 'w') as f:
                f.write(barcode)
            
            logger.info("📄 Barcode written to POS files")
            return True
        except Exception as e:
            logger.error(f"File forwarding failed: {e}")
            return False

# Global instance
_pos_forwarder = None

def get_dedicated_pos_forwarder():
    """Get global dedicated POS forwarder instance"""
    global _pos_forwarder
    if _pos_forwarder is None:
        _pos_forwarder = DedicatedPOSForwarder()
    return _pos_forwarder

def test_dedicated_pos_forwarding():
    """Test dedicated POS forwarding"""
    print("🎯 Dedicated POS Forwarding Test")
    print("=" * 50)
    
    forwarder = get_dedicated_pos_forwarder()
    
    test_barcodes = ["817994ccfe14", "8053734093444"]
    
    for barcode in test_barcodes:
        print(f"\n🧪 Testing barcode: {barcode}")
        success = forwarder.forward_to_pos_terminal(barcode)
        
        if success:
            print(f"✅ {barcode} forwarded to POS successfully!")
        else:
            print(f"❌ Failed to forward {barcode}")
    
    print(f"\n💡 Check your POS terminal or /tmp/current_pos_barcode.txt")

if __name__ == "__main__":
    test_dedicated_pos_forwarding()
