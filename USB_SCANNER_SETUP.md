# 🚀 Automatic USB Barcode Scanner Setup

## Overview
The USB barcode scanner is now **FULLY AUTOMATIC**. When you connect a USB scanner and run the automatic script, it will:

1. ✅ **Auto-detect** the USB scanner when connected
2. ✅ **Auto-register** the device on the first barcode scan
3. ✅ **Auto-send** all scanned barcodes to Azure IoT Hub
4. ✅ **Auto-reconnect** if the scanner is disconnected
5. ✅ **Auto-retry** failed messages when back online

## 🔧 Quick Start

### Option 1: Run Directly (Recommended for Testing)
```bash
# Make the script executable
chmod +x start_auto_usb_scanner.sh

# Run the automatic scanner
./start_auto_usb_scanner.sh
```

### Option 2: Install as System Service (Recommended for Production)
```bash
# Run as root to install as service
sudo ./start_auto_usb_scanner.sh

# The service will:
# - Start automatically on boot
# - Restart if it crashes
# - Run in the background
```

## 📱 How It Works

### First Time Setup
1. Connect your USB barcode scanner
2. Run the script: `./start_auto_usb_scanner.sh`
3. Scan any barcode - the device will auto-register
4. All subsequent scans are automatically sent to IoT Hub

### Normal Operation
1. Scanner detects barcode → Automatically sends to IoT Hub
2. No manual intervention needed
3. Works offline (queues messages for later)

## 🛠️ Service Management

If installed as a service:

```bash
# Check service status
sudo systemctl status usb_scanner_auto

# View real-time logs
sudo journalctl -u usb_scanner_auto -f

# Stop the service
sudo systemctl stop usb_scanner_auto

# Start the service
sudo systemctl start usb_scanner_auto

# Disable auto-start on boot
sudo systemctl disable usb_scanner_auto

# Enable auto-start on boot
sudo systemctl enable usb_scanner_auto
```

## 🔍 Troubleshooting

### Scanner Not Detected
1. Check USB connection
2. Try different USB port
3. Check scanner compatibility (most HID scanners work)
4. View logs: `sudo journalctl -u usb_scanner_auto -f`

### Registration Issues
1. Ensure internet connectivity
2. Check API endpoints are accessible
3. Verify Azure IoT Hub configuration in `config.json`

### Messages Not Sending
1. Check network connection
2. Verify device is registered in IoT Hub
3. Check Azure connection string in config
4. View queued messages in local database

## 📊 Features

### Automatic Device Registration
- First barcode scan triggers auto-registration
- No manual device ID entry needed
- Registers with both API and Azure IoT Hub

### Persistent Connection
- Maintains connection to IoT Hub
- Auto-reconnects on disconnection
- Efficient message sending

### Offline Support
- Queues messages when offline
- Auto-sends when back online
- No data loss

### Multi-Scanner Support
- Auto-detects various scanner brands
- Works with keyboard-emulation scanners
- Supports USB HID scanners

## 🔧 Configuration

The system uses `config.json` for Azure IoT Hub settings:

```json
{
  "iot_hub": {
    "connection_string": "Your IoT Hub connection string",
    "devices": {
      // Auto-populated when devices register
    }
  }
}
```

## 📝 Manual Testing

To test the automatic scanner manually:

```bash
# Run directly with Python
python3 src/usb_auto_scanner.py

# The script will:
# 1. Wait for USB scanner connection
# 2. Auto-register on first scan
# 3. Process all scans automatically
```

## 🚨 Important Notes

1. **Device Registration**: The device auto-registers using the first scanned barcode
2. **Persistent Storage**: All scans are saved locally before sending
3. **Error Recovery**: Automatic retry for failed messages
4. **No UI Needed**: Completely headless operation

## 📱 Supported Scanners

Tested with:
- Honeywell scanners
- Symbol/Zebra scanners
- Datalogic scanners
- Generic USB HID barcode scanners

## 🔄 Comparison with Web App

| Feature | Web App (`barcode_scanner_app.py`) | Auto Scanner (`usb_auto_scanner.py`) |
|---------|-------------------------------------|---------------------------------------|
| UI Required | Yes (Gradio Web) | No (Headless) |
| Manual Steps | Multiple clicks | None |
| Auto-register | No | Yes |
| Auto-send | No | Yes |
| Service Mode | No | Yes |
| Offline Queue | Manual trigger | Automatic |

## 🎯 Use Cases

### Production/Warehouse
- Install as service for 24/7 operation
- No operator intervention needed
- Automatic data collection

### Testing/Development
- Run manually for debugging
- View real-time logs
- Test different scanners

## 📞 Support

For issues:
1. Check logs: `sudo journalctl -u usb_scanner_auto -f`
2. Verify configuration: `cat config.json`
3. Test connectivity: `ping CaleffiIoT.azure-devices.net`
4. Check device registration in Azure Portal

---

**Version**: 1.0.0  
**Last Updated**: 2024-01-11  
**Status**: Production Ready