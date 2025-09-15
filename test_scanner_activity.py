#!/usr/bin/env python3
"""
Test if the USB scanner is sending any data at all
"""

import os
import time
import sys

def test_scanner_activity():
    """Test if scanner is sending any data"""
    print("🔍 Testing USB Scanner Activity")
    print("=" * 40)

    # Find HID device
    hid_devices = ['/dev/hidraw0', '/dev/hidraw1', '/dev/hidraw2', '/dev/hidraw3']

    device_path = None
    for dev in hid_devices:
        if os.path.exists(dev):
            device_path = dev
            break

    if not device_path:
        print("❌ No HID devices found!")
        print("Make sure your USB barcode scanner is connected.")
        return

    print(f"✅ Found HID device: {device_path}")

    # Check permissions
    if not os.access(device_path, os.R_OK):
        print(f"❌ No read permission for {device_path}")
        print("Try running with sudo: sudo python3 test_scanner_activity.py")
        return

    print(f"✅ Have read permission for {device_path}")
    print("\n📡 Listening for scanner data...")
    print("Scan a barcode now (or press Ctrl+C to stop)")
    print("=" * 40)

    try:
        with open(device_path, 'rb') as fp:
            data_count = 0
            start_time = time.time()

            while True:
                # Read data with timeout
                data = fp.read(8)
                current_time = time.time()

                if data:
                    data_count += 1
                    data_bytes = [b for b in data]
                    data_hex = [f"{b:02x}" for b in data_bytes]
                    non_zero = sum(1 for b in data_bytes if b > 0)

                    print(f"[{current_time - start_time:.1f}s] Data #{data_count}: {data_bytes} (hex: {data_hex}) - {non_zero} non-zero bytes")

                    # If we get data, show more details
                    if data_count <= 5:  # Show details for first 5 packets
                        print(f"  Raw bytes: {data}")
                        print(f"  As string: {data.decode('latin-1', errors='ignore')}")
                else:
                    # No data, just show we're waiting
                    if data_count == 0 and int(current_time - start_time) % 5 == 0:
                        print(f"[{current_time - start_time:.1f}s] Waiting for scanner data...")

                time.sleep(0.01)  # Small delay

    except KeyboardInterrupt:
        print(f"\n\n👋 Test stopped after {data_count} data packets received")
        if data_count == 0:
            print("⚠️ No data received from scanner!")
            print("Possible issues:")
            print("  - Scanner not powered on")
            print("  - Wrong scanner type (not HID)")
            print("  - Scanner needs different configuration")
            print("  - Try a different USB port")
        else:
            print(f"✅ Scanner is sending data ({data_count} packets)")

    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    test_scanner_activity()