#!/usr/bin/env python3

import os
import glob

def test_all_hid_devices():
    """Test all HID devices to see which one receives barcode data"""
    devices = glob.glob('/dev/hidraw*')
    
    print(f"Found HID devices: {devices}")
    
    for device in devices:
        print(f"\n🔍 Testing {device}...")
        try:
            with open(device, 'rb') as fp:
                print(f"✅ Opened {device} - scan a barcode now (5 second timeout)")
                
                # Read for 5 seconds or until data received
                import select
                ready, _, _ = select.select([fp], [], [], 5.0)
                
                if ready:
                    data = fp.read(8)
                    print(f"📱 Raw data from {device}: {[hex(b) for b in data]}")
                    return device
                else:
                    print(f"⏰ No data received from {device}")
                    
        except PermissionError:
            print(f"❌ Permission denied for {device}")
        except Exception as e:
            print(f"❌ Error with {device}: {e}")
    
    return None

if __name__ == "__main__":
    print("🔍 HID Device Scanner Test")
    print("Scan a barcode when prompted...")
    test_all_hid_devices()
