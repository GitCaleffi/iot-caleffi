# Blackbox Raspberry Pi Deployment Guide

## Overview
This guide explains how to deploy your barcode scanner application as a complete blackbox solution for customers. The Raspberry Pi operates autonomously with zero technical knowledge required from end users.

## Customer Experience

### What Customers Receive
- Pre-configured Raspberry Pi with SD card
- USB barcode scanner
- Power adapter
- Simple instruction card

### Customer Setup Process
1. **Connect hardware**: Plug in Pi, connect barcode scanner
2. **Power on**: Insert power adapter
3. **Wait 2 minutes**: Pi boots and discovers server
4. **Scan any barcode**: Device auto-registers and becomes operational
5. **Done**: System is fully operational

## Technical Implementation

### Automatic Operations

#### 1. Server Discovery
```python
# Pi automatically tries these discovery methods:
- https://iot.caleffionline.it (your production server)
- Local network scan (10.0.0.4, 192.168.1.1, etc.)
- mDNS/Bonjour discovery
- Broadcast discovery
```

#### 2. Device Registration
```python
# Triggered by first barcode scan:
- Generates unique device ID (CPU serial + MAC address)
- Sends registration request with scanned barcode
- Receives IoT Hub connection string
- Saves configuration locally
- Starts operational mode
```

#### 3. Ongoing Automation
```python
# Background services run continuously:
- OTA updates: Check every hour, auto-apply
- Heartbeat: Send status every 5 minutes
- Barcode processing: Real-time scanning
- Error recovery: Auto-restart on failures
```

## Deployment Package Structure

```
raspberry-pi-deployment/
├── barcode_scanner_app.py          # Main application
├── install_barcode_scanner_plug_play.sh  # Installation script
├── requirements.txt                # Python dependencies
├── config.json.template           # Configuration template
├── README_CUSTOMER.md             # Simple customer instructions
└── systemd/
    └── barcode-scanner-plug-play.service  # System service
```

## Server-Side Requirements

### API Endpoints (Already Implemented)
- `POST /api/register_device` - Device registration
- `GET /api/ota/check_update` - Update checking
- `GET /api/ota/download_update` - Update download
- `POST /api/ota/update_status` - Update status reporting
- `POST /api/device_heartbeat` - Health monitoring

### Configuration
```json
{
  "server_urls": [
    "https://iot.caleffionline.it",
    "http://10.0.0.4:5000",
    "http://192.168.1.1:5000"
  ],
  "iot_hub": {
    "connection_string": "HostName=your-hub.azure-devices.net;..."
  }
}
```

## Pi Installation Process

### Automated Installation
```bash
# Run on fresh Raspberry Pi OS
curl -sSL https://your-server.com/install.sh | bash

# Or manual installation:
chmod +x install_barcode_scanner_plug_play.sh
sudo ./install_barcode_scanner_plug_play.sh
```

### What Installation Does
1. **Environment Setup**
   - Creates Python virtual environment
   - Installs dependencies (requests, azure-iot-device, etc.)
   - Sets up application directory `/opt/barcode-scanner/`

2. **System Configuration**
   - Creates systemd service for auto-start
   - Sets up USB scanner permissions
   - Configures log rotation
   - Enables service on boot

3. **Security Setup**
   - Creates dedicated user account
   - Sets proper file permissions
   - Configures firewall rules

## Blackbox Features

### Zero Configuration
- No IP addresses to configure
- No server URLs to enter
- No technical setup required
- Works across different networks

### Automatic Updates
```python
# Update process (every hour):
1. Check server for new version
2. Download update package
3. Create backup of current version
4. Apply update atomically
5. Restart service
6. Report success/failure to server
```

### Self-Healing
- Auto-restart on crashes
- Network reconnection handling
- IoT Hub connection recovery
- Fallback server discovery

### Monitoring & Diagnostics
```python
# Heartbeat data sent every 5 minutes:
{
  "device_id": "pi-abc123-def456",
  "status": "online",
  "timestamp": "2024-01-15T10:30:00Z",
  "system_info": {
    "hostname": "raspberrypi",
    "uptime": 86400,
    "version": "2.0.0",
    "last_scan": "2024-01-15T10:25:00Z"
  }
}
```

## Customer Support

### Remote Diagnostics
- Real-time device status via web dashboard
- Remote log access through server API
- OTA troubleshooting and fixes
- Device health monitoring

### Simple Troubleshooting
1. **No scanning**: Check USB connection, restart Pi
2. **No network**: Check ethernet/WiFi, Pi auto-reconnects
3. **Not registered**: Scan any barcode to re-register
4. **Updates failing**: Pi auto-retries, server can push fixes

## Production Deployment Checklist

### Server Preparation
- [ ] Deploy server with Pi registration API
- [ ] Configure IoT Hub connection strings
- [ ] Set up OTA update repository
- [ ] Test cross-network discovery

### Pi Image Preparation
- [ ] Flash Raspberry Pi OS
- [ ] Run installation script
- [ ] Test plug-and-play registration
- [ ] Create master SD card image
- [ ] Duplicate for customer deployment

### Quality Assurance
- [ ] Test on different network configurations
- [ ] Verify OTA update process
- [ ] Test barcode scanning functionality
- [ ] Validate IoT Hub connectivity
- [ ] Confirm heartbeat monitoring

### Customer Handover
- [ ] Provide pre-configured Pi devices
- [ ] Include simple setup instructions
- [ ] Set up monitoring dashboard access
- [ ] Establish support procedures

## Maintenance & Updates

### Pushing Updates
1. Upload new version to server OTA repository
2. Pis automatically detect and apply updates
3. Monitor update success via dashboard
4. Rollback if issues detected

### Monitoring Fleet
- Device status dashboard
- Update deployment tracking
- Error reporting and alerts
- Usage analytics and insights

## Security Considerations

### Device Security
- Unique device certificates
- Encrypted communication (HTTPS/TLS)
- Signed update packages
- Local configuration encryption

### Network Security
- No inbound connections required
- Outbound HTTPS only
- IoT Hub device authentication
- Server API key authentication

This blackbox deployment ensures your customers can deploy barcode scanning devices with zero technical expertise while maintaining full remote management and update capabilities.
