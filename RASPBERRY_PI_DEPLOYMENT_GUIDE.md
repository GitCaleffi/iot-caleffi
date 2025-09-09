# 🍓 Raspberry Pi Barcode Scanner Deployment Guide

## 📋 Overview
This guide shows how to deploy the barcode_scanner_app.py on a Raspberry Pi device for automatic barcode scanning with Azure IoT Hub integration.

## 🔧 Prerequisites
- Raspberry Pi (3B+, 4, or newer)
- MicroSD card (16GB+) with Raspberry Pi OS
- USB Barcode Scanner
- Internet connection (Wi-Fi or Ethernet)
- SSH access to Pi (optional but recommended)

## 📦 Step 1: Prepare Raspberry Pi

### 1.1 Update System
```bash
sudo apt update && sudo apt upgrade -y
```

### 1.2 Install Required Packages
```bash
# Install Python and dependencies
sudo apt install -y python3 python3-pip python3-venv git

# Install GPIO libraries
sudo apt install -y python3-lgpio python3-rpi.gpio

# Install system dependencies
sudo apt install -y build-essential libssl-dev libffi-dev
```

### 1.3 Enable GPIO (if not already enabled)
```bash
sudo raspi-config
# Navigate to: Interface Options → GPIO → Enable
```

## 📁 Step 2: Deploy Application Files

### 2.1 Create Application Directory
```bash
sudo mkdir -p /opt/barcode-scanner
sudo chown pi:pi /opt/barcode-scanner
cd /opt/barcode-scanner
```

### 2.2 Copy Application Files
Transfer these files to `/opt/barcode-scanner/`:
```
barcode_scanner_app.py
src/
├── api/
├── database/
├── iot/
├── utils/
config.json
requirements.txt
```

### 2.3 Set Up Python Environment
```bash
cd /opt/barcode-scanner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Step 3: Configure Application

### 3.1 Update config.json
```json
{
  "iot_hub": {
    "connection_string": "YOUR_IOT_HUB_CONNECTION_STRING"
  },
  "raspberry_pi": {
    "status": "auto",
    "force_detection": false
  },
  "performance": {
    "fast_mode": true,
    "parallel_processing": true,
    "auto_config": true
  }
}
```

### 3.2 Set Permissions
```bash
chmod +x barcode_scanner_app.py
chmod -R 755 src/
```

## 🚀 Step 4: Create Startup Scripts

### 4.1 Create Main Startup Script
```bash
cat > /opt/barcode-scanner/start_scanner.sh << 'EOF'
#!/bin/bash
# Raspberry Pi Barcode Scanner Startup Script

cd /opt/barcode-scanner
source venv/bin/activate

echo "🍓 Starting Raspberry Pi Barcode Scanner..."
echo "📱 Device will auto-register and start scanning"
echo "🔌 Connect your USB barcode scanner now"
echo ""

# Start the barcode scanner application
python3 barcode_scanner_app.py

EOF

chmod +x /opt/barcode-scanner/start_scanner.sh
```

### 4.2 Create Auto-Start Service
```bash
sudo cat > /etc/systemd/system/barcode-scanner.service << 'EOF'
[Unit]
Description=Raspberry Pi Barcode Scanner Service
After=network.target
Wants=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/barcode-scanner
ExecStart=/opt/barcode-scanner/start_scanner.sh
Restart=always
RestartSec=10
Environment=PYTHONPATH=/opt/barcode-scanner/src

[Install]
WantedBy=multi-user.target
EOF
```

### 4.3 Enable Auto-Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable barcode-scanner.service
sudo systemctl start barcode-scanner.service
```

## 🔌 Step 5: Connect Hardware

### 5.1 Connect USB Barcode Scanner
1. Plug USB barcode scanner into any USB port
2. Pi will automatically detect it as keyboard input
3. No additional drivers needed for most scanners

### 5.2 Connect LEDs (Optional)
Connect RGB LEDs to GPIO pins:
- Red LED: GPIO 17 (Pin 11)
- Yellow LED: GPIO 18 (Pin 12)  
- Green LED: GPIO 24 (Pin 18)
- Ground: Any GND pin

