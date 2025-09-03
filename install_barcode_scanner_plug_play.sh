#!/bin/bash

# Raspberry Pi Barcode Scanner Plug-and-Play Installation Script
# Uses existing barcode_scanner_app.py with plug-and-play enhancements

set -e

echo "🚀 Installing Raspberry Pi Barcode Scanner (Plug-and-Play)..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt-get update -y
apt-get upgrade -y

# Install required packages
echo "🔧 Installing required packages..."
apt-get install -y python3 python3-pip python3-venv git curl wget wireless-tools

# Create application directory
APP_DIR="/opt/barcode-scanner"
echo "📁 Creating application directory: $APP_DIR"
mkdir -p $APP_DIR
cd $APP_DIR

# Copy the barcode scanner app and dependencies
echo "📋 Installing Barcode Scanner App..."
cp -r /var/www/html/abhimanyu/barcode_scanner_clean/src $APP_DIR/
cp /var/www/html/abhimanyu/barcode_scanner_clean/requirements.txt $APP_DIR/

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service file
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/barcode-scanner-plug-play.service << 'EOF'
[Unit]
Description=Raspberry Pi Barcode Scanner Plug-and-Play
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/barcode-scanner
Environment=PATH=/opt/barcode-scanner/venv/bin
Environment=PYTHONPATH=/opt/barcode-scanner
ExecStart=/opt/barcode-scanner/venv/bin/python /opt/barcode-scanner/src/barcode_scanner_app.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

# Wait for network to be fully ready
ExecStartPre=/bin/sleep 30

[Install]
WantedBy=multi-user.target
EOF

# Create startup script for manual testing
echo "🔧 Creating startup script..."
cat > $APP_DIR/start_barcode_scanner.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Raspberry Pi Barcode Scanner (Plug-and-Play)..."
echo "📡 This will auto-discover the server and wait for barcode registration"
echo ""

cd /opt/barcode-scanner
source venv/bin/activate
export PYTHONPATH=/opt/barcode-scanner
python src/barcode_scanner_app.py
EOF

chmod +x $APP_DIR/start_barcode_scanner.sh

# Create Wi-Fi setup helper
echo "📶 Creating Wi-Fi setup helper..."
cat > $APP_DIR/setup_wifi.sh << 'EOF'
#!/bin/bash
# Wi-Fi Setup Helper for Plug-and-Play

echo "📶 Wi-Fi Setup for Barcode Scanner"
echo "=================================="

if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use sudo)"
    exit 1
fi

echo "Available Wi-Fi networks:"
iwlist wlan0 scan | grep ESSID | head -10

echo ""
read -p "Enter Wi-Fi SSID: " WIFI_SSID
read -s -p "Enter Wi-Fi Password: " WIFI_PASSWORD
echo ""

# Create wpa_supplicant configuration
cat > /etc/wpa_supplicant/wpa_supplicant.conf << EOL
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PASSWORD"
}
EOL

echo "✅ Wi-Fi configuration saved"
echo "🔄 Restarting networking..."

# Restart networking
systemctl restart dhcpcd
systemctl restart wpa_supplicant

sleep 5

# Check connection
if iwgetid -r > /dev/null 2>&1; then
    echo "✅ Wi-Fi connected successfully"
    echo "📡 SSID: $(iwgetid -r)"
    echo "🌐 IP: $(hostname -I | awk '{print $1}')"
    echo ""
    echo "🎯 You can now start the barcode scanner:"
    echo "   sudo systemctl start barcode-scanner-plug-play"
    echo "   OR"
    echo "   sudo /opt/barcode-scanner/start_barcode_scanner.sh"
else
    echo "❌ Wi-Fi connection failed"
    echo "💡 Please check SSID and password"
fi
EOF

chmod +x $APP_DIR/setup_wifi.sh

# Set up USB barcode scanner permissions
echo "🔌 Setting up USB scanner permissions..."
cat > /etc/udev/rules.d/99-barcode-scanner.rules << 'EOF'
# USB Barcode Scanner Rules for Plug-and-Play
SUBSYSTEM=="input", GROUP="input", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", GROUP="plugdev", MODE="0664"

# Common barcode scanner vendor IDs
SUBSYSTEM=="usb", ATTRS{idVendor}=="05e0", GROUP="plugdev", MODE="0664"  # Symbol/Zebra
SUBSYSTEM=="usb", ATTRS{idVendor}=="0536", GROUP="plugdev", MODE="0664"  # Hand Held Products
SUBSYSTEM=="usb", ATTRS{idVendor}=="1a86", GROUP="plugdev", MODE="0664"  # QinHeng Electronics
SUBSYSTEM=="usb", ATTRS{idVendor}=="04b4", GROUP="plugdev", MODE="0664"  # Cypress Semiconductor
EOF

# Add user to required groups
usermod -a -G input,plugdev root 2>/dev/null || true

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Create log rotation config
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/barcode-scanner-plug-play << 'EOF'
/var/log/barcode_scanner.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

# Enable service (don't start automatically)
echo "🔄 Enabling service (will start on boot)..."
systemctl daemon-reload
systemctl enable barcode-scanner-plug-play.service

echo ""
echo "✅ Raspberry Pi Barcode Scanner (Plug-and-Play) installed successfully!"
echo ""
echo "📋 Installation Summary:"
echo "  • Service: barcode-scanner-plug-play.service"
echo "  • Location: /opt/barcode-scanner/"
echo "  • Config: /etc/pi_barcode_config.json (created after registration)"
echo ""
echo "🎯 Next Steps:"
echo ""
echo "1. **Setup Wi-Fi** (if needed):"
echo "   sudo /opt/barcode-scanner/setup_wifi.sh"
echo ""
echo "2. **Start Barcode Scanner**:"
echo "   sudo systemctl start barcode-scanner-plug-play"
echo "   OR for testing:"
echo "   sudo /opt/barcode-scanner/start_barcode_scanner.sh"
echo ""
echo "3. **Connect USB Barcode Scanner**"
echo ""
echo "4. **Scan ANY barcode to register device**"
echo ""
echo "5. **After registration, restart service to begin normal operation**"
echo "   sudo systemctl restart barcode-scanner-plug-play"
echo ""
echo "🔧 Management Commands:"
echo "  • Status:    sudo systemctl status barcode-scanner-plug-play"
echo "  • Logs:      sudo journalctl -u barcode-scanner-plug-play -f"
echo "  • Stop:      sudo systemctl stop barcode-scanner-plug-play"
echo "  • Restart:   sudo systemctl restart barcode-scanner-plug-play"
echo ""
echo "🌐 The system will automatically discover these servers:"
echo "  • https://iot.caleffionline.it (client's production server)"
echo "  • Local network servers (10.0.0.4, 192.168.1.1, etc.)"
echo ""
echo "🎉 Ready for plug-and-play operation!"
