#!/usr/bin/env python3
"""
Automatic USB Barcode Scanner
- Captures barcode data automatically as scanner types it
- No manual input required
- Works with keyboard-emulation scanners
"""

import sys
import time
import threading
from datetime import datetime

try:
    import evdev
    from evdev import InputDevice, ecodes
except ImportError:
    print("Installing evdev...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, ecodes

class AutoUSBScanner:
    def __init__(self):
        self.running = False
        self.scan_count = 0
        self.device = None
        
    def find_scanner_device(self):
        """Find the USB scanner device"""
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        print("🔍 Scanning for input devices...")
        for device in devices:
            print(f"  📱 {device.name}")
            
            # Check device capabilities
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                
                # Check if it has keyboard-like capabilities
                has_numbers = any(ecodes.KEY_1 + i in keys for i in range(10))
                has_letters = any(ecodes.KEY_A + i in keys for i in range(26))
                has_enter = ecodes.KEY_ENTER in keys
                
                if has_numbers and has_letters and has_enter:
                    # Check if it's likely a scanner (not a regular keyboard)
                    name = device.name.lower()
                    scanner_keywords = ['barcode', 'scanner', 'honeywell', 'symbol', 'datalogic', 'zebra', 'pos', 'hid']
                    
                    if any(keyword in name for keyword in scanner_keywords):
                        print(f"✅ Found barcode scanner: {device.name}")
                        return device
                    elif 'keyboard' not in name:  # Might be a scanner without obvious name
                        print(f"✅ Found possible scanner device: {device.name}")
                        return device
        
        # If no obvious scanner found, try the first keyboard-like device
        for device in devices:
            caps = device.capabilities()
            if ecodes.EV_KEY in caps:
                keys = caps[ecodes.EV_KEY]
                has_numbers = any(ecodes.KEY_1 + i in keys for i in range(10))
                has_enter = ecodes.KEY_ENTER in keys
                
                if has_numbers and has_enter:
                    print(f"⚠️ Using keyboard-like device: {device.name}")
                    return device
        
        return None
    
    def read_barcode_automatically(self):
        """Read barcode data automatically from scanner"""
        if not self.device:
            return None
            
        barcode_buffer = ""
        
        try:
            print(f"📱 Monitoring {self.device.name}")
            print("🔍 Scanner ready - scan any barcode...")
            print("Press Ctrl+C to stop\n")
            
            for event in self.device.read_loop():
                if not self.running:
                    break
                    
                if event.type == ecodes.EV_KEY and event.value == 1:  # Key press
                    key_code = event.code
                    
                    # Convert key codes to characters
                    if ecodes.KEY_1 <= key_code <= ecodes.KEY_9:
                        barcode_buffer += str(key_code - ecodes.KEY_1 + 1)
                    elif key_code == ecodes.KEY_0:
                        barcode_buffer += "0"
                    elif ecodes.KEY_A <= key_code <= ecodes.KEY_Z:
                        barcode_buffer += chr(ord('a') + key_code - ecodes.KEY_A)
                    elif key_code == ecodes.KEY_ENTER:
                        # Barcode scan complete
                        if barcode_buffer.strip():
                            barcode = barcode_buffer.strip()
                            self.process_barcode(barcode)
                            barcode_buffer = ""
                    elif key_code == ecodes.KEY_SPACE:
                        barcode_buffer += " "
                    elif key_code == ecodes.KEY_MINUS:
                        barcode_buffer += "-"
                    elif key_code == ecodes.KEY_DOT:
                        barcode_buffer += "."
                    elif key_code == ecodes.KEY_SLASH:
                        barcode_buffer += "/"
                        
        except Exception as e:
            print(f"❌ Error reading from scanner: {e}")
    
    def process_barcode(self, barcode):
        """Process scanned barcode"""
        self.scan_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("=" * 60)
        print(f"📊 AUTOMATIC SCAN #{self.scan_count}")
        print("=" * 60)
        print(f"📱 Barcode: {barcode}")
        print(f"📏 Length: {len(barcode)} characters")
        print(f"🕒 Time: {timestamp}")
        print(f"🔢 Format: {self.detect_barcode_format(barcode)}")
        print("=" * 60)
        print("🔍 Ready for next scan...\n")
    
    def detect_barcode_format(self, barcode):
        """Detect barcode format"""
        length = len(barcode)
        
        if length == 13 and barcode.isdigit():
            return "EAN-13"
        elif length == 12 and barcode.isdigit():
            return "UPC-A"
        elif length == 8 and barcode.isdigit():
            return "EAN-8"
        elif length in [6, 7] and barcode.isdigit():
            return "UPC-E"
        elif barcode.isdigit():
            return f"Numeric ({length} digits)"
        elif barcode.isalnum():
            return f"Alphanumeric ({length} chars)"
        else:
            return f"Mixed format ({length} chars)"
    
    def start(self):
        """Start the automatic scanner"""
        self.running = True
        
        print("🚀 AUTOMATIC USB BARCODE SCANNER")
        print("=" * 50)
        print("No manual input required!")
        print("Just scan barcodes with your USB scanner")
        print("=" * 50)
        
        # Find scanner device
        self.device = self.find_scanner_device()
        
        if not self.device:
            print("❌ No USB scanner device found")
            print("💡 Make sure your USB barcode scanner is connected")
            return False
        
        try:
            # Start automatic barcode reading
            self.read_barcode_automatically()
            
        except KeyboardInterrupt:
            print(f"\n\n👋 Scanner stopped after {self.scan_count} scans")
        except Exception as e:
            print(f"\n❌ Scanner error: {e}")
            return False
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the scanner"""
        self.running = False
        print(f"\n✅ Automatic scanner session completed")
        if self.scan_count > 0:
            print(f"📊 Total scans: {self.scan_count}")

def main():
    """Main function"""
    scanner = AutoUSBScanner()
    success = scanner.start()
    
    if not success:
        print("\n❌ Scanner failed to start")
        print("💡 Troubleshooting:")
        print("  1. Check USB scanner connection")
        print("  2. Make sure scanner is in keyboard emulation mode")
        print("  3. Try running with sudo if permission issues")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
