#!/bin/bash
# Auto Barcode Service Installer
# Installs the service as a systemd service for true plug-and-play

set -e

echo "🚀 Installing Auto Barcode Service..."

# Get the current directory
INSTALL_DIR=$(pwd)
SERVICE_NAME="auto-barcode-scanner"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Create systemd service file
echo "📝 Creating systemd service..."
sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=Auto Barcode Scanner Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR/src
ExecStart=/usr/bin/python3 $INSTALL_DIR/start_auto_scanner.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
sudo chmod 644 "$SERVICE_FILE"

# Make scripts executable
chmod +x start_auto_scanner.py
chmod +x src/auto_barcode_service.py

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable service
echo "✅ Enabling service..."
sudo systemctl enable "$SERVICE_NAME"

# Start service
echo "🚀 Starting service..."
sudo systemctl start "$SERVICE_NAME"

# Check status
echo "📊 Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l

echo ""
echo "✅ AUTO BARCODE SERVICE INSTALLED!"
echo "=" * 40
echo "🎯 Service: $SERVICE_NAME"
echo "📁 Location: $INSTALL_DIR"
echo "🔄 Auto-starts on boot"
echo "📱 Ready for plug-and-play scanning"
echo ""
echo "📋 Useful commands:"
echo "   sudo systemctl status $SERVICE_NAME    # Check status"
echo "   sudo systemctl stop $SERVICE_NAME     # Stop service"
echo "   sudo systemctl start $SERVICE_NAME    # Start service"
echo "   sudo journalctl -u $SERVICE_NAME -f   # View logs"
echo ""
echo "🎉 INSTALLATION COMPLETE!"
