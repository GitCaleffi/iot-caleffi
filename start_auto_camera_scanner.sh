#!/bin/bash
# Fully Automatic Camera Barcode Scanner Startup Script
# Zero configuration required - just run and scan!

echo "🤖 FULLY AUTOMATIC CAMERA BARCODE SCANNER"
echo "=========================================="
echo "✅ Zero configuration required"
echo "✅ Automatic device registration"
echo "✅ Continuous barcode scanning"
echo "✅ IoT Hub integration"
echo "✅ Local database storage"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

# Install required packages if not available
echo "🔧 Checking dependencies..."
python3 -c "import cv2" 2>/dev/null || {
    echo "📦 Installing OpenCV..."
    pip3 install opencv-python
}

python3 -c "import pyzbar" 2>/dev/null || {
    echo "📦 Installing pyzbar..."
    pip3 install pyzbar
}

# Check camera availability
echo "📷 Checking camera availability..."
if ! ls /dev/video* 1> /dev/null 2>&1; then
    echo "⚠️  No camera devices found. Please connect a USB camera or enable Pi camera."
    echo "   For Pi camera, run: sudo raspi-config -> Interface Options -> Camera -> Enable"
    read -p "Press Enter to continue anyway or Ctrl+C to exit..."
fi

echo "🚀 Starting automatic camera barcode scanner..."
echo "📷 Point camera at barcodes - they will be processed automatically"
echo "🛑 Press Ctrl+C to stop"
echo ""

# Run the scanner
cd src
python3 automatic_camera_scanner.py

echo ""
echo "✅ Scanner stopped. Thank you for using the automatic barcode scanner!"
