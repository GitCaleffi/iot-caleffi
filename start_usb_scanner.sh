#!/bin/bash
# USB Barcode Scanner Startup Script with HID Support
# Handles permissions and provides fallback options

echo "🚀 Starting USB Barcode Scanner Service..."
echo "📱 Checking for USB barcode scanner devices..."

# Check if HID device exists
if [ -e "/dev/hidraw0" ]; then
    echo "✅ Found HID device: /dev/hidraw0"
    
    # Check if we have permission to read the device
    if [ -r "/dev/hidraw0" ]; then
        echo "✅ HID device permissions OK"
        echo "🔌 Using HID scanner mode"
        cd /var/www/html/abhimanyu/barcode_scanner_clean
        python3 start_hid_scanner.py
    else
        echo "⚠️ HID device requires elevated permissions"
        echo "🔐 Starting with sudo..."
        cd /var/www/html/abhimanyu/barcode_scanner_clean
        sudo python3 start_hid_scanner.py
    fi
else
    echo "❌ No HID device found at /dev/hidraw0"
    echo "🔄 Checking for other USB input devices..."
    
    # List available input devices
    if command -v evtest &> /dev/null; then
        echo "📋 Available input devices:"
        evtest 2>/dev/null | head -20
    fi
    
    echo "🔌 Using EVDEV scanner mode as fallback"
    cd /var/www/html/abhimanyu/barcode_scanner_clean/src
    
    # Modify the scanner to use EVDEV mode
    python3 -c "
import sys
sys.path.insert(0, '.')
from barcode_scanner_app import *
USE_HID_SCANNER = False
start_usb_scanner_service()
"
fi
