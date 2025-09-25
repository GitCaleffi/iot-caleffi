#!/usr/bin/env python3
"""
Simple POS Forwarder - File-based barcode forwarding
Works on any system without USB HID or network setup
"""
import os
import time
import json
from datetime import datetime

class SimplePOSForwarder:
    def __init__(self):
        self.pos_file = "/tmp/pos_barcodes.txt"
        self.pos_json = "/tmp/pos_barcodes.json"
        self.history_file = "/tmp/pos_history.txt"
        
    def send_barcode_to_pos(self, barcode):
        """Send barcode to POS system via file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Write to simple text file
            with open(self.pos_file, 'w') as f:
                f.write(f"{barcode}\n")
            
            # Write to JSON file with metadata
            pos_data = {
                "barcode": barcode,
                "timestamp": timestamp,
                "status": "ready_for_pos"
            }
            
            with open(self.pos_json, 'w') as f:
                json.dump(pos_data, f, indent=2)
            
            # Append to history
            with open(self.history_file, 'a') as f:
                f.write(f"{timestamp} - {barcode}\n")
            
            print(f"✅ Barcode saved: {barcode}")
            print(f"📄 POS File: {self.pos_file}")
            print(f"📋 Copy this barcode to your POS: {barcode}")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to save barcode: {e}")
            return False
    
    def get_latest_barcode(self):
        """Get the latest barcode from POS file"""
        try:
            if os.path.exists(self.pos_file):
                with open(self.pos_file, 'r') as f:
                    return f.read().strip()
            return None
        except:
            return None
    
    def show_barcode_display(self, barcode):
        """Show barcode in a clear display format"""
        print("\n" + "=" * 50)
        print("📦 BARCODE FOR POS SYSTEM")
        print("=" * 50)
        print(f"   {barcode}")
        print("=" * 50)
        print(f"📄 Saved to: {self.pos_file}")
        print("💡 Copy the barcode above to your POS system")
        print("=" * 50 + "\n")
    
    def show_history(self):
        """Show barcode history"""
        try:
            if os.path.exists(self.history_file):
                print("\n📋 Barcode History:")
                print("-" * 40)
                with open(self.history_file, 'r') as f:
                    lines = f.readlines()
                    for line in lines[-10:]:  # Show last 10
                        print(line.strip())
                print("-" * 40)
            else:
                print("📋 No barcode history found")
        except Exception as e:
            print(f"❌ Error reading history: {e}")

def send_to_pos(barcode):
    """Main function to send barcode to POS"""
    forwarder = SimplePOSForwarder()
    success = forwarder.send_barcode_to_pos(barcode)
    if success:
        forwarder.show_barcode_display(barcode)
    return success

def test_pos_system():
    """Test the POS system with sample barcode"""
    test_barcode = "8053734093444"
    print("🧪 Testing POS system...")
    return send_to_pos(test_barcode)

def interactive_mode():
    """Run interactive barcode entry mode"""
    forwarder = SimplePOSForwarder()
    
    print("🎯 Interactive POS Mode")
    print("Enter barcodes to send to POS system")
    print("Commands: 'history' to show history, 'quit' to exit")
    print("-" * 50)
    
    try:
        while True:
            barcode = input("\n📦 Enter barcode (or command): ").strip()
            
            if barcode.lower() == 'quit':
                break
            elif barcode.lower() == 'history':
                forwarder.show_history()
            elif barcode:
                if barcode.isdigit() and 8 <= len(barcode) <= 20:
                    success = forwarder.send_barcode_to_pos(barcode)
                    if success:
                        forwarder.show_barcode_display(barcode)
                else:
                    print("⚠️  Please enter a valid numeric barcode (8-20 digits)")
            else:
                print("⚠️  Please enter a barcode or command")
                
    except KeyboardInterrupt:
        print("\n👋 Exiting POS system")

def main():
    print("🚀 Simple POS Forwarder")
    print("=" * 30)
    
    # Test the system
    if test_pos_system():
        print("✅ POS system working!")
        
        # Show file locations
        print(f"\n📁 POS Files:")
        print(f"   Text: /tmp/pos_barcodes.txt")
        print(f"   JSON: /tmp/pos_barcodes.json")
        print(f"   History: /tmp/pos_history.txt")
        
        # Ask for interactive mode
        response = input("\nStart interactive mode? (y/n): ").lower()
        if response == 'y':
            interactive_mode()
    else:
        print("❌ POS system test failed")

if __name__ == "__main__":
    main()
