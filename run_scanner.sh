#!/bin/bash
# Run the barcode scanner with proper virtual environment

# Activate virtual environment
source /home/Geektech/src/iot-caleffi/venv310/bin/activate

# Run the scanner
cd /var/www/html/abhimanyu/barcode_scanner_clean
python3 src/barcode_scanner_app.py --usb-auto
