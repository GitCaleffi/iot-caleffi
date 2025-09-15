#!/usr/bin/env python3
# Test HID device access

import os
import sys

def check_hid_access():
    hid_devices = [f'/dev/hidraw{i}' for i in range(5)]
    
    print("🔍 Checking HID device access...")
    
    for dev in hid_devices:
        if os.path.exists(dev):
            print(f"\n✅ Found HID device: {dev}")
            print(f"   Exists: {os.path.exists(dev)}")
            print(f"   Readable: {os.access(dev, os.R_OK)}")
            print(f"   Writable: {os.access(dev, os.W_OK)}")
            try:
                with open(dev, 'rb') as f:
                    print("   Successfully opened for reading!")
            except Exception as e:
                print(f"   Error opening: {e}")
        else:
            print(f"\n❌ Device not found: {dev}")

if __name__ == "__main__":
    check_hid_access()
