#!/usr/bin/env python3
import sys
import os
import subprocess

# Test POS forwarding for barcode 8053734093444
test_barcode = "8053734093444"

print(f"🧪 Testing POS forwarding for: {test_barcode}")

# Check if HID device exists
hid_device = "/dev/hidg0"
if os.path.exists(hid_device):
    print(f"✅ HID device {hid_device} found")
    try:
        # Simple HID test - write barcode as keyboard input
        with open(hid_device, 'wb') as hid:
            # Convert each digit to HID keyboard codes
            hid_data = bytearray()
            for char in test_barcode:
                if char.isdigit():
                    hid_code = ord(char) - ord('0') + 30  # HID codes 30-39 for 0-9
                    hid_data.extend([0, 0, hid_code, 0, 0, 0, 0, 0])
            # Add Enter key
            hid_data.extend([0, 0, 40, 0, 0, 0, 0, 0])
            hid.write(bytes(hid_data))
        print(f"✅ Barcode {test_barcode} sent via USB HID to POS!")
    except Exception as e:
        print(f"❌ HID write failed: {e}")
else:
    print(f"❌ HID device {hid_device} not found")
    print("⚠️  USB HID gadget not configured")
    
    # Try alternative - write to file for manual copy
    try:
        with open('/tmp/pos_barcode.txt', 'w') as f:
            f.write(test_barcode)
        print(f"📄 Barcode written to /tmp/pos_barcode.txt")
        print(f"💡 You can manually copy this to your POS system")
        
        # Show the barcode clearly
        print(f"\n📦 BARCODE FOR POS: {test_barcode}")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ File write failed: {e}")

# Check if we can detect the connected PC
print(f"\n🔍 Checking USB connections...")
try:
    result = subprocess.run(['lsusb'], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print("USB devices:")
        for line in result.stdout.split('\n'):
            if line.strip():
                print(f"  {line}")
except:
    print("Could not check USB devices")
