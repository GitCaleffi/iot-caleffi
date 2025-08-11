#!/bin/bash
"""
Install Plug-and-Play Barcode Scanner Service
Installs the automated service as a system service for true plug-and-play experience
"""

echo ""
echo "🔧 INSTALLING PLUG-AND-PLAY BARCODE SCANNER SERVICE"
echo "=================================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if running as root for service installation
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script needs sudo privileges to install the system service."
    echo "   Run: sudo bash install_plug_and_play.sh"
    echo ""
    echo "   Or you can use the manual mode:"
    echo "   bash start_plug_and_play.sh"
    exit 1
fi

echo "✅ Installing automated barcode scanner service..."

# Copy service file to systemd
cp "$SCRIPT_DIR/auto-barcode-scanner.service" /etc/systemd/system/
echo "📁 Service file copied to /etc/systemd/system/"

# Reload systemd
systemctl daemon-reload
echo "🔄 Systemd daemon reloaded"

# Enable service to start on boot
systemctl enable auto-barcode-scanner
echo "🚀 Service enabled to start on boot"

# Start the service
systemctl start auto-barcode-scanner
echo "▶️  Service started"

# Check service status
echo ""
echo "📊 Service Status:"
systemctl status auto-barcode-scanner --no-pager -l

echo ""
echo "🎉 INSTALLATION COMPLETE!"
echo "========================="
echo ""
echo "✅ The automated barcode scanner service is now installed and running!"
echo "✅ It will automatically start when the system boots"
echo "✅ Just plug in USB barcode scanners and start scanning!"
echo ""
echo "📋 Useful Commands:"
echo "   Check status:    sudo systemctl status auto-barcode-scanner"
echo "   View logs:       sudo journalctl -u auto-barcode-scanner -f"
echo "   Stop service:    sudo systemctl stop auto-barcode-scanner"
echo "   Start service:   sudo systemctl start auto-barcode-scanner"
echo "   Restart service: sudo systemctl restart auto-barcode-scanner"
echo ""
echo "🎯 TRUE PLUG-AND-PLAY MODE ACTIVATED!"
echo "   Users just need to plug in scanners and start scanning!"
echo ""
