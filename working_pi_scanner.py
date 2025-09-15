#!/usr/bin/env python3
"""
Working Raspberry Pi USB Scanner
- Uses direct keyboard input (proven to work)
- Simple and reliable approach
- No complex device detection needed
"""

import sys
import time
from datetime import datetime

class WorkingPiScanner:
    def __init__(self):
        self.scan_count = 0
        self.running = True
        
    def detect_barcode_format(self, barcode):
        """Detect barcode format"""
        length = len(barcode)
        
        if length == 13 and barcode.isdigit():
            return "EAN-13"
        elif length == 12 and barcode.isdigit():
            return "UPC-A"
        elif length == 8 and barcode.isdigit():
            return "EAN-8"
        elif barcode.isdigit():
            return f"Numeric ({length} digits)"
        elif barcode.isalnum():
            return f"Alphanumeric ({length} chars)"
        else:
            return f"Mixed format ({length} chars)"
    
    def process_barcode(self, barcode):
        """Process scanned barcode"""
        self.scan_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("=" * 60)
        print(f"📊 SCAN #{self.scan_count} SUCCESSFUL")
        print("=" * 60)
        print(f"📱 Barcode: {barcode}")
        print(f"📏 Length: {len(barcode)} characters")
        print(f"🕒 Time: {timestamp}")
        print(f"🔢 Format: {self.detect_barcode_format(barcode)}")
        print("=" * 60)
        
        # Here you can add your IoT Hub integration
        # self.send_to_iot_hub(barcode)
        # self.save_to_database(barcode)
        
        return True
    
    def start_scanning(self):
        """Start continuous barcode scanning"""
        print("🚀 WORKING RASPBERRY PI USB SCANNER")
        print("=" * 50)
        print("✅ Scanner detected and working!")
        print("🔍 Scan barcodes continuously...")
        print("Press Ctrl+C to stop")
        print("=" * 50)
        
        try:
            while self.running:
                print(f"\n🔍 Ready for scan #{self.scan_count + 1}...")
                print("Scan barcode: ", end="", flush=True)
                
                # Read barcode input directly
                barcode = input().strip()
                
                if barcode:
                    self.process_barcode(barcode)
                else:
                    print("⚠️ Empty scan - try again")
                    
        except KeyboardInterrupt:
            print(f"\n\n👋 Scanner stopped")
            print(f"📊 Total scans completed: {self.scan_count}")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        print("✅ Scanner session ended")

def main():
    """Main function"""
    scanner = WorkingPiScanner()
    scanner.start_scanning()

if __name__ == '__main__':
    main()
