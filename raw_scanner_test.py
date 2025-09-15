#!/usr/bin/env python3
"""
Raw USB Scanner Test - Shows exactly what your scanner sends
"""

import sys
import os

def test_raw_input(device_path):
    """Show raw bytes from scanner"""
    print(f"📱 Reading raw data from {device_path}")
    print("🔍 Scan a barcode now...")
    print("Press Ctrl+C to stop\n")
    
    try:
        with open(device_path, 'rb') as fp:
            packet_count = 0
            
            while packet_count < 50:  # Limit to 50 packets
                buffer = fp.read(8)
                
                if any(b != 0 for b in buffer):
                    packet_count += 1
                    non_zero = [b for b in buffer if b != 0]
                    
                    print(f"Packet {packet_count}: {non_zero} -> {[hex(b) for b in non_zero]}")
                    
                    # Show what these would be as keys
                    for b in non_zero:
                        if b == 40:
                            print("  -> ENTER key detected (end of barcode)")
                        elif b == 2:
                            print("  -> SHIFT key detected")
                        elif 30 <= b <= 39:
                            num = str(b - 29) if b != 39 else '0'
                            print(f"  -> Number key: {num}")
                        elif 4 <= b <= 29:
                            letter = chr(ord('a') + b - 4)
                            print(f"  -> Letter key: {letter}")
                    
                    if 40 in buffer:  # Enter key - end of barcode
                        print("\n✅ End of barcode detected")
                        break
                        
    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Test raw scanner input"""
    print("🔧 Raw USB Scanner Test")
    print("=" * 30)
    
    if os.geteuid() != 0:
        print("❌ Need root access. Run with: sudo python3 raw_scanner_test.py")
        return
    
    # Test the device that was working
    device = "/dev/hidraw0"
    if os.path.exists(device):
        test_raw_input(device)
    else:
        print(f"❌ Device {device} not found")

if __name__ == '__main__':
    main()
