#!/bin/bash
"""
USB HID Scanner Startup Script
Accelerated barcode scanning using direct HID interface
"""

echo "🎯 Starting USB HID Barcode Scanner..."
echo "📱 Connect your USB barcode scanner and start scanning!"
echo ""
echo "🔧 Features:"
echo "   ✅ Direct HID interface for maximum speed"
echo "   ✅ Automatic device registration"
echo "   ✅ Real-time barcode processing"
echo "   ✅ LED feedback (on Raspberry Pi)"
echo "   ✅ IoT Hub + API integration"
echo ""
echo "💡 Press Ctrl+C to stop the scanner"
echo "=" * 50

# Check if running as root for HID access
if [ "$EUID" -ne 0 ]; then
    echo "⚠️ Warning: Not running as root. You may need sudo for HID device access."
    echo "💡 If you get permission errors, run: sudo ./start_usb_hid_scanner.sh"
    echo ""
fi

# Change to script directory
cd "$(dirname "$0")"

# Start the USB HID scanner service
python3 src/barcode_scanner_app.py --usb-hid
