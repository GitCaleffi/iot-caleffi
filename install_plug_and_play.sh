#!/bin/bash

# Raspberry Pi Plug-and-Play Installation Script
# Creates a true plug-and-play system for client deployment

set -e

echo "🚀 Installing Raspberry Pi Plug-and-Play System..."

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
APP_DIR="/opt/pi-plug-play"
echo "📁 Creating application directory: $APP_DIR"
mkdir -p $APP_DIR
cd $APP_DIR

# Copy the plug-and-play client
echo "📋 Installing Plug-and-Play Client..."
if [ -f "/var/www/html/abhimanyu/barcode_scanner_clean/pi_plug_and_play_client.py" ]; then
    cp /var/www/html/abhimanyu/barcode_scanner_clean/pi_plug_and_play_client.py $APP_DIR/
else
    echo "⚠️ Source file not found, downloading from current directory..."
    cp pi_plug_and_play_client.py $APP_DIR/ 2>/dev/null || echo "❌ Please ensure pi_plug_and_play_client.py is in current directory"
fi

chmod +x $APP_DIR/pi_plug_and_play_client.py

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install requests azure-iot-device

# Create systemd service file
echo "⚙️ Creating systemd service..."
cat > /etc/systemd/system/pi-plug-play.service << 'EOF'
[Unit]
Description=Raspberry Pi Plug-and-Play Client
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/pi-plug-play
Environment=PATH=/opt/pi-plug-play/venv/bin
ExecStart=/opt/pi-plug-play/venv/bin/python /opt/pi-plug-play/pi_plug_and_play_client.py
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
cat > $APP_DIR/start_plug_play.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Raspberry Pi Plug-and-Play Client..."
echo "📡 This will auto-discover the server and wait for barcode registration"
echo ""

cd /opt/pi-plug-play
source venv/bin/activate
python pi_plug_and_play_client.py
EOF

chmod +x $APP_DIR/start_plug_play.sh

# Create Wi-Fi setup helper
echo "📶 Creating Wi-Fi setup helper..."
cat > $APP_DIR/setup_wifi.sh << 'EOF'
#!/bin/bash
# Wi-Fi Setup Helper for Plug-and-Play

echo "📶 Wi-Fi Setup for Plug-and-Play System"
echo "======================================"

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
    echo "🎯 You can now start the plug-and-play client:"
    echo "   sudo systemctl start pi-plug-play"
    echo "   OR"
    echo "   sudo /opt/pi-plug-play/start_plug_play.sh"
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
cat > /etc/logrotate.d/pi-plug-play << 'EOF'
/var/log/pi_plug_play.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

# Create deployment package creator
echo "📦 Creating deployment package creator..."
cat > $APP_DIR/create_deployment_package.sh << 'EOF'
#!/bin/bash
# Create deployment package for client distribution

echo "📦 Creating Plug-and-Play Deployment Package..."

PACKAGE_DIR="/tmp/pi-plug-play-package"
rm -rf $PACKAGE_DIR
mkdir -p $PACKAGE_DIR

# Copy files
cp /opt/pi-plug-play/pi_plug_and_play_client.py $PACKAGE_DIR/
cp /opt/pi-plug-play/setup_wifi.sh $PACKAGE_DIR/
cp /opt/pi-plug-play/start_plug_play.sh $PACKAGE_DIR/

# Copy installation script
cp /var/www/html/abhimanyu/barcode_scanner_clean/install_plug_and_play.sh $PACKAGE_DIR/ 2>/dev/null || \
cp install_plug_and_play.sh $PACKAGE_DIR/

# Create README
cat > $PACKAGE_DIR/README.md << 'EOL'
# Raspberry Pi Plug-and-Play Package

## Quick Setup (3 Steps)

1. **Setup Wi-Fi** (if using Wi-Fi):
   ```bash
   sudo ./setup_wifi.sh
   ```

2. **Install System**:
   ```bash
   sudo ./install_plug_and_play.sh
   ```

3. **Connect Scanner & Scan**:
   - Connect USB barcode scanner
   - Scan any barcode to register device
   - Start scanning barcodes for quantity updates

## Manual Start (for testing):
```bash
sudo ./start_plug_play.sh
```

## Service Management:
```bash
sudo systemctl start pi-plug-play    # Start
sudo systemctl stop pi-plug-play     # Stop  
sudo systemctl status pi-plug-play   # Status
sudo journalctl -u pi-plug-play -f   # Logs
```

The system will automatically:
- Discover the server (iot.caleffionline.it or local network)
- Register device when barcode is scanned
- Send all barcode scans to API and IoT Hub
- Handle network reconnections
- Update automatically
EOL

# Create archive
cd /tmp
tar -czf pi-plug-play-package.tar.gz pi-plug-play-package/

echo "✅ Deployment package created: /tmp/pi-plug-play-package.tar.gz"
echo "📤 Copy this file to client's Raspberry Pi devices"
EOF

chmod +x $APP_DIR/create_deployment_package.sh

# Enable and start service
echo "🔄 Enabling service (will start on boot)..."
systemctl daemon-reload
systemctl enable pi-plug-play.service

# Don't start automatically - let user choose when to start
echo "⏸️ Service enabled but not started (manual start required)"

echo ""
echo "✅ Raspberry Pi Plug-and-Play System installed successfully!"
echo ""
echo "📋 Installation Summary:"
echo "  • Service: pi-plug-play.service"
echo "  • Location: /opt/pi-plug-play/"
echo "  • Logs: /var/log/pi_plug_play.log"
echo "  • Config: /etc/pi_plug_play.json"
echo ""
echo "🎯 Next Steps:"
echo ""
echo "1. **Setup Wi-Fi** (if needed):"
echo "   sudo /opt/pi-plug-play/setup_wifi.sh"
echo ""
echo "2. **Start Plug-and-Play System**:"
echo "   sudo systemctl start pi-plug-play"
echo "   OR for testing:"
echo "   sudo /opt/pi-plug-play/start_plug_play.sh"
echo ""
echo "3. **Connect USB Barcode Scanner**"
echo ""
echo "4. **Scan ANY barcode to register device**"
echo ""
echo "5. **Start scanning barcodes for quantity updates**"
echo ""
echo "🔧 Management Commands:"
echo "  • Status:    sudo systemctl status pi-plug-play"
echo "  • Logs:      sudo journalctl -u pi-plug-play -f"
echo "  • Stop:      sudo systemctl stop pi-plug-play"
echo "  • Restart:   sudo systemctl restart pi-plug-play"
echo ""
echo "📦 Create deployment package for clients:"
echo "   sudo /opt/pi-plug-play/create_deployment_package.sh"
echo ""
echo "🌐 The system will automatically discover these servers:"
echo "  • https://iot.caleffionline.it (client's production server)"
echo "  • Local network servers (10.0.0.4, 192.168.1.1, etc.)"
echo ""
echo "🎉 Ready for plug-and-play operation!"
