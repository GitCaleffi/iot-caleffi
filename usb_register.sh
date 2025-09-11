#!/bin/bash

# USB Scanner Auto-Register Script
# Run this to automatically capture USB scanner input for device registration

echo "🔌 USB Scanner Auto-Register"
echo "================================"
echo ""
echo "This script will capture input from your USB scanner"
echo "and automatically register your device."
echo ""
echo "Instructions:"
echo "1. Make sure your USB scanner is connected"
echo "2. Simply scan a barcode with your USB scanner"
echo "3. The device will be registered automatically"
echo ""
echo "Press Enter to start, or Ctrl+C to cancel..."
read

# Activate virtual environment if it exists
if [ -d "venv_ssl111" ]; then
    echo "📦 Activating virtual environment..."
    source venv_ssl111/bin/activate
fi

# Run the USB auto-register script
echo "🚀 Starting USB auto-register..."
echo ""
python3 src/usb_auto_register.py