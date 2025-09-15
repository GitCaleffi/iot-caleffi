#!/usr/bin/env python3
"""
Debug HID scanner data to understand what the scanner is sending
"""

import os
import time
import sys
from datetime import datetime

def find_hid_scanner_device():
    """Find HID barcode scanner device"""
    hid_devices = ['/dev/hidraw0', '/dev/hidraw1', '/dev/hidraw2', '/dev/hidraw3']

    for device_path in hid_devices:
        if os.path.exists(device_path):
            try:
                # Test if we can open the device
                with open(device_path, 'rb') as test_fp:
                    print(f"✅ Found HID device: {device_path}")
                    return device_path
            except PermissionError:
                print(f"⚠️ Permission denied for {device_path}. May need sudo.")
                return device_path  # Return it anyway, let caller handle permission
            except Exception as e:
                print(f"Cannot access {device_path}: {e}")
                continue

    print("❌ No HID scanner device found")
    return None

def debug_hid_scanner():
    """Debug what the HID scanner is actually sending"""
    print("🔍 HID Scanner Debug Mode")
    print("=" * 50)

    device_path = find_hid_scanner_device()
    if not device_path:
        print("No HID device found. Make sure your scanner is connected.")
        return

    print(f"📱 Reading from: {device_path}")
    print("🔍 Scan a barcode now...")
    print("Press Ctrl+C to stop debugging")
    print("=" * 50)

    try:
        with open(device_path, 'rb') as fp:
            scan_count = 0
            buffer_data = []

            while True:
                # Read 8-byte HID report
                data = fp.read(8)
                if not data:
                    continue

                current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                data_bytes = [b for b in data]
                data_hex = [f"{b:02x}" for b in data_bytes]

                # Check if this looks like barcode data (has non-zero bytes)
                has_data = any(b > 0 for b in data_bytes)

                if has_data:
                    scan_count += 1
                    print(f"\n[{current_time}] Scan #{scan_count}")
                    print(f"Raw bytes: {data_bytes}")
                    print(f"Hex codes: {data_hex}")

                    # Try to interpret as HID key codes
                    interpreted = []
                    for b in data_bytes:
                        if b > 0:
                            if 4 <= b <= 39:  # Letters and numbers
                                if 30 <= b <= 39:  # Numbers
                                    char = str((b - 29) % 10)
                                elif 4 <= b <= 29:  # Letters
                                    char = chr(ord('a') + (b - 4))
                                else:
                                    char = f"[{b}]"
                                interpreted.append(char)
                            elif b == 40:  # Enter
                                interpreted.append("[ENTER]")
                            elif b == 2:  # Shift
                                interpreted.append("[SHIFT]")
                            else:
                                interpreted.append(f"[{b}]")

                    print(f"Interpreted: {interpreted}")
                    print(f"As string: {''.join(c for c in interpreted if not c.startswith('['))}")

                    buffer_data.extend(data_bytes)

                    # Check for termination
                    if 40 in data_bytes:  # Enter key
                        print(f"🔚 Buffer complete! Total bytes: {len(buffer_data)}")
                        print(f"📊 Full buffer: {buffer_data}")
                        buffer_data = []  # Reset for next scan

                time.sleep(0.01)  # Small delay to prevent CPU hogging

    except KeyboardInterrupt:
        print(f"\n\n👋 Debug stopped after {scan_count} data packets")
        print("✅ Debug session complete")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    debug_hid_scanner()