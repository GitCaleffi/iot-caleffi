#!/bin/bash
# Raspberry Pi HID Scanner Startup Script
# Handles virtual environment and sudo permissions properly

echo "🍓 Starting Raspberry Pi HID Barcode Scanner..."
echo "📱 Checking USB barcode scanner connection..."

# Set the correct paths
PI_PROJECT_DIR="/home/Geektech/src/iot-caleffi"
VENV_PYTHON="$PI_PROJECT_DIR/venv310/bin/python3"
SRC_DIR="$PI_PROJECT_DIR/src"

# Check if we're in the right directory
if [ ! -d "$PI_PROJECT_DIR" ]; then
    echo "❌ Project directory not found: $PI_PROJECT_DIR"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ Virtual environment not found: $VENV_PYTHON"
    echo "💡 Please activate your virtual environment first"
    exit 1
fi

# Check if HID device exists
if [ -e "/dev/hidraw0" ]; then
    echo "✅ Found HID device: /dev/hidraw0"
    
    # Check if we have permission to read the device
    if [ -r "/dev/hidraw0" ]; then
        echo "✅ HID device permissions OK"
        echo "🔌 Starting HID scanner with virtual environment..."
        cd "$SRC_DIR"
        "$VENV_PYTHON" barcode_scanner_app.py --usb-auto
    else
        echo "🔐 HID device requires elevated permissions"
        echo "🔐 Starting with sudo using virtual environment Python..."
        cd "$SRC_DIR"
        sudo "$VENV_PYTHON" barcode_scanner_app.py --usb-auto
    fi
else
    echo "❌ No HID device found at /dev/hidraw0"
    echo "🔍 Please check that your USB barcode scanner is connected"
    echo "💡 Try unplugging and reconnecting your scanner"
    
    # Try to list available hidraw devices
    echo "🔍 Available HID devices:"
    ls -la /dev/hidraw* 2>/dev/null || echo "No HID devices found"
    exit 1
fi
