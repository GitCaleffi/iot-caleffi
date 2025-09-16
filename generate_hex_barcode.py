#!/usr/bin/env python3
"""
Generate numeric barcodes for hexadecimal values
Creates scannable numeric barcodes that your USB scanner can read
"""

from hex_barcode_converter import HexBarcodeConverter

def generate_numeric_for_hex(hex_barcode):
    """Generate numeric barcode for a hex value"""
    converter = HexBarcodeConverter()
    numeric = converter.get_scannable_barcode(hex_barcode)
    
    print(f"🔄 Hex Barcode Conversion")
    print(f"Original hex: {hex_barcode}")
    print(f"Numeric for USB scanner: {numeric}")
    print(f"✅ Create a barcode label with: {numeric}")
    print(f"📱 When scanned, it will be processed as: {hex_barcode}")
    
    return numeric

def main():
    """Generate numeric barcode for e6fcc128b131"""
    target_hex = "e6fcc128b131"
    
    print("📱 USB Scanner Barcode Generator")
    print("=" * 40)
    
    numeric_barcode = generate_numeric_for_hex(target_hex)
    
    print(f"\n💡 Instructions:")
    print(f"1. Create a barcode label with the number: {numeric_barcode}")
    print(f"2. Scan it with your USB scanner")
    print(f"3. The system will automatically recognize it as hex: {target_hex}")
    print(f"4. Both API and IoT Hub will receive the hex value: {target_hex}")

if __name__ == "__main__":
    main()
