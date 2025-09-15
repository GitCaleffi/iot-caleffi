#!/usr/bin/env python3

import sys
import termios
import tty

def test_keyboard_input():
    """Test if barcode scanner sends keyboard input"""
    print("🔍 Barcode Scanner Keyboard Test")
    print("=" * 50)
    print("This will capture keyboard input directly.")
    print("Scan a barcode now - it should appear as typed text.")
    print("Press Ctrl+C to exit")
    print("=" * 50)
    
    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        # Set terminal to raw mode
        tty.setraw(sys.stdin.fileno())
        
        barcode = ""
        
        while True:
            char = sys.stdin.read(1)
            
            # Handle Ctrl+C
            if ord(char) == 3:
                break
            
            # Handle Enter (end of barcode)
            if ord(char) == 13 or ord(char) == 10:
                if barcode:
                    print(f"\n📦 Scanned Barcode: {barcode}")
                    print("🔍 Scan another barcode or Ctrl+C to exit")
                    barcode = ""
                continue
            
            # Handle printable characters
            if 32 <= ord(char) <= 126:
                barcode += char
                print(char, end='', flush=True)
            
    except KeyboardInterrupt:
        pass
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print("\n🛑 Test completed")

if __name__ == "__main__":
    test_keyboard_input()
