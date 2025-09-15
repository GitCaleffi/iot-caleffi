#!/bin/bash

echo "🚀 USB Barcode Scanner Test Script"
echo "=================================="

# Check if Python3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python3"
    exit 1
fi

# Navigate to script directory
cd "$(dirname "$0")"

# Check if test script exists
if [ ! -f "test_usb_scanner_simple.py" ]; then
    echo "❌ Test script not found: test_usb_scanner_simple.py"
    exit 1
fi

echo "📱 Starting USB scanner test..."
echo "💡 Make sure your USB barcode scanner is connected"
echo "💡 If you get permission errors, try: sudo ./run_usb_test.sh"
echo ""

# Run the test script
python3 test_usb_scanner_simple.py

echo ""
echo "✅ Test script finished"
