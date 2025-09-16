#!/usr/bin/env python3
"""
Convert hexadecimal device ID to numeric barcode that USB scanners can read
"""

def hex_to_numeric(hex_string):
    """Convert hexadecimal string to numeric equivalent"""
    # Remove any non-hex characters
    hex_clean = ''.join(c for c in hex_string.lower() if c in '0123456789abcdef')
    
    # Convert hex to decimal
    decimal_value = int(hex_clean, 16)
    
    return str(decimal_value)

def numeric_to_hex(numeric_string):
    """Convert numeric string back to hexadecimal"""
    decimal_value = int(numeric_string)
    hex_value = hex(decimal_value)[2:]  # Remove '0x' prefix
    return hex_value

def main():
    """Convert the device ID from the image"""
    original_hex = "7079fa7ab32e"
    
    print("🔄 Hexadecimal to Numeric Converter")
    print("=" * 40)
    print(f"Original hex device ID: {original_hex}")
    
    # Convert to numeric
    numeric_equivalent = hex_to_numeric(original_hex)
    print(f"Numeric equivalent:     {numeric_equivalent}")
    
    # Verify conversion works both ways
    converted_back = numeric_to_hex(numeric_equivalent)
    print(f"Converted back to hex:  {converted_back}")
    
    print("\n📱 Use this numeric barcode with your USB scanner:")
    print(f"   {numeric_equivalent}")
    
    print(f"\n✅ This will register device as: device-{numeric_equivalent}")
    print("   Which represents the same device ID as the original hex value")
    
    # Also provide a shorter version if the number is too long
    if len(numeric_equivalent) > 12:
        # Use last 10 digits for a shorter barcode
        short_numeric = numeric_equivalent[-10:]
        print(f"\n💡 Alternative shorter barcode: {short_numeric}")
        print(f"   (Last 10 digits - easier to scan)")

if __name__ == "__main__":
    main()
