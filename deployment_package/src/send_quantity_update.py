#!/usr/bin/env python3
"""
Send quantity update for EAN barcode to API and IoT Hub
"""
import barcode_scanner_app as app

def main():
    device_id = "cfabc4830309"
    barcode = "5901234123457"  # EAN from image
    
    print(f"🚀 Sending quantity update...")
    print(f"📱 Device: {device_id}")
    print(f"📊 EAN Barcode: {barcode}")
    print(f"🔢 Quantity: 1")
    print("=" * 50)
    
    # Process barcode scan with registered device
    result = app.process_barcode_scan(barcode, device_id)
    print(result)
    
    print("=" * 50)
    print("✅ Quantity update completed!")

if __name__ == "__main__":
    main()