## ▶️ Step 6: Run the Application

### 6.1 Manual Start (for testing)
```bash
cd /opt/barcode-scanner
source venv/bin/activate
python3 barcode_scanner_app.py
```

### 6.2 Service Management
```bash
# Check service status
sudo systemctl status barcode-scanner

# View logs
sudo journalctl -u barcode-scanner -f

# Stop service
sudo systemctl stop barcode-scanner

# Start service
sudo systemctl start barcode-scanner

# Restart service
sudo systemctl restart barcode-scanner
```

## 📱 Step 7: Usage Instructions

### 7.1 Automatic Operation
1. **Power on Pi** - Service starts automatically
2. **Connect scanner** - USB barcode scanner detected automatically
3. **Start scanning** - Just scan barcodes, no setup needed
4. **LED feedback**:
   - 🟢 Green: Successful IoT Hub send
   - 🟡 Yellow: Saved offline (will retry automatically)
   - 🔴 Red: Error occurred

### 7.2 What Happens Automatically
- ✅ Device ID generated from Pi's MAC address
- ✅ Auto-registration with Azure IoT Hub
- ✅ Network connectivity detection
- ✅ Barcode validation and processing
- ✅ IoT Hub message sending
- ✅ Offline storage with auto-retry
- ✅ LED status indicators

## 🔍 Step 8: Monitoring and Troubleshooting

### 8.1 Check System Status
```bash
# View real-time logs
sudo journalctl -u barcode-scanner -f

# Check Pi connectivity
ping google.com

# Test USB scanner
lsusb | grep -i scanner
```

### 8.2 Common Issues

**Issue: Scanner not detected**
```bash
# Check USB devices
lsusb
# Scanner should appear as HID device
```

**Issue: No network connectivity**
```bash
# Check network interfaces
ip addr show
# Ensure Wi-Fi or Ethernet is connected
```

**Issue: IoT Hub connection failed**
```bash
# Check config.json has correct connection string
cat /opt/barcode-scanner/config.json
```

### 8.3 Debug Mode
```bash
# Run with debug logging
cd /opt/barcode-scanner
source venv/bin/activate
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from barcode_scanner_app import *
test_lan_detection_and_iot_hub_flow()
"
```

## 🎯 Step 9: Production Deployment

### 9.1 For Multiple Pi Devices
1. Create SD card image with configured system
2. Flash to multiple SD cards
3. Each Pi will auto-generate unique device ID
4. All devices auto-register with IoT Hub

### 9.2 Mass Deployment Script
```bash
#!/bin/bash
# Quick deployment for multiple Pis

# Update system
sudo apt update -y

# Install dependencies
sudo apt install -y python3-pip python3-lgpio git

# Clone and setup application
cd /opt
sudo git clone YOUR_REPO barcode-scanner
sudo chown -R pi:pi barcode-scanner
cd barcode-scanner
pip3 install -r requirements.txt

# Enable service
sudo systemctl enable barcode-scanner.service
sudo systemctl start barcode-scanner.service

echo "✅ Barcode scanner deployed and running!"
```

## 📊 Expected Behavior

### Startup Sequence
1. 🍓 Pi boots up
2. 🌐 Network connection established
3. 🆔 Device ID generated (e.g., `pi-c1323007`)
4. 📡 Auto-registration with IoT Hub
5. 🔌 USB scanner detection
6. ✅ Ready for barcode scanning

### Scanning Process
1. 📱 Scan barcode with USB scanner
2. 🔍 Automatic validation and processing
3. 📡 Send to Azure IoT Hub
4. 💾 Save locally (if offline)
5. 🔄 Auto-retry when connection restored
6. 💡 LED feedback indicates status

## 🎉 Success Indicators
- Green LED blinks after successful scans
- Service logs show "✅ Barcode sent to IoT Hub"
- Azure IoT Hub receives messages
- No manual intervention required
- Works immediately after Pi boot

This deployment creates a truly plug-and-play barcode scanning solution for your Raspberry Pi devices!
