# Auto Barcode Scanner - Plug and Play Guide

## 🎯 Zero-Configuration Barcode Scanning

This system provides **true plug-and-play** barcode scanning for non-technical users. No manual configuration, no device registration steps, no technical knowledge required.

## 🚀 Quick Start (3 Steps)

### Step 1: Connect Scanner
- Plug USB barcode scanner into any USB port
- System automatically detects the scanner

### Step 2: Start Service
Choose one option:

**Option A: Manual Start**
```bash
cd /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package
python3 start_auto_scanner.py
```

**Option B: Install as System Service (Recommended)**
```bash
cd /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package
chmod +x install_auto_service.sh
./install_auto_service.sh
```

### Step 3: Start Scanning
- Point scanner at any barcode
- Pull trigger to scan
- System automatically processes everything

## ✅ What Happens Automatically

1. **Device Registration**: System generates unique device ID based on hardware
2. **IoT Hub Registration**: Device automatically registers with Azure IoT Hub
3. **Barcode Processing**: All scanned barcodes sent to inventory system
4. **Offline Handling**: Barcodes saved locally when offline, sent when online
5. **Error Recovery**: Automatic retry of failed operations

## 🎮 User Experience

```
🚀 AUTO BARCODE SERVICE STARTING...
==================================================
📱 Connect your USB barcode scanner
🔄 System will automatically process all scans
📡 All data sent to inventory system
⏹️  Press Ctrl+C to stop
==================================================
✅ USB SCANNER: Detected and ready
✅ DEVICE: device-a1b2c3d4 registered and ready

📊 SCANNED: 1234567890123
✅ SUCCESS: Barcode sent to inventory system

📊 SCANNED: 9876543210987
✅ SUCCESS: Barcode sent to inventory system
```

## 🔧 System Service Management

After installing as a service:

```bash
# Check service status
sudo systemctl status auto-barcode-scanner

# View live logs
sudo journalctl -u auto-barcode-scanner -f

# Stop service
sudo systemctl stop auto-barcode-scanner

# Start service
sudo systemctl start auto-barcode-scanner

# Restart service
sudo systemctl restart auto-barcode-scanner
```

## 📱 LED Feedback (Raspberry Pi)

- **Green Solid**: Successfully sent to inventory system
- **Yellow Blinking**: Processing in progress
- **Red Solid**: Error or offline (saved locally for retry)

## 🌐 Network Requirements

- **Internet Connection**: Required for IoT Hub and API communication
- **Offline Mode**: Barcodes saved locally, sent when connection restored
- **Auto-Retry**: System automatically retries failed sends

## 🔍 Troubleshooting

### Scanner Not Detected
- Ensure USB scanner is properly connected
- Try different USB port
- Check if scanner appears in `lsusb` output

### No Barcode Response
- Ensure scanner is configured for keyboard emulation mode
- Try scanning test barcode: `1234567890123`
- Check system logs for errors

### Connection Issues
- Verify internet connection
- Check IoT Hub configuration in config.json
- Review service logs: `sudo journalctl -u auto-barcode-scanner -f`

### Service Won't Start
```bash
# Check service status
sudo systemctl status auto-barcode-scanner

# Check logs
sudo journalctl -u auto-barcode-scanner --no-pager -l

# Restart service
sudo systemctl restart auto-barcode-scanner
```

## 📊 Features

- ✅ **Zero Configuration**: No manual setup required
- ✅ **Automatic Registration**: Device auto-registers with IoT Hub
- ✅ **USB Scanner Detection**: Automatically detects connected scanners
- ✅ **Dual Channel**: Sends to both API and IoT Hub
- ✅ **Offline Support**: Local storage with automatic retry
- ✅ **Error Recovery**: Robust error handling and recovery
- ✅ **System Service**: Runs automatically on boot
- ✅ **Real-time Processing**: Instant barcode processing
- ✅ **Hardware-based ID**: Unique device identification

## 🎯 Perfect for Non-Technical Users

- **No URLs to remember**
- **No device IDs to enter**
- **No registration forms**
- **No technical configuration**
- **Just plug in scanner and start scanning**

## 📞 Support

If you encounter any issues:
1. Check the service logs: `sudo journalctl -u auto-barcode-scanner -f`
2. Verify scanner connection: `lsusb`
3. Test network connectivity
4. Restart the service: `sudo systemctl restart auto-barcode-scanner`

---

**Ready for 10,000+ users with zero technical knowledge required!**
