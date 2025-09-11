#!/bin/bash

# Automatic USB Barcode Scanner Startup Script
echo "🚀 Starting Automatic USB Barcode Scanner"
echo "========================================="
echo ""

# Check if running as root for systemd installation
if [ "$EUID" -eq 0 ]; then 
   echo "📦 Installing as system service..."
   
   # Copy service file
   cp usb_scanner_auto.service /etc/systemd/system/
   
   # Reload systemd
   systemctl daemon-reload
   
   # Enable service to start on boot
   systemctl enable usb_scanner_auto.service
   
   # Start the service
   systemctl start usb_scanner_auto.service
   
   echo "✅ Service installed and started!"
   echo ""
   echo "Commands:"
   echo "  • Check status: systemctl status usb_scanner_auto"
   echo "  • View logs: journalctl -u usb_scanner_auto -f"
   echo "  • Stop service: systemctl stop usb_scanner_auto"
   echo "  • Disable auto-start: systemctl disable usb_scanner_auto"
   
else
   echo "🔌 Running in user mode..."
   echo ""
   
   # Activate virtual environment if exists
   if [ -d "barcode_env" ]; then
       echo "📦 Activating virtual environment..."
       source barcode_env/bin/activate
   elif [ -d "venv_ssl111" ]; then
       echo "📦 Activating virtual environment..."
       source venv_ssl111/bin/activate
   fi
   
   # Check for required packages
   echo "📋 Checking dependencies..."
   python3 -c "import evdev" 2>/dev/null
   if [ $? -ne 0 ]; then
       echo "📦 Installing evdev..."
       pip3 install evdev
   fi
   
   python3 -c "import azure.iot.device" 2>/dev/null
   if [ $? -ne 0 ]; then
       echo "📦 Installing Azure IoT SDK..."
       pip3 install azure-iot-device
   fi
   
   # Run the automatic scanner
   echo ""
   echo "🚀 Starting automatic USB scanner..."
   echo "This will:"
   echo "  ✅ Auto-detect USB scanner"
   echo "  ✅ Auto-register device on first scan"
   echo "  ✅ Auto-send all scans to IoT Hub"
   echo ""
   echo "Press Ctrl+C to stop"
   echo ""
   
   python3 src/usb_auto_scanner.py
fi