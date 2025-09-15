#!/usr/bin/env python3

import os
import glob

def find_hid_device():
    """Find HID device for barcode scanner"""
    hid_devices = glob.glob('/dev/hidraw*')
    
    if not hid_devices:
        print("❌ No HID devices found")
        return None
    
    print(f"📱 Found HID devices: {hid_devices}")
    
    # Try each device
    for device in hid_devices:
        try:
            # Check permissions
            stat = os.stat(device)
            print(f"📱 {device}: permissions = {oct(stat.st_mode)[-3:]}")
            
            # Try to open for reading
            with open(device, 'rb') as f:
                print(f"✅ {device}: Successfully opened for reading")
                return device
        except PermissionError:
            print(f"❌ {device}: Permission denied")
        except Exception as e:
            print(f"⚠️ {device}: Error - {e}")
    
    return None

def test_hid_scanner():
    """Test HID scanner functionality"""
    print("🔍 Testing HID Scanner...")
    
    device = find_hid_device()
    if not device:
        print("❌ No accessible HID device found")
        return
    
    print(f"📱 Using device: {device}")
    print("🔍 Scan a barcode now (Ctrl+C to stop)...")
    
    try:
        with open(device, 'rb') as fp:
            barcode = ''
            
            while True:
                buffer = fp.read(8)
                if not buffer:
                    continue
                
                for b in buffer:
                    code = b if isinstance(b, int) else ord(b)
                    
                    if code == 0:
                        continue
                    
                    if code == 40:  # ENTER key
                        if barcode.strip():
                            print(f"📦 Scanned: {barcode}")
                            barcode = ''
                    else:
                        # Simple character mapping for numbers
                        char_map = {
                            30: '1', 31: '2', 32: '3', 33: '4', 34: '5',
                            35: '6', 36: '7', 37: '8', 38: '9', 39: '0'
                        }
                        if code in char_map:
                            barcode += char_map[code]
                        else:
                            print(f"Debug: Unknown code {code}")
                            
    except KeyboardInterrupt:
        print("\n🛑 Test stopped")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_hid_scanner()
