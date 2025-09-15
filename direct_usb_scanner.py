#!/usr/bin/env python3
"""
Direct USB Scanner - Works with scanners that act as keyboard input
"""

import sys
import os
import time
import select
import termios
import tty
from datetime import datetime

class DirectUSBScanner:
    def __init__(self):
        self.scan_count = 0
        self.running = True
        
    def read_scanner_input(self):
        """Read scanner input directly from stdin"""
        print("🔍 Direct USB Scanner Test")
        print("=" * 40)
        print("📱 Point your USB scanner at a barcode and scan")
        print("The barcode should appear automatically")
        print("Press Ctrl+C to stop")
        print("=" * 40)
        
        # Save terminal settings
        old_settings = termios.tcgetattr(sys.stdin)
        
        try:
            # Set terminal to raw mode to capture scanner input
            tty.setraw(sys.stdin.fileno())
            
            barcode_buffer = ""
            
            while self.running:
                # Check if input is available
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)
                    
                    # Handle different characters
                    if ord(char) == 13 or ord(char) == 10:  # Enter/Return
                        if barcode_buffer:
                            self.process_barcode(barcode_buffer)
                            barcode_buffer = ""
                    elif ord(char) == 3:  # Ctrl+C
                        break
                    elif ord(char) >= 32 and ord(char) <= 126:  # Printable characters
                        barcode_buffer += char
                        print(char, end='', flush=True)
                        
        except KeyboardInterrupt:
            pass
        finally:
            # Restore terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print(f"\n\n👋 Scanner stopped after {self.scan_count} scans")
    
    def simple_input_method(self):
        """Simple input method - scanner types directly"""
        print("\n🔍 Simple USB Scanner Method")
        print("=" * 40)
        print("📱 This method works if your scanner types like a keyboard")
        print("Just scan barcodes - they should appear as typed text")
        print("Press Enter after each scan, or Ctrl+C to stop")
        print("=" * 40)
        
        try:
            while self.running:
                print(f"\nScan #{self.scan_count + 1}: ", end="", flush=True)
                
                # Read line from stdin (scanner should type and press Enter)
                barcode = sys.stdin.readline().strip()
                
                if barcode:
                    self.process_barcode(barcode)
                else:
                    print("Empty scan - try again")
                    
        except KeyboardInterrupt:
            print(f"\n👋 Stopped after {self.scan_count} scans")
    
    def process_barcode(self, barcode):
        """Process scanned barcode"""
        self.scan_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n" + "="*50)
        print(f"📊 SCAN #{self.scan_count} SUCCESS")
        print(f"="*50)
        print(f"📱 Barcode: {barcode}")
        print(f"📏 Length: {len(barcode)}")
        print(f"🕒 Time: {timestamp}")
        print(f"🔢 Format: {self.detect_format(barcode)}")
        print(f"="*50)
        
        # Here you can integrate with your IoT Hub system
        # self.send_to_iot_hub(barcode)
        
    def detect_format(self, barcode):
        """Detect barcode format"""
        if barcode.isdigit():
            length = len(barcode)
            if length == 13:
                return "EAN-13"
            elif length == 12:
                return "UPC-A"
            elif length == 8:
                return "EAN-8"
            else:
                return f"Numeric ({length} digits)"
        else:
            return f"Alphanumeric ({len(barcode)} chars)"
    
    def test_scanner_methods(self):
        """Test different scanner input methods"""
        print("🧪 USB SCANNER INPUT TEST")
        print("=" * 50)
        print("Testing different methods to capture scanner input")
        
        methods = [
            ("Simple Input (Recommended)", self.simple_input_method),
            ("Direct Raw Input", self.read_scanner_input)
        ]
        
        for i, (name, method) in enumerate(methods, 1):
            print(f"\n{i}. {name}")
            choice = input("Try this method? (y/n/q): ").lower()
            
            if choice == 'q':
                break
            elif choice == 'y':
                try:
                    method()
                    if self.scan_count > 0:
                        print(f"✅ Method '{name}' worked!")
                        return True
                except Exception as e:
                    print(f"❌ Method '{name}' failed: {e}")
        
        return False

def main():
    """Main function"""
    scanner = DirectUSBScanner()
    
    print("🚀 DIRECT USB BARCODE SCANNER")
    print("=" * 50)
    print("This will test your USB scanner with direct input methods")
    
    # Test if scanner works
    success = scanner.test_scanner_methods()
    
    if success:
        print(f"\n🎉 Scanner working successfully!")
    else:
        print(f"\n❌ Scanner test failed")
        print(f"💡 Make sure:")
        print(f"  1. USB scanner is connected")
        print(f"  2. Scanner is in keyboard emulation mode")
        print(f"  3. Scanner LED lights up when scanning")

if __name__ == '__main__':
    main()
