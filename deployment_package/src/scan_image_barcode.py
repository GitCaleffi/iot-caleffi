#!/usr/bin/env python3
"""
Scan barcode from image file and send to barcode scanner app
"""
import os
import re
import barcode_scanner_app as app

def scan_image_barcode(image_path, device_id):
    """Extract barcode from image and process it"""
    print(f"📷 Scanning barcode from image: {image_path}")
    
    # Extract EAN from filename
    filename = os.path.basename(image_path)
    ean_match = re.search(r'EAN-13-(\d{13})', filename)
    
    if ean_match:
        barcode = ean_match.group(1)
        print(f"✅ Found EAN barcode: {barcode}")
        
        # Process barcode with registered device
        result = app.process_barcode_scan(barcode, device_id)
        return result
    else:
        return "❌ No EAN barcode found in image filename"

if __name__ == "__main__":
    # Scan EAN barcode from image
    image_path = "EAN-13-5901234123457.svg.png"
    device_id = "cfabc4830309"
    
    print("🚀 Image Barcode Scanner")
    print("=" * 50)
    
    result = scan_image_barcode(image_path, device_id)
    print(result)