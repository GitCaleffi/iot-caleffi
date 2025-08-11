#!/bin/bash
"""
Plug-and-Play Barcode Scanner Startup Script
Zero-configuration barcode scanning

Just run this script and start scanning barcodes!
No setup, no URLs, no manual registration required.
"""

echo ""
echo "🚀 PLUG-AND-PLAY BARCODE SCANNER"
echo "=================================="
echo ""
echo "✅ Zero configuration required!"
echo "✅ Auto-registers your device!"
echo "✅ Auto-sends to IoT Hub and API!"
echo ""
echo "Just plug in your USB barcode scanner and start scanning!"
echo ""
echo "=================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run the setup script first:"
    echo "   bash setup_new_device.sh"
    exit 1
fi

# Activate virtual environment
source venv/bin/activate

# Check if config exists
if [ ! -f "config.json" ]; then
    echo "❌ Configuration file not found!"
    echo "Please run the setup script first:"
    echo "   bash setup_new_device.sh"
    exit 1
fi

# Make sure the auto service script is executable
chmod +x auto_barcode_service.py

echo "🔧 Starting Automated Barcode Scanner Service..."
echo ""
echo "INSTRUCTIONS:"
echo "1. Connect your USB barcode scanner"
echo "2. Start scanning barcodes"
echo "3. Watch the logs for success messages"
echo "4. Press Ctrl+C to stop"
echo ""
echo "🎯 Your device will be automatically registered!"
echo "📡 Barcodes will be automatically sent to IoT Hub and API!"
echo ""

# Start the automated service
python3 auto_barcode_service.py
