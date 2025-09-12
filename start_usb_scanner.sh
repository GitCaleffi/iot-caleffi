#!/bin/bash
# Start USB Scanner Service on Raspberry Pi
# This script runs the automatic USB barcode scanner

echo "🚀 Starting USB Barcode Scanner Service on Raspberry Pi"
echo "============================================================"

# Check if running on Raspberry Pi
if [[ $(uname -m) == arm* ]] || [[ -f /proc/device-tree/model ]]; then
    echo "✅ Raspberry Pi detected"
else
    echo "⚠️  Not running on Raspberry Pi - continuing anyway"
fi

# Check for required permissions
if [[ $EUID -ne 0 ]]; then
    echo "⚠️  Running without root privileges"
    echo "   If USB scanner detection fails, try: sudo ./start_usb_scanner.sh"
fi

# Navigate to project directory
cd "$(dirname "$0")"

# Install dependencies if needed
echo "📦 Checking dependencies..."
python3 -c "import evdev" 2>/dev/null || {
    echo "Installing evdev..."
    pip3 install evdev
}

# Start the USB scanner service
echo "🔌 Starting USB Scanner Service..."
echo "   This will:"
echo "   • Auto-detect USB barcode scanners"
echo "   • Register device on first scan"
echo "   • Send all barcodes to IoT Hub automatically"
echo "   • Run continuously until stopped (Ctrl+C)"
echo ""

python3 usb_auto_scanner_service.py
