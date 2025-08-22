# 🚀 Live Server Plug-and-Play Deployment Guide

## 📋 Overview
Complete deployment guide for barcode scanner system with:
- ✅ **Automatic Raspberry Pi IP detection** (no static IPs)
- ✅ **Real GPIO LED control** (hardware LEDs)
- ✅ **Zero-configuration setup** for live servers

## 🔧 Prerequisites

### Server Requirements
- Ubuntu/Debian Linux server
- Python 3.8+
- Network access to Raspberry Pi devices
- Root/sudo access for GPIO control

### Hardware Requirements
- Raspberry Pi with GPIO LEDs connected
- USB barcode scanner
- Network connectivity between server and Raspberry Pi

## 🎯 LED Wiring Configuration

Connect LEDs to your Raspberry Pi GPIO pins as follows:

```
LED Color    | GPIO Pin | Physical Pin | Purpose
-------------|----------|--------------|------------------
Red LED      | GPIO 18  | Pin 12       | Error/Failure
Green LED    | GPIO 23  | Pin 16       | Success/OK  
Yellow LED   | GPIO 24  | Pin 18       | Warning/Offline
Orange LED   | GPIO 25  | Pin 22       | Partial Success
Ground       | GND      | Pin 6,9,14   | Common Ground
```

### LED Circuit Diagram
```
GPIO Pin → 220Ω Resistor → LED Anode → LED Cathode → Ground
```

## 📦 Installation Steps

### 1. Install System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and GPIO support
sudo apt install python3-pip python3-venv python3-rpi.gpio git -y

# Install network discovery tools
sudo apt install nmap arp-scan net-tools iputils-ping -y

# Install web server dependencies
sudo apt install nginx -y
```

### 2. Install Python Dependencies
```bash
# Navigate to project directory
cd /var/www/html/abhimanyu/barcode_scanner_clean

# Install Python packages
pip3 install -r requirements.txt

# Install additional packages for GPIO and networking
pip3 install RPi.GPIO python-nmap netifaces
```

### 3. Configure GPIO Permissions
```bash
# Add user to gpio group for LED control
sudo usermod -a -G gpio $USER

# Set GPIO permissions
sudo chmod 666 /dev/gpiomem

# Create udev rule for GPIO access
echo 'KERNEL=="gpiomem", GROUP="gpio", MODE="0660"' | sudo tee /etc/udev/rules.d/99-gpio.rules

# Reload udev rules
sudo udevadm control --reload-rules
```

### 4. Test Automatic Pi Detection
```bash
# Test the automatic detection system
python3 -c "
from src.barcode_scanner_app import get_primary_raspberry_pi_ip
ip = get_primary_raspberry_pi_ip()
print(f'Auto-detected Pi IP: {ip}')
"
```

## 🔄 Automatic Features

### 1. Raspberry Pi Auto-Detection
The system automatically:
- Scans local network for Raspberry Pi devices
- Identifies devices by MAC address prefixes
- Tests SSH and web service connectivity
- Selects the best available Pi device
- Saves detected IP to config for faster access

### 2. Real GPIO LED Control
LEDs provide real-time status feedback:
- **Red LED (Rapid Blink)**: Errors, failures, Pi offline
- **Green LED (Steady 2s)**: Success, barcode processed
- **Yellow LED (Slow Blink)**: Warnings, offline mode
- **Orange LED (Standard Blink)**: Partial success

## 🚀 Quick Start

1. **Connect LEDs** to GPIO pins as specified above
2. **Run the application**: `python3 web_app.py`
3. **Access web interface**: `http://your-server-ip/`
4. **System automatically detects** your Raspberry Pi
5. **LEDs blink** to show real-time status

## 🔧 Troubleshooting

### Pi Detection Issues
```bash
# Check network connectivity
ping 192.168.1.1

# Manual network scan
nmap -sn 192.168.1.0/24

# Check ARP table
arp -a
```

### GPIO LED Issues
```bash
# Check GPIO permissions
ls -l /dev/gpiomem

# Test GPIO manually
python3 -c "import RPi.GPIO as GPIO; print('GPIO OK')"

# Check user groups
groups $USER
```

### Service Issues
```bash
# Check service status
sudo systemctl status barcode-scanner

# View logs
sudo journalctl -u barcode-scanner -f
```

## 📝 Configuration Files

### config.json (Auto-generated)
```json
{
  "raspberry_pi": {
    "auto_detected_ip": "192.168.1.18",
    "last_detection": "2025-01-22T13:49:00Z",
    "mac_address": "2c:cf:67:6c:45:f2"
  },
  "led_pins": {
    "red": 18,
    "green": 23,
    "yellow": 24,
    "orange": 25
  }
}
```

This configuration enables true plug-and-play deployment with automatic Pi detection and real hardware LED feedback!