#!/bin/bash
# Enhanced POS Forwarding System Startup Script
# Compatible with all Raspberry Pi models (Pi 1 through Pi 5)

set -e

echo "🚀 Starting Enhanced POS Forwarding System"
echo "=========================================="

# Check if running on Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
    echo "🍓 Detected: $PI_MODEL"
else
    echo "⚠️  Not running on Raspberry Pi - some features may be limited"
fi

# Check if setup has been run
if [ ! -f "/tmp/pos_setup_complete" ]; then
    echo "🔧 Running initial setup..."
    
    # Check if we have root privileges for setup
    if [ "$EUID" -eq 0 ]; then
        ./setup_usb_hid.sh
        touch /tmp/pos_setup_complete
    else
        echo "⚠️  Initial setup requires root privileges"
        echo "💡 Please run: sudo ./setup_usb_hid.sh"
        echo "💡 Then run this script again"
        exit 1
    fi
fi

# Change to the correct directory
cd /var/www/html/abhimanyu/barcode_scanner_clean

# Test the POS forwarding system
echo ""
echo "🧪 Testing POS forwarding system..."
python3 test_pos_forwarding_enhanced.py

echo ""
echo "🎯 Starting barcode scanner with enhanced POS forwarding..."
echo "📱 Barcodes like '8053734093444' will be automatically forwarded to your POS system"
echo "🔌 Multiple forwarding methods available: USB HID, Network, Serial, Clipboard"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the keyboard scanner
python3 keyboard_scanner.py
