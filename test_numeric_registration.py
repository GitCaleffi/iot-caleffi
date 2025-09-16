#!/usr/bin/env python3
"""
Test script to simulate numeric barcode registration
This demonstrates how to register a device using numeric barcodes only
"""

import sys
import os
import subprocess
import time

def test_numeric_registration():
    """Test device registration with numeric barcode"""
    print("🧪 Testing Numeric Barcode Device Registration")
    print("=" * 50)
    
    # Example numeric barcodes that your USB scanner can read
    test_barcodes = [
        "1234567890",      # 10-digit numeric
        "987654321",       # 9-digit numeric  
        "555666777",       # Another 9-digit
        "123456",          # 6-digit numeric
        "7079732"          # 7-digit (similar to your image but numeric only)
    ]
    
    print("📱 Available numeric barcodes for testing:")
    for i, barcode in enumerate(test_barcodes, 1):
        print(f"   {i}. {barcode}")
    
    print("\n🔧 To register your device:")
    print("1. Run: python3 /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src/auto_barcode_service.py")
    print("2. When prompted, scan one of these numeric barcodes with your USB scanner")
    print("3. The system will register your device with that barcode as the device ID")
    print("4. After registration, you can scan any barcodes for processing")
    
    print("\n💡 Your USB scanner should be able to read any of these numeric barcodes")
    print("   The scanned barcode will become your device ID (e.g., device-1234567890)")

if __name__ == "__main__":
    test_numeric_registration()
