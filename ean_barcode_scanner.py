#!/usr/bin/env python3
"""
EAN Barcode Scanner with Quantity Tracking
- Validates EAN barcodes (8-13 digits)
- Tracks quantity per barcode
- Updates quantity on repeated scans
"""

import os
import json
from datetime import datetime

# HID key mapping for normal keys
hid = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j',
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's',
    23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: 'ENTER', 44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\',
    51: ';', 52: "'", 53: '`', 54: ',', 55: '.', 56: '/'
}

# HID key mapping for shifted characters
hid_shift = {
    4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J',
    14: 'K', 15: 'L', 16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S',
    23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y', 29: 'Z',
    30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')',
    44: ' ', 45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<',
    55: '>', 56: '?'
}

DEVICE_PATH = '/dev/hidraw0'
INVENTORY_FILE = 'barcode_inventory.json'

class BarcodeInventory:
    def __init__(self):
        self.inventory = self.load_inventory()
    
    def load_inventory(self):
        """Load inventory from JSON file"""
        if os.path.exists(INVENTORY_FILE):
            try:
                with open(INVENTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_inventory(self):
        """Save inventory to JSON file"""
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(self.inventory, f, indent=2)
    
    def is_valid_ean(self, barcode):
        """Validate EAN barcode (8-13 digits)"""
        if not barcode.isdigit():
            return False
        return 8 <= len(barcode) <= 13
    
    def add_barcode(self, barcode):
        """Add or update barcode quantity"""
        if not self.is_valid_ean(barcode):
            return False, "Invalid EAN: Must be 8-13 digits"
        
        if barcode in self.inventory:
            self.inventory[barcode]['quantity'] += 1
            self.inventory[barcode]['last_scanned'] = datetime.now().isoformat()
            action = "Updated"
        else:
            self.inventory[barcode] = {
                'quantity': 1,
                'first_scanned': datetime.now().isoformat(),
                'last_scanned': datetime.now().isoformat()
            }
            action = "Added"
        
        self.save_inventory()
        return True, action
    
    def get_summary(self):
        """Get inventory summary"""
        total_items = len(self.inventory)
        total_quantity = sum(item['quantity'] for item in self.inventory.values())
        return total_items, total_quantity

def read_barcode(device, inventory):
    """Read barcode from the HID device"""
    try:
        with open(device, 'rb') as fp:
            print(f"📱 Reading from {device}")
            print("🔍 Scan EAN barcodes (8-13 digits)... (Ctrl+C to stop)\n")
            barcode = ''
            shift = False
            
            while True:
                buffer = fp.read(8)
                for b in buffer:
                    code = b if isinstance(b, int) else ord(b)

                    if code == 0:
                        continue

                    if code == 40:  # ENTER key
                        if barcode.strip():
                            process_barcode(barcode.strip(), inventory)
                        barcode = ''
                    elif code == 2:  # SHIFT key
                        shift = True
                    else:
                        if shift:
                            barcode += hid_shift.get(code, '')
                            shift = False
                        else:
                            barcode += hid.get(code, '')
                            
    except PermissionError:
        print(f"❌ Permission denied for {device}. Try running with sudo.")
    except Exception as e:
        print(f"❌ Error reading from {device}: {e}")

def process_barcode(barcode, inventory):
    """Process scanned barcode"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    success, message = inventory.add_barcode(barcode)
    
    if success:
        quantity = inventory.inventory[barcode]['quantity']
        total_items, total_quantity = inventory.get_summary()
        
        print("=" * 60)
        print(f"✅ {message}: {barcode}")
        print(f"📦 Quantity: {quantity}")
        print(f"🕒 Time: {timestamp}")
        print(f"📊 Total Items: {total_items} | Total Quantity: {total_quantity}")
        print("=" * 60)
    else:
        print("=" * 60)
        print(f"❌ {message}: {barcode}")
        print(f"🕒 Time: {timestamp}")
        print("=" * 60)

def show_inventory(inventory):
    """Display current inventory"""
    if not inventory.inventory:
        print("📦 Inventory is empty")
        return
    
    print("\n📊 CURRENT INVENTORY")
    print("=" * 80)
    print(f"{'EAN Code':<15} {'Quantity':<10} {'First Scanned':<20} {'Last Scanned':<20}")
    print("-" * 80)
    
    for barcode, data in inventory.inventory.items():
        first = data['first_scanned'][:19].replace('T', ' ')
        last = data['last_scanned'][:19].replace('T', ' ')
        print(f"{barcode:<15} {data['quantity']:<10} {first:<20} {last:<20}")
    
    total_items, total_quantity = inventory.get_summary()
    print("-" * 80)
    print(f"Total Items: {total_items} | Total Quantity: {total_quantity}")
    print("=" * 80)

def main():
    inventory = BarcodeInventory()
    
    print("🔍 EAN Barcode Scanner with Quantity Tracking")
    print("=" * 60)
    
    # Show current inventory
    show_inventory(inventory)
    
    if not os.path.exists(DEVICE_PATH):
        print(f"❌ Device {DEVICE_PATH} not found. Connect your scanner and retry.")
        return

    if os.geteuid() != 0:
        print("⚠️ Warning: Not running as root. May need sudo for HID access.\n")

    try:
        read_barcode(DEVICE_PATH, inventory)
    except KeyboardInterrupt:
        print("\n\n🛑 Scanner stopped")
        show_inventory(inventory)

if __name__ == '__main__':
    main()
