#!/bin/bash
# Raspberry Pi Barcode Scanner - One-Click Deployment Script
# Run this script on your Raspberry Pi to automatically set up the barcode scanner

set -e  # Exit on any error

echo "🍓 Raspberry Pi Barcode Scanner - Auto Deployment"
echo "=================================================="

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null && ! grep -q "BCM" /proc/cpuinfo; then
    echo "⚠️ Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update system
echo "📦 Updating system packages..."
sudo apt update -y
sudo apt upgrade -y

# Install dependencies
echo "🔧 Installing dependencies..."
sudo apt install -y python3 python3-pip python3-venv python3-lgpio git build-essential

# Create application directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/barcode-scanner
sudo chown pi:pi /opt/barcode-scanner

# Copy files to deployment location
echo "📋 Copying application files..."
cp -r deployment_package/src /opt/barcode-scanner/
cp deployment_package/config.json /opt/barcode-scanner/
cp requirements.txt /opt/barcode-scanner/

# Create main application file
cp deployment_package/src/barcode_scanner_app.py /opt/barcode-scanner/

# Set up Python virtual environment
echo "🐍 Setting up Python environment..."
cd /opt/barcode-scanner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create startup script
echo "🚀 Creating startup script..."
cat > /opt/barcode-scanner/start_scanner.sh << 'EOF'
#!/bin/bash
# Raspberry Pi Barcode Scanner Startup

cd /opt/barcode-scanner
source venv/bin/activate

echo "🍓 Raspberry Pi Barcode Scanner Starting..."
echo "📱 Device will auto-register with IoT Hub"
echo "🔌 Connect USB barcode scanner and start scanning"
echo "💡 LED Status: 🟢=Success 🟡=Offline 🔴=Error"
echo "==============================================="

# Start the application
python3 barcode_scanner_app.py
EOF

chmod +x /opt/barcode-scanner/start_scanner.sh

# Create systemd service
echo "⚙️ Creating system service..."
sudo tee /etc/systemd/system/barcode-scanner.service > /dev/null << 'EOF'
[Unit]
Description=Raspberry Pi Barcode Scanner Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/barcode-scanner
ExecStart=/opt/barcode-scanner/start_scanner.sh
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/barcode-scanner/src
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
echo "🔄 Enabling auto-start service..."
sudo systemctl daemon-reload
sudo systemctl enable barcode-scanner.service

# Create manual start script
echo "📱 Creating manual start script..."
cat > /opt/barcode-scanner/run_manual.sh << 'EOF'
#!/bin/bash
# Manual start for testing

cd /opt/barcode-scanner
source venv/bin/activate

echo "🧪 Manual Test Mode"
echo "=================="
python3 -c "
from barcode_scanner_app import test_lan_detection_and_iot_hub_flow
print('🧪 Running system test...')
test_lan_detection_and_iot_hub_flow()
"
EOF

chmod +x /opt/barcode-scanner/run_manual.sh

# Create quick test script
cat > /opt/barcode-scanner/test_system.sh << 'EOF'
#!/bin/bash
# Quick system test

cd /opt/barcode-scanner
source venv/bin/activate

echo "🔍 System Test Results:"
echo "======================"

# Test Python imports
python3 -c "
try:
    from barcode_scanner_app import *
    print('✅ Application imports: OK')
except Exception as e:
    print(f'❌ Import error: {e}')

try:
    import lgpio
    print('✅ GPIO library: OK')
except:
    print('⚠️ GPIO library: Not available (normal on non-Pi systems)')

# Test USB devices
import subprocess
result = subprocess.run(['lsusb'], capture_output=True, text=True)
if 'HID' in result.stdout:
    print('✅ USB HID device detected (likely barcode scanner)')
else:
    print('⚠️ No USB HID device detected (connect barcode scanner)')
"

echo ""
echo "📊 Service Status:"
sudo systemctl status barcode-scanner --no-pager -l
EOF

chmod +x /opt/barcode-scanner/test_system.sh

# Set permissions
sudo chown -R pi:pi /opt/barcode-scanner
chmod -R 755 /opt/barcode-scanner

echo ""
echo "✅ Deployment Complete!"
echo "======================"
echo ""
echo "📋 Next Steps:"
echo "1. Connect USB barcode scanner"
echo "2. Start service: sudo systemctl start barcode-scanner"
echo "3. Check status: sudo systemctl status barcode-scanner"
echo "4. View logs: sudo journalctl -u barcode-scanner -f"
echo ""
echo "🚀 Quick Commands:"
echo "• Manual test: /opt/barcode-scanner/run_manual.sh"
echo "• System test: /opt/barcode-scanner/test_system.sh"
echo "• Start service: sudo systemctl start barcode-scanner"
echo "• Auto-start on boot: Already enabled!"
echo ""
echo "🎉 Your Raspberry Pi is ready for barcode scanning!"
