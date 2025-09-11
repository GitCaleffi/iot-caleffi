#!/bin/bash

# USB Barcode Scanner App Launcher
echo "🔌 USB Barcode Scanner App"
echo "=========================="
echo ""
echo "This app will:"
echo "✅ Automatically detect USB scanner input"
echo "✅ Register your device with scanned barcodes"
echo "✅ Process barcode scans for registered devices"
echo ""

# Activate virtual environment if it exists
if [ -d "venv_ssl111" ]; then
    echo "📦 Activating virtual environment..."
    source venv_ssl111/bin/activate
fi

# Run the fixed barcode scanner app
echo "🚀 Starting USB Barcode Scanner App..."
echo "🌐 Web interface will be available at: http://0.0.0.0:7860"
echo ""
echo "Instructions:"
echo "1. Open http://raspberrypi.local:7860 in your browser"
echo "2. Scan a barcode with your USB scanner (like 098b581a7f38)"
echo "3. The barcode will appear in the text field automatically"
echo "4. Click 'Process Barcode' to register your device"
echo ""
echo "Press Ctrl+C to stop the app"
echo ""

cd src && python3 barcode_scanner_app_fixed.py