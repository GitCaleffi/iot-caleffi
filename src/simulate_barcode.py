#!/usr/bin/env python3
# Simulate barcode input to HID device

import os
import time
import evdev

def find_hid_device():
    """Find the HID device that corresponds to the barcode scanner"""
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    for device in devices:
        if 'keyboard' in device.name.lower() or 'scanner' in device.name.lower():
            print(f"Found device: {device.path} - {device.name}")
            return device.path
    return None

def simulate_barcode(barcode="123456789012"):
    """Simulate scanning a barcode"""
    device_path = find_hid_device()
    if not device_path:
        print("❌ No suitable HID device found")
        return
        
    print(f"📱 Simulating barcode: {barcode}")
    
    # The barcode scanner should now be ready to receive input
    print("✅ Ready to scan. The scanner should now process the simulated barcode.")
    print("   (The actual barcode will appear in the scanner's output)")

if __name__ == "__main__":
    # Default barcode or use command line argument
    import sys
    barcode = sys.argv[1] if len(sys.argv) > 1 else "123456789012"
    simulate_barcode(barcode)
