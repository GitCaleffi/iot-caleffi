#!/bin/bash
"""
Install Automatic Pi Heartbeat Service
Sets up systemd service for automatic Pi IoT Hub connection maintenance
"""

echo "🚀 Installing Automatic Pi Heartbeat Service"
echo "============================================"

# Check if running as root for systemd installation
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo privileges to install systemd service"
    echo "   Run: sudo ./install_auto_heartbeat.sh"
    exit 1
fi

# Set working directory
WORK_DIR="/var/www/html/abhimanyu/barcode_scanner_clean"
SERVICE_FILE="auto-pi-heartbeat.service"
PYTHON_SCRIPT="auto_pi_heartbeat.py"

echo "📁 Working directory: $WORK_DIR"

# Check if files exist
if [ ! -f "$WORK_DIR/$PYTHON_SCRIPT" ]; then
    echo "❌ Python script not found: $WORK_DIR/$PYTHON_SCRIPT"
    exit 1
fi

if [ ! -f "$WORK_DIR/$SERVICE_FILE" ]; then
    echo "❌ Service file not found: $WORK_DIR/$SERVICE_FILE"
    exit 1
fi

# Make Python script executable
chmod +x "$WORK_DIR/$PYTHON_SCRIPT"
echo "✅ Made Python script executable"

# Copy service file to systemd
cp "$WORK_DIR/$SERVICE_FILE" /etc/systemd/system/
echo "✅ Copied service file to /etc/systemd/system/"

# Reload systemd daemon
systemctl daemon-reload
echo "✅ Reloaded systemd daemon"

# Enable service for auto-start
systemctl enable auto-pi-heartbeat
echo "✅ Enabled auto-pi-heartbeat service for auto-start"

# Start the service
systemctl start auto-pi-heartbeat
echo "✅ Started auto-pi-heartbeat service"

# Check service status
echo ""
echo "📊 Service Status:"
systemctl status auto-pi-heartbeat --no-pager -l

echo ""
echo "🎉 Installation completed!"
echo ""
echo "📋 Useful commands:"
echo "   Check status:    sudo systemctl status auto-pi-heartbeat"
echo "   View logs:       sudo journalctl -u auto-pi-heartbeat -f"
echo "   Stop service:    sudo systemctl stop auto-pi-heartbeat"
echo "   Start service:   sudo systemctl start auto-pi-heartbeat"
echo "   Restart service: sudo systemctl restart auto-pi-heartbeat"
echo ""
echo "🔄 The service will automatically:"
echo "   • Start on system boot"
echo "   • Maintain IoT Hub connection"
echo "   • Send heartbeat every 30 seconds"
echo "   • Auto-reconnect if connection fails"
echo "   • Use dynamic device registration"
