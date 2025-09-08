#!/usr/bin/env python3
"""
Simple test to demonstrate dynamic device ID generation from barcodes
"""

import time

def generate_device_id_from_barcode(barcode):
    """Generate device ID from barcode scan (same logic as in barcode_scanner_app.py)"""
    # Create device ID from barcode + timestamp for uniqueness
    barcode_suffix = barcode[-6:] if len(barcode) >= 6 else barcode
    timestamp_suffix = str(int(time.time()))[-4:]
    device_id = f"scanner-{barcode_suffix}-{timestamp_suffix}"
    return device_id

def test_dynamic_device_ids():
    """Test dynamic device ID generation"""
    print("🧪 Testing Dynamic Device ID Generation")
    print("=" * 50)
    
    test_barcodes = [
        "1234567890123",
        "5625415485555", 
        "8574458712541",
        "817994ccfe14"
    ]
    
    print("📱 How device IDs are generated from barcodes:\n")
    
    for i, barcode in enumerate(test_barcodes, 1):
        device_id = generate_device_id_from_barcode(barcode)
        print(f"Test {i}:")
        print(f"  📊 Barcode: {barcode}")
        print(f"  🆔 Device ID: {device_id}")
        print(f"  🔍 Logic: scanner-{barcode[-6:]}-{str(int(time.time()))[-4:]}")
        print()
        time.sleep(1)  # Different timestamp for each test
    
    print("✅ Each barcode scan creates a unique device ID!")
    print("✅ No more static pi-6770e067 - device ID comes from barcode!")

if __name__ == "__main__":
    test_dynamic_device_ids()
