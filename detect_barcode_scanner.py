#!/usr/bin/env python3
"""
Detect and identify actual USB barcode scanner devices
"""
import os
import subprocess
import sys

def get_usb_device_info():
    """Get detailed USB device information"""
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        print("📱 Connected USB devices:")
        print(result.stdout)
        return result.stdout
    except Exception as e:
        print(f"Error getting USB info: {e}")
        return ""

def get_input_devices():
    """Get input device information"""
    try:
        result = subprocess.run(['ls', '-la', '/dev/input/'], capture_output=True, text=True)
        print("\n📱 Input devices:")
        print(result.stdout)
        
        # Check for event devices
        event_devices = []
        for i in range(20):
            event_path = f'/dev/input/event{i}'
            if os.path.exists(event_path):
                event_devices.append(event_path)
        
        print(f"\n📱 Event devices found: {event_devices}")
        return event_devices
    except Exception as e:
        print(f"Error getting input devices: {e}")
        return []

def get_hid_devices():
    """Get HID device information with details"""
    hid_devices = []
    
    for i in range(10):
        hid_path = f'/dev/hidraw{i}'
        if os.path.exists(hid_path):
            try:
                # Get device info using udevadm
                result = subprocess.run(['udevadm', 'info', '--name=' + hid_path], 
                                      capture_output=True, text=True)
                
                print(f"\n📱 HID Device: {hid_path}")
                print("Device info:")
                for line in result.stdout.split('\n'):
                    if 'ID_VENDOR' in line or 'ID_MODEL' in line or 'ID_PRODUCT' in line:
                        print(f"  {line}")
                
                hid_devices.append({
                    'path': hid_path,
                    'info': result.stdout
                })
            except Exception as e:
                print(f"Error getting info for {hid_path}: {e}")
    
    return hid_devices

def identify_barcode_scanner():
    """Try to identify which device is the barcode scanner"""
    print("🔍 Identifying barcode scanner device...")
    
    # Common barcode scanner vendor/product keywords
    scanner_keywords = [
        'scanner', 'barcode', 'symbol', 'honeywell', 'zebra', 'datalogic', 
        'code', 'reader', 'handheld', 'pos', 'retail'
    ]
    
    hid_devices = get_hid_devices()
    
    scanner_candidates = []
    
    for device in hid_devices:
        device_info = device['info'].lower()
        
        # Check if device info contains scanner-related keywords
        for keyword in scanner_keywords:
            if keyword in device_info:
                scanner_candidates.append(device)
                print(f"✅ Potential barcode scanner: {device['path']} (contains '{keyword}')")
                break
    
    if scanner_candidates:
        print(f"\n🎯 Found {len(scanner_candidates)} potential barcode scanner(s)")
        return scanner_candidates
    else:
        print("\n⚠️ No obvious barcode scanner devices found")
        print("💡 Your barcode scanner might not have identifying keywords")
        return hid_devices

def main():
    print("🚀 USB Barcode Scanner Detection Tool")
    print("=" * 60)
    
    # Get USB device list
    get_usb_device_info()
    
    # Get input devices
    get_input_devices()
    
    # Identify barcode scanner
    scanner_devices = identify_barcode_scanner()
    
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    print("=" * 60)
    
    if scanner_devices:
        print("🎯 Recommended barcode scanner devices:")
        for i, device in enumerate(scanner_devices, 1):
            print(f"  {i}. {device['path']}")
    else:
        print("❌ No barcode scanner devices detected")
    
    print("\n💡 Tips:")
    print("• Try unplugging and reconnecting your barcode scanner")
    print("• Run 'lsusb' before and after connecting to see the difference")
    print("• Some scanners appear as keyboards - look for new /dev/input/event* devices")

if __name__ == "__main__":
    main()
