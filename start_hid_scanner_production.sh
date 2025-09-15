#!/bin/bash
# Production HID Barcode Scanner Startup Script
# Handles permissions automatically and provides clean output

echo "🚀 Starting Production HID Barcode Scanner..."
echo "📱 Checking USB barcode scanner connection..."

# Check if HID device exists
if [ -e "/dev/hidraw0" ]; then
    echo "✅ Found HID device: /dev/hidraw0"
    
    # Check if we have permission to read the device
    if [ -r "/dev/hidraw0" ]; then
        echo "✅ HID device permissions OK"
        echo "🔌 Starting HID scanner service..."
        cd /var/www/html/abhimanyu/barcode_scanner_clean
        python3 usb_hid_scanner.py
    else
        echo "🔐 HID device requires elevated permissions"
        echo "🔐 Starting with sudo (you may be prompted for password)..."
        cd /var/www/html/abhimanyu/barcode_scanner_clean
        sudo python3 usb_hid_scanner.py
    fi
else
    echo "❌ No HID device found at /dev/hidraw0"
    echo "🔍 Please check that your USB barcode scanner is connected"
    echo "💡 Try unplugging and reconnecting your scanner"
    exit 1
fi
