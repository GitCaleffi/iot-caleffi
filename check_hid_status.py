#!/usr/bin/env python3
"""
Check USB HID status and test POS forwarding
"""
import os
import subprocess

def check_hid_status():
    """Check if USB HID is properly configured"""
    print("🔍 Checking USB HID status...")
    
    # Check if HID device exists
    hid_device = "/dev/hidg0"
    if os.path.exists(hid_device):
        print(f"✅ HID device {hid_device} found!")
        
        # Check permissions
        stat = os.stat(hid_device)
        mode = oct(stat.st_mode)[-3:]
        print(f"📋 Permissions: {mode}")
        
        if mode == "666":
            print("✅ Permissions are correct")
        else:
            print("⚠️  Permissions may need fixing (should be 666)")
        
        return True
    else:
        print(f"❌ HID device {hid_device} not found")
        print("💡 Run: sudo ./fix_pos.sh")
        return False

def test_barcode_forwarding():
    """Test forwarding barcode 8053734093444"""
    barcode = "8053734093444"
    hid_device = "/dev/hidg0"
    
    if not os.path.exists(hid_device):
        print(f"❌ Cannot test - {hid_device} not found")
        return False
    
    print(f"🧪 Testing barcode forwarding: {barcode}")
    
    try:
        with open(hid_device, 'wb') as hid:
            # Convert barcode to HID keyboard codes
            hid_data = bytearray()
            
            for char in barcode:
                if char.isdigit():
                    # Numbers 0-9 map to HID codes 30-39
                    hid_code = ord(char) - ord('0') + 30
                    # HID report: modifier, reserved, keycode, reserved...
                    hid_data.extend([0, 0, hid_code, 0, 0, 0, 0, 0])
                    # Key release
                    hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])
            
            # Add Enter key (HID code 40)
            hid_data.extend([0, 0, 40, 0, 0, 0, 0, 0])
            hid_data.extend([0, 0, 0, 0, 0, 0, 0, 0])
            
            hid.write(bytes(hid_data))
        
        print(f"✅ Barcode {barcode} sent to POS system!")
        print("📝 Check your Notepad - the barcode should appear there")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send barcode: {e}")
        return False

def check_usb_gadget_config():
    """Check USB gadget configuration"""
    print("\n🔧 Checking USB gadget configuration...")
    
    gadget_path = "/sys/kernel/config/usb_gadget/caleffi_scanner"
    if os.path.exists(gadget_path):
        print("✅ USB gadget configured")
        
        # Check if UDC is enabled
        udc_path = f"{gadget_path}/UDC"
        if os.path.exists(udc_path):
            with open(udc_path, 'r') as f:
                udc = f.read().strip()
            if udc:
                print(f"✅ UDC enabled: {udc}")
            else:
                print("❌ UDC not enabled")
        else:
            print("❌ UDC file not found")
    else:
        print("❌ USB gadget not configured")
        print("💡 Run: sudo ./fix_pos.sh")

if __name__ == "__main__":
    print("🚀 USB HID Status Check")
    print("=" * 50)
    
    # Check HID status
    hid_ready = check_hid_status()
    
    # Check gadget config
    check_usb_gadget_config()
    
    # Test if ready
    if hid_ready:
        print("\n🎯 Ready to test POS forwarding!")
        response = input("Send test barcode 8053734093444 to POS? (y/n): ")
        if response.lower() == 'y':
            test_barcode_forwarding()
    else:
        print("\n⚠️  USB HID not ready. Please run: sudo ./fix_pos.sh")
