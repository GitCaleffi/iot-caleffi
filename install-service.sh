#!/bin/bash
# Install barcode scanner as system service

echo "🚀 Installing Barcode Scanner Service..."

# Copy service file
sudo cp barcode-scanner.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable barcode-scanner.service

# Start service now
sudo systemctl start barcode-scanner.service

# Check status
sudo systemctl status barcode-scanner.service

echo "✅ Service installed! Pi will auto-connect to server on boot."
echo "📱 Just plug in USB barcode scanner and scan barcodes!"

# Show logs
echo "📋 Service logs:"
sudo journalctl -u barcode-scanner.service -f --no-pager -n 10
