#!/bin/bash
# setup_automation.sh - Black Box Barcode Scanner Service Setup
# Configures the barcode scanner to run automatically as a background service

# Define project variables
PROJECT_DIR="/var/www/html/abhimanyu/barcode_scanner_clean"
USER=$(whoami)
SERVICE_NAME="barcode-scanner"

echo "🔧 Setting up Black Box Barcode Scanner Service"
echo "=============================================="
echo "📁 Project Directory: $PROJECT_DIR"
echo "👤 User: $USER"
echo "🔧 Service Name: $SERVICE_NAME"
echo ""

# Make launcher script executable
echo "📝 Making launcher.sh executable..."
chmod 755 $PROJECT_DIR/launcher.sh

# Make the Python script executable
echo "📝 Making keyboard_scanner.py executable..."
chmod +x $PROJECT_DIR/keyboard_scanner.py

# Create logs directory if it doesn't exist
echo "📁 Creating logs directory..."
mkdir -p /home/pi/logs

# Create systemd service file for better service management
echo "📋 Creating systemd service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Barcode Scanner Black Box Service
After=network.target
Wants=network.target

[Service]
Type=forking
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/launcher.sh
ExecStop=/bin/kill -TERM \$MAINPID
PIDFile=/var/run/barcode_scanner.pid
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable the service
echo "🔄 Enabling systemd service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME.service

# Also add cron job as backup method
echo "📅 Adding cron job as backup..."
(crontab -l 2>/dev/null | grep -v "barcode_scanner"; echo "@reboot sleep 30 && $PROJECT_DIR/launcher.sh") | crontab -

echo ""
echo "✅ Black Box Service Setup Complete!"
echo "===================================="
echo ""
echo "📋 What was configured:"
echo "• Systemd service: $SERVICE_NAME.service"
echo "• Project directory: $PROJECT_DIR"
echo "• Running as user: $USER"
echo "• Automatic startup on boot"
echo "• Background daemon operation"
echo "• No user interaction required"
echo "• Automatic restart on failure"
echo ""
echo "🔄 Service Management Commands:"
echo "• Start service:    sudo systemctl start $SERVICE_NAME"
echo "• Stop service:     sudo systemctl stop $SERVICE_NAME"
echo "• Restart service:  sudo systemctl restart $SERVICE_NAME"
echo "• Check status:     sudo systemctl status $SERVICE_NAME"
echo "• View logs:        sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "📊 Monitoring:"
echo "• Service logs:     sudo journalctl -u $SERVICE_NAME"
echo "• Scanner logs:     tail -f $PROJECT_DIR/scanner.log"
echo "• Process status:   ps aux | grep keyboard_scanner"
echo ""
echo "🚀 To start the service now:"
echo "sudo systemctl start $SERVICE_NAME"
echo ""
echo "🔄 To activate on next boot:"
echo "sudo reboot"
echo ""
echo "💡 The service will:"
echo "• Start automatically on boot"
echo "• Run in background (no terminal needed)"
echo "• Restart automatically if it crashes"
echo "• Require no user interaction"
echo "• Only use LED indicators for status"
echo "• Log all activity to files"