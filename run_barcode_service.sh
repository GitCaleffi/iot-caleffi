#!/bin/bash

echo "🚀 Starting Barcode Scanner Service (No Terminal Required)"
echo "📱 This service monitors USB barcode scanners automatically"
echo "🔍 Scans will be processed and sent to IoT Hub automatically"
echo "================================================"

# Run the keyboard scanner in service mode (no terminal)
nohup python3 keyboard_scanner.py > barcode_service.log 2>&1 &

echo "✅ Service started in background"
echo "📄 Check barcode_service.log for output"
echo "🛑 To stop: pkill -f keyboard_scanner.py"
