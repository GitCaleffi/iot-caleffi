#!/usr/bin/env python3
"""
Test script to read raw HID data from barcode scanner
This will help debug why scanned barcodes aren't being processed
"""

import sys
import time
from datetime import datetime

def test_raw_hid_reading(device_path='/dev/hidraw0'):
    """Read raw HID data to see what the scanner is sending"""
    print(f"🔍 Testing raw HID data reading from: {device_path}")
    print("Scan a barcode now... (Press Ctrl+C to stop)")
    print("=" * 60)

    try:
        with open(device_path, 'rb') as fp:
            print("✅ Successfully opened HID device")
            print("Waiting for data...")

            while True:
                # Read 8 bytes (standard HID report size)
                buffer = fp.read(8)

                if buffer:
                    # Convert bytes to integers for display
                    data_bytes = [b if isinstance(b, int) else ord(b) for b in buffer]

                    # Only show non-zero data (filter out empty reports)
                    if any(b > 0 for b in data_bytes):
                        timestamp = datetime.now().strftime('%H:%M:%S.%f')
                        print(f"[{timestamp}] Raw HID data: {data_bytes}")

                        # Try to decode as characters
                        chars = []
                        for b in data_bytes:
                            if b > 0:
                                if 4 <= b <= 39:  # HID key codes for letters/numbers
                                    # Simple mapping for common keys
                                    if 4 <= b <= 29:  # a-z
                                        chars.append(chr(ord('a') + (b - 4)))
                                    elif 30 <= b <= 39:  # 1-0
                                        chars.append(chr(ord('1') + (b - 30)))
                                    elif b == 40:  # Enter
                                        chars.append('[ENTER]')
                                else:
                                    chars.append(f'[{b}]')

                        if chars:
                            print(f"                Decoded: {''.join(chars)}")

                time.sleep(0.01)  # Small delay to prevent CPU hogging

    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user")
    except PermissionError:
        print(f"❌ Permission denied for {device_path}")
        print("💡 Try running with: sudo python3 test_raw_hid.py")
    except Exception as e:
        print(f"❌ Error reading HID data: {e}")

if __name__ == "__main__":
    device_path = '/dev/hidraw0'  # Default device

    if len(sys.argv) > 1:
        device_path = sys.argv[1]

    test_raw_hid_reading(device_path)