#!/usr/bin/env python3
"""
HID Barcode Scanner Startup Script
Uses the integrated HID scanner functionality from barcode_scanner_app.py
"""

import sys
import os

# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from barcode_scanner_app import start_usb_scanner_service

def main():
    print("🚀 Starting HID Barcode Scanner Service...")
    print("📱 Connect your USB barcode scanner and start scanning!")
    print("🔍 The system will automatically detect and process barcodes")
    print("=" * 60)
    
    try:
        start_usb_scanner_service()
    except KeyboardInterrupt:
        print("\n🛑 Scanner service stopped by user")
    except Exception as e:
        print(f"❌ Error starting scanner service: {e}")

if __name__ == "__main__":
    main()
