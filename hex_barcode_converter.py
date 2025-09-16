#!/usr/bin/env python3
"""
Hexadecimal Barcode Converter for USB Scanners
Converts hex barcodes to numeric equivalents that USB scanners can read
"""

import json
import os
from pathlib import Path

class HexBarcodeConverter:
    def __init__(self):
        self.mapping_file = Path(__file__).parent / "hex_to_numeric_mapping.json"
        self.load_mappings()
    
    def load_mappings(self):
        """Load existing hex to numeric mappings"""
        try:
            if self.mapping_file.exists():
                with open(self.mapping_file, 'r') as f:
                    self.mappings = json.load(f)
            else:
                self.mappings = {}
        except Exception as e:
            print(f"Error loading mappings: {e}")
            self.mappings = {}
    
    def save_mappings(self):
        """Save hex to numeric mappings to file"""
        try:
            with open(self.mapping_file, 'w') as f:
                json.dump(self.mappings, f, indent=2)
        except Exception as e:
            print(f"Error saving mappings: {e}")
    
    def hex_to_numeric(self, hex_barcode):
        """Convert hexadecimal barcode to numeric equivalent"""
        # Clean the hex string
        hex_clean = ''.join(c for c in hex_barcode.lower() if c in '0123456789abcdef')
        
        if not hex_clean:
            raise ValueError("Invalid hexadecimal barcode")
        
        # Convert to decimal
        decimal_value = int(hex_clean, 16)
        numeric_barcode = str(decimal_value)
        
        # Store mapping for reverse lookup
        self.mappings[numeric_barcode] = hex_clean
        self.mappings[hex_clean] = numeric_barcode
        self.save_mappings()
        
        return numeric_barcode
    
    def numeric_to_hex(self, numeric_barcode):
        """Convert numeric barcode back to hexadecimal"""
        # Check if we have a stored mapping
        if numeric_barcode in self.mappings:
            return self.mappings[numeric_barcode]
        
        # Convert decimal to hex
        try:
            decimal_value = int(numeric_barcode)
            hex_value = hex(decimal_value)[2:]  # Remove '0x' prefix
            return hex_value
        except ValueError:
            raise ValueError("Invalid numeric barcode")
    
    def get_scannable_barcode(self, hex_barcode):
        """Get the numeric barcode that can be scanned by USB scanner"""
        return self.hex_to_numeric(hex_barcode)
    
    def get_original_barcode(self, numeric_barcode):
        """Get the original hex barcode from scanned numeric barcode"""
        return self.numeric_to_hex(numeric_barcode)

def convert_hex_barcode(hex_barcode):
    """Standalone function to convert hex barcode"""
    converter = HexBarcodeConverter()
    return converter.hex_to_numeric(hex_barcode)

def main():
    """Test the converter with example barcodes"""
    converter = HexBarcodeConverter()
    
    # Test barcodes
    test_hex_barcodes = [
        "e6fcc128b131",
        "7079fa7ab32e", 
        "abc123def456",
        "deadbeef",
        "cafebabe"
    ]
    
    print("🔄 Hexadecimal to Numeric Barcode Converter")
    print("=" * 50)
    
    for hex_barcode in test_hex_barcodes:
        try:
            numeric_barcode = converter.hex_to_numeric(hex_barcode)
            print(f"Hex: {hex_barcode} → Numeric: {numeric_barcode}")
            
            # Verify reverse conversion
            converted_back = converter.numeric_to_hex(numeric_barcode)
            if converted_back == hex_barcode:
                print(f"  ✅ Reverse conversion verified")
            else:
                print(f"  ❌ Reverse conversion failed: {converted_back}")
        except Exception as e:
            print(f"  ❌ Error converting {hex_barcode}: {e}")
        print()
    
    print("📱 Usage Instructions:")
    print("1. Convert your hex barcode to numeric using this tool")
    print("2. Create a numeric barcode label/sticker")
    print("3. Scan the numeric barcode with your USB scanner")
    print("4. The system will automatically map it back to the original hex barcode")

if __name__ == "__main__":
    main()
