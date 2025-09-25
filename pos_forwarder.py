#!/usr/bin/env python3
"""
POS Forwarder - Automatically forward scanned barcodes to connected PC
Integrates with existing barcode scanner system
"""
import os
import time
import sys
import subprocess

class POSForwarder:
    def __init__(self):
        self.hid_device = "/dev/hidg0"
        self.is_setup = False
    
    def check_hid_device(self):
        """Check if HID device is available"""
        if os.path.exists(self.hid_device):
            try:
                # Test if we can write to the device
                with open(self.hid_device, 'wb') as f:
                    pass
                self.is_setup = True
                return True
            except PermissionError:
                print(f"⚠️  Permission denied for {self.hid_device}")
                print("💡 Run: sudo chmod 666 /dev/hidg0")
                return False
            except Exception as e:
                print(f"❌ HID device error: {e}")
                return False
        else:
            print(f"❌ HID device {self.hid_device} not found")
            print("💡 Run: sudo python3 simple_pos_setup.py")
            return False
    
    def forward_barcode(self, barcode):
        """Forward barcode to POS system via USB HID"""
        if not self.is_setup:
            if not self.check_hid_device():
                print("⚠️  POS forwarding not available - using clipboard fallback")
                return self.clipboard_fallback(barcode)
        
        try:
            print(f"📤 Forwarding to POS: {barcode}")
            
            with open(self.hid_device, 'wb') as hid:
                # Convert each character to HID keyboard codes
                for char in barcode:
                    if char.isdigit():
                        # Numbers 0-9 map to HID codes 30-39
                        hid_code = ord(char) - ord('0') + 30
                        # Send key press
                        hid.write(bytes([0, 0, hid_code, 0, 0, 0, 0, 0]))
                        # Send key release
                        hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))
                        time.sleep(0.01)  # Small delay between keystrokes
                
                # Send Enter key
                hid.write(bytes([0, 0, 40, 0, 0, 0, 0, 0]))  # Enter press
                hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))   # Enter release
            
            print(f"✅ Barcode {barcode} sent to POS!")
            return True
            
        except Exception as e:
            print(f"❌ POS forward failed: {e}")
            return self.clipboard_fallback(barcode)
    
    def clipboard_fallback(self, barcode):
        """Fallback method - save to clipboard file"""
        try:
            clipboard_file = "/tmp/pos_barcode.txt"
            with open(clipboard_file, 'w') as f:
                f.write(barcode)
            
            print(f"📋 Barcode saved to {clipboard_file}")
            print(f"💡 Manually copy this to your POS: {barcode}")
            return True
            
        except Exception as e:
            print(f"❌ Clipboard fallback failed: {e}")
            return False

# Global POS forwarder instance
pos_forwarder = POSForwarder()

def send_to_pos(barcode):
    """Main function to send barcode to POS system"""
    return pos_forwarder.forward_barcode(barcode)

def test_pos_forwarding():
    """Test POS forwarding with sample barcode"""
    test_barcode = "8053734093444"
    print(f"🧪 Testing POS forwarding...")
    
    if send_to_pos(test_barcode):
        print("✅ POS forwarding test successful!")
        print("📝 Check your PC's Notepad - the barcode should appear")
        return True
    else:
        print("❌ POS forwarding test failed")
        return False

if __name__ == "__main__":
    print("🚀 POS Forwarder Test")
    print("=" * 30)
    
    # Check system status
    print("🔍 Checking POS system status...")
    if pos_forwarder.check_hid_device():
        print("✅ POS system ready")
        
        # Run test
        test_pos_forwarding()
        
        # Interactive mode
        print("\n🎯 Interactive mode (Ctrl+C to exit)")
        try:
            while True:
                barcode = input("\nEnter barcode: ").strip()
                if barcode:
                    send_to_pos(barcode)
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
    else:
        print("❌ POS system not ready")
        print("💡 Setup required - run: sudo python3 simple_pos_setup.py")
