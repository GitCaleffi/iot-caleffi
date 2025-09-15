#!/usr/bin/env python3
"""
Keyboard Mode Scanner Test
- Reads scanner input as if it were a keyboard
- Works when scanner is in keyboard emulation mode
"""

import sys
import select
import termios
import tty

def read_keyboard_input():
    """Read input as if scanner is typing on keyboard"""
    print("🔍 Scanner Keyboard Mode Test")
    print("=" * 40)
    print("📱 Make sure your scanner is in KEYBOARD MODE")
    print("🔍 Scan a barcode now (it should type like a keyboard):")
    print("Press Enter after scanning, or Ctrl+C to exit\n")
    
    try:
        # Read input normally (like keyboard typing)
        barcode = input("Scan here: ")
        
        if barcode.strip():
            print(f"\n✅ Received: {barcode}")
            print(f"📏 Length: {len(barcode)}")
            print(f"🔢 Type: {detect_format(barcode)}")
            return barcode
        else:
            print("⚠️ No input received")
            return None
            
    except KeyboardInterrupt:
        print("\n👋 Stopped")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def detect_format(barcode):
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

def continuous_scan():
    """Continuous scanning mode"""
    print("\n🔄 Continuous Scanning Mode")
    print("Scan barcodes one by one, press Ctrl+C to stop\n")
    
    scan_count = 0
    
    try:
        while True:
            barcode = input(f"Scan #{scan_count + 1}: ")
            
            if barcode.strip():
                scan_count += 1
                print(f"  ✅ Got: {barcode} ({detect_format(barcode)})")
            else:
                print("  ⚠️ Empty scan")
                
    except KeyboardInterrupt:
        print(f"\n👋 Completed {scan_count} scans")

def main():
    """Main function"""
    print("⌨️ USB Scanner Keyboard Mode Test")
    print("=" * 50)
    print("This test assumes your scanner acts like a keyboard")
    print("If your scanner is NOT in keyboard mode, configure it first\n")
    
    # Single scan test
    result = read_keyboard_input()
    
    if result:
        print(f"\n🎉 Success! Your scanner works in keyboard mode")
        
        # Ask for continuous mode
        try:
            choice = input("\nDo continuous scanning? (y/n): ")
            if choice.lower().startswith('y'):
                continuous_scan()
        except KeyboardInterrupt:
            pass
    else:
        print(f"\n❌ Scanner not working in keyboard mode")
        print(f"💡 Try configuring your scanner for 'keyboard emulation'")
    
    print(f"\n✅ Test completed")

if __name__ == '__main__':
    main()
