#!/bin/bash

# MQTT Pi Client Setup Script
# This script configures a Raspberry Pi for MQTT-based server discovery

set -e

echo "🍓 Setting up MQTT Pi Client for automatic server discovery..."

# Configuration
SERVER_HOST="iot.caleffionline.it"
SERVICE_NAME="mqtt-pi-client"
INSTALL_DIR="/home/pi/barcode_scanner_clean"

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "⚠️  Warning: This doesn't appear to be a Raspberry Pi"
    echo "   Continuing anyway..."
fi

# Install required Python packages
echo "📦 Installing Python MQTT client and dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install paho-mqtt netifaces

# Create installation directory if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    echo "📁 Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR/src/utils"
fi

# Copy MQTT client files
echo "📋 Installing MQTT Pi client..."
cp src/utils/mqtt_pi_client.py "$INSTALL_DIR/src/utils/"
chmod +x "$INSTALL_DIR/src/utils/mqtt_pi_client.py"

# Create systemd service
echo "🔧 Creating MQTT Pi client service..."
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null << EOF
[Unit]
Description=MQTT Pi Client - Device Announcement Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=$INSTALL_DIR/src/utils
ExecStart=/usr/bin/python3 $INSTALL_DIR/src/utils/mqtt_pi_client.py $SERVER_HOST
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=PYTHONPATH=$INSTALL_DIR/src

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
echo "🚀 Starting MQTT Pi client service..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME.service
sudo systemctl start $SERVICE_NAME.service

# Wait a moment for service to start
sleep 3

# Check service status
if sudo systemctl is-active --quiet $SERVICE_NAME; then
    echo "✅ MQTT Pi Client Service is running"
else
    echo "❌ Failed to start MQTT Pi Client Service"
    sudo systemctl status $SERVICE_NAME
    exit 1
fi

# Get device information
DEVICE_ID=$(python3 -c "
import sys
sys.path.append('$INSTALL_DIR/src/utils')
from mqtt_pi_client import MQTTPiClient
client = MQTTPiClient('$SERVER_HOST')
print(client.device_id)
")

PI_IP=$(hostname -I | awk '{print $1}')
PI_HOSTNAME=$(hostname)

echo ""
echo "🎉 MQTT Pi Client setup completed successfully!"
echo ""
echo "📊 Service Status:"
echo "   • Service: $(sudo systemctl is-active $SERVICE_NAME)"
echo "   • Device ID: $DEVICE_ID"
echo "   • Pi IP: $PI_IP"
echo "   • Hostname: $PI_HOSTNAME"
echo ""
echo "📡 Connection Details:"
echo "   • Server: $SERVER_HOST"
echo "   • MQTT Port: 1883"
echo "   • Heartbeat: Every 30 seconds"
echo ""
echo "🔍 Monitor the service with:"
echo "   sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "🔄 Service management commands:"
echo "   sudo systemctl start $SERVICE_NAME    # Start service"
echo "   sudo systemctl stop $SERVICE_NAME     # Stop service"
echo "   sudo systemctl restart $SERVICE_NAME  # Restart service"
echo "   sudo systemctl status $SERVICE_NAME   # Check status"
echo ""
echo "✅ Your Pi will now automatically announce itself to the server!"
echo "   The server will detect this Pi regardless of network changes."
