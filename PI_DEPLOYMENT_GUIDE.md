# Raspberry Pi Auto Client - Complete Deployment Guide

## Overview

The Raspberry Pi Auto Client is a **complete autonomous system** that transforms any Raspberry Pi into a plug-and-play barcode scanning device. Once installed, the Pi becomes a "black box" that requires **zero user configuration** and handles everything automatically.

## What the Pi Client Does Automatically

### 🔄 **Auto-Registration**
- Generates unique device ID based on hardware (CPU serial/MAC address)
- Discovers the live server automatically on network startup
- Registers itself with the server and receives IoT Hub connection string
- No manual device registration required

### 📦 **Over-The-Air (OTA) Updates**
- Checks for updates every hour automatically
- Downloads and applies updates with automatic rollback on failure
- Creates backups before updates and restores if needed
- Notifies server of update status
- Restarts service automatically after successful updates

### 💓 **Health Monitoring & Heartbeat**
- Sends heartbeat to IoT Hub every 30 seconds via Device Twin
- Reports system status (online/offline, IP address, uptime, services)
- Automatic reconnection handling for network interruptions
- Real-time status reporting to live server

### 📊 **Barcode Processing**
- Listens for USB barcode scanner input automatically
- Processes scanned barcodes and sends to both API and IoT Hub
- Handles offline scenarios with local queuing and retry
- No user interaction required for barcode scanning

### 🌐 **Network Management**
- Auto-discovers server on different network segments
- Handles network changes (LAN, Wi-Fi, mobile hotspot)
- Automatic reconnection when network is restored
- Works across different IP ranges (192.168.x.x, 10.x.x.x, etc.)

## Installation Process

### 1. **Prepare Raspberry Pi**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Copy installation files to Pi
scp pi_auto_client.py pi@192.168.1.18:/home/pi/
scp install_pi_client.sh pi@192.168.1.18:/home/pi/
```

### 2. **Run Installation Script**
```bash
# SSH into Raspberry Pi
ssh pi@192.168.1.18

# Make installation script executable
chmod +x install_pi_client.sh

# Run installation (requires sudo)
sudo ./install_pi_client.sh
```

### 3. **Verify Installation**
```bash
# Check service status
sudo systemctl status pi-auto-client

# View real-time logs
sudo journalctl -u pi-auto-client -f

# Check if device registered
curl http://192.168.1.18:5000/api/pi_devices
```

## What Gets Installed

### **System Service**
- **Service Name**: `pi-auto-client.service`
- **Location**: `/opt/pi-auto-client/`
- **Auto-start**: Enabled on boot
- **Auto-restart**: On failure with 10-second delay

### **Configuration**
- **Config File**: `/etc/pi_auto_client.json`
- **Log File**: `/var/log/pi_auto_client.log`
- **Log Rotation**: Daily, 7 days retention

### **USB Scanner Support**
- **udev Rules**: Automatic USB barcode scanner detection
- **Permissions**: Proper access to input devices
- **HID Support**: Works with standard USB HID barcode scanners

## Server-Side Requirements

The live server must have the Pi Registration API endpoints available:

### **Required API Endpoints**
```
POST /api/register_device          # Device registration
GET  /api/ota/check_update        # Update checking
GET  /api/ota/download_update     # Update download
POST /api/ota/update_status       # Update status reporting
GET  /api/pi_devices              # Device listing
GET  /api/health                  # Health check for discovery
```

### **Server Integration**
The Pi Registration API has been integrated into `web_app.py`:
```python
from src.api.pi_registration_api import pi_api
app.register_blueprint(pi_api)
```

## Customer Deployment Workflow

### **For 10,000+ Non-Technical Users**

1. **Pre-configure Raspberry Pi**
   - Install Pi Auto Client on Pi devices before shipping
   - No customer configuration required

2. **Customer Receives Pi**
   - Connect USB barcode scanner
   - Connect Pi to network (Ethernet or Wi-Fi)
   - Power on Pi

3. **Automatic Operation**
   - Pi boots and auto-registers with server
   - Receives IoT Hub connection string
   - Starts barcode scanning immediately
   - Updates automatically when available

4. **Zero Maintenance**
   - No manual updates required
   - No configuration changes needed
   - Automatic error recovery and reconnection

## Management Commands

### **Service Management**
```bash
# Start service
sudo systemctl start pi-auto-client

