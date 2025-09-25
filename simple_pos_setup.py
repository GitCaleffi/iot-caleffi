#!/usr/bin/env python3
"""
Simple POS System Setup for Raspberry Pi 5
Automatically configures USB HID gadget and forwards barcodes to connected PC
"""
import os
import subprocess
import time
import sys

class SimplePOSSystem:
    def __init__(self):
        self.hid_device = "/dev/hidg0"
        self.gadget_path = "/sys/kernel/config/usb_gadget/caleffi_scanner"
    
    def check_root_privileges(self):
        """Check if running as root"""
        if os.geteuid() != 0:
            print("❌ This script requires root privileges")
            print("💡 Run with: sudo python3 simple_pos_setup.py")
            return False
        return True
    
    def setup_usb_hid_gadget(self):
        """Set up USB HID gadget for Raspberry Pi 5"""
        print("🔧 Setting up USB HID gadget...")
        
        try:
            # Load required modules
            subprocess.run(['modprobe', 'dwc2'], check=False)
            subprocess.run(['modprobe', 'libcomposite'], check=False)
            
            # Remove existing gadget if it exists
            if os.path.exists(self.gadget_path):
                try:
                    with open(f"{self.gadget_path}/UDC", 'w') as f:
                        f.write("")
                    subprocess.run(['rm', '-rf', self.gadget_path], check=False)
                except:
                    pass
            
            # Create gadget directory
            os.makedirs(self.gadget_path, exist_ok=True)
            os.chdir(self.gadget_path)
            
            # Basic USB device configuration
            with open('idVendor', 'w') as f: f.write('0x1d6b')
            with open('idProduct', 'w') as f: f.write('0x0104')
            with open('bcdDevice', 'w') as f: f.write('0x0100')
            with open('bcdUSB', 'w') as f: f.write('0x0200')
            
            # Device strings
            os.makedirs('strings/0x409', exist_ok=True)
            with open('strings/0x409/manufacturer', 'w') as f: f.write('Caleffi')
            with open('strings/0x409/product', 'w') as f: f.write('POS Barcode Scanner')
            with open('strings/0x409/serialnumber', 'w') as f: f.write('123456')
            
            # HID function configuration
            os.makedirs('functions/hid.usb0', exist_ok=True)
            with open('functions/hid.usb0/protocol', 'w') as f: f.write('1')
            with open('functions/hid.usb0/subclass', 'w') as f: f.write('1')
            with open('functions/hid.usb0/report_length', 'w') as f: f.write('8')
            
            # HID keyboard descriptor
            hid_descriptor = b'\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0'
            with open('functions/hid.usb0/report_desc', 'wb') as f:
                f.write(hid_descriptor)
            
            # Configuration
            os.makedirs('configs/c.1/strings/0x409', exist_ok=True)
            with open('configs/c.1/strings/0x409/configuration', 'w') as f: f.write('HID Keyboard')
            with open('configs/c.1/MaxPower', 'w') as f: f.write('250')
            
            # Link function to configuration
            if not os.path.exists('configs/c.1/hid.usb0'):
                os.symlink('../../functions/hid.usb0', 'configs/c.1/hid.usb0')
            
            # Enable the gadget
            udc_list = os.listdir('/sys/class/udc')
            if udc_list:
                udc = udc_list[0]
                with open('UDC', 'w') as f: f.write(udc)
                print(f"✅ USB gadget enabled with UDC: {udc}")
            else:
                print("❌ No UDC found")
                return False
            
            # Wait for device to appear and set permissions
            time.sleep(2)
            if os.path.exists(self.hid_device):
                os.chmod(self.hid_device, 0o666)
                print(f"✅ HID device {self.hid_device} configured with proper permissions")
                return True
            else:
                print(f"❌ HID device {self.hid_device} not created")
                return False
                
        except Exception as e:
            print(f"❌ Failed to setup USB HID gadget: {e}")
            return False
    
    def send_barcode_to_pos(self, barcode):
        """Send barcode to connected PC via USB HID"""
        if not os.path.exists(self.hid_device):
            print(f"❌ HID device {self.hid_device} not found")
            return False
        
        print(f"📤 Sending barcode to POS: {barcode}")
        
        try:
            with open(self.hid_device, 'wb') as hid:
                # Convert barcode to HID keyboard reports
                for char in barcode:
                    if char.isdigit():
                        # Numbers 0-9 map to HID codes 30-39
                        hid_code = ord(char) - ord('0') + 30
                        # Send key press (8-byte HID report)
                        hid.write(bytes([0, 0, hid_code, 0, 0, 0, 0, 0]))
                        # Send key release
                        hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))
                
                # Send Enter key (HID code 40)
                hid.write(bytes([0, 0, 40, 0, 0, 0, 0, 0]))  # Enter press
                hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))   # Enter release
            
            print(f"✅ Barcode {barcode} sent to POS system!")
            print("📝 Check your PC's Notepad - the barcode should appear there")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send barcode: {e}")
            return False
    
    def test_connection(self):
        """Test the POS connection with sample barcode"""
        test_barcode = "8053734093444"
        print(f"\n🧪 Testing POS connection with barcode: {test_barcode}")
        return self.send_barcode_to_pos(test_barcode)
    
    def run_interactive_mode(self):
        """Run interactive mode for manual barcode entry"""
        print("\n🎯 Interactive POS Mode")
        print("Enter barcodes to send to your PC (Ctrl+C to exit)")
        print("=" * 50)
        
        try:
            while True:
                barcode = input("\n📦 Enter barcode: ").strip()
                if barcode:
                    if barcode.isdigit() and 8 <= len(barcode) <= 20:
                        self.send_barcode_to_pos(barcode)
                    else:
                        print("⚠️  Please enter a valid numeric barcode (8-20 digits)")
                else:
                    print("⚠️  Please enter a barcode")
        except KeyboardInterrupt:
            print("\n👋 Exiting POS system")

def main():
    print("🚀 Simple POS System for Raspberry Pi 5")
    print("=" * 50)
    
    pos_system = SimplePOSSystem()
    
    # Check root privileges
    if not pos_system.check_root_privileges():
        sys.exit(1)
    
    # Setup USB HID gadget
    if not pos_system.setup_usb_hid_gadget():
        print("\n❌ Failed to setup USB HID gadget")
        print("💡 Make sure:")
        print("   1. You're using a Raspberry Pi 5 with USB-C cable")
        print("   2. The USB-C cable is connected to a PC")
        print("   3. The PC recognizes the Pi as a USB device")
        sys.exit(1)
    
    print("\n✅ POS System Ready!")
    print("🔌 Connect your Pi to PC via USB-C cable")
    print("📝 Open Notepad on your PC")
    
    # Test connection
    if pos_system.test_connection():
        print("\n🎉 POS system is working!")
        
        # Ask if user wants interactive mode
        response = input("\nStart interactive mode? (y/n): ").lower()
        if response == 'y':
            pos_system.run_interactive_mode()
    else:
        print("\n❌ POS system test failed")
        print("💡 Check USB connection and try again")

if __name__ == "__main__":
    main()