# Stop service
sudo systemctl stop pi-auto-client

# Restart service
sudo systemctl restart pi-auto-client

# Check status
sudo systemctl status pi-auto-client

# View logs
sudo journalctl -u pi-auto-client -f
```

### **Manual Operations**
```bash
# Force update check
sudo /opt/pi-auto-client/update_client.sh

# Uninstall completely
sudo /opt/pi-auto-client/uninstall.sh

# View configuration
cat /etc/pi_auto_client.json

# Check device registration
curl http://your-server:5000/api/pi_device/$(hostname)
```

## Troubleshooting

### **Common Issues**

1. **Pi Not Registering**
   - Check network connectivity: `ping 8.8.8.8`
   - Verify server discovery: `curl http://10.0.0.4:5000/api/health`
   - Check service logs: `sudo journalctl -u pi-auto-client -f`

2. **Barcode Scanner Not Working**
   - Check USB connection: `lsusb`
   - Verify input permissions: `ls -la /dev/input/`
   - Test scanner: `sudo cat /dev/input/event0` (scan barcode)

3. **IoT Hub Connection Issues**
   - Verify device registration: Check server `/api/pi_devices`
   - Check connection string in config: `/etc/pi_auto_client.json`
   - Test Azure connectivity: `ping CaleffiIoT.azure-devices.net`

4. **Update Failures**
   - Check server update endpoints: `/api/ota/check_update`
   - Verify backup creation: Check `/tmp/backup_*.zip`
   - Manual rollback: `sudo /opt/pi-auto-client/uninstall.sh && reinstall`

### **Log Analysis**
```bash
# View registration logs
sudo journalctl -u pi-auto-client | grep "register"

# View update logs
sudo journalctl -u pi-auto-client | grep "update"

# View barcode processing logs
sudo journalctl -u pi-auto-client | grep "barcode"

# View IoT Hub logs
sudo journalctl -u pi-auto-client | grep "IoT Hub"
```

## Security Considerations

### **Network Security**
- Pi communicates only with configured server
- HTTPS support for external server connections
- No open ports or services exposed

### **Update Security**
- SHA256 hash verification for all updates
- Automatic backup and rollback on failure
- Signed update packages (can be implemented)

### **Device Security**
- Unique device IDs prevent impersonation
- Connection strings are device-specific
- No hardcoded credentials in code

## Production Deployment Checklist

### **Before Shipping Pi Devices**
- [ ] Install Pi Auto Client on all devices
- [ ] Test auto-registration with live server
- [ ] Verify barcode scanner compatibility
- [ ] Test OTA update process
- [ ] Confirm IoT Hub connectivity
- [ ] Validate offline/online scenarios

### **Server Preparation**
- [ ] Deploy Pi Registration API endpoints
- [ ] Configure IoT Hub device provisioning
- [ ] Set up update package distribution
- [ ] Test device discovery and registration
- [ ] Monitor device heartbeats and status

### **Customer Support**
- [ ] Prepare troubleshooting guides
- [ ] Set up remote monitoring dashboard
- [ ] Configure alerting for device issues
- [ ] Train support team on Pi management

## Architecture Benefits

### **For Customers (Non-Technical Users)**
- **Zero Configuration**: Plug and play operation
- **Automatic Updates**: No manual maintenance required
- **Self-Healing**: Automatic error recovery and reconnection
- **Transparent Operation**: Works like an appliance

### **For Caleffi (Technical Team)**
- **Centralized Management**: Monitor all devices from server
- **Remote Updates**: Push updates to all devices simultaneously
- **Real-time Monitoring**: Device status and health reporting
- **Scalable Architecture**: Supports thousands of devices

### **For System Reliability**
- **Offline Resilience**: Continues working without internet
- **Network Flexibility**: Works on any network configuration
- **Automatic Recovery**: Self-healing from failures
- **Update Safety**: Rollback protection for failed updates

This complete system transforms the Raspberry Pi into a true "black box" appliance that customers can use without any technical knowledge while providing Caleffi with full remote management capabilities.
