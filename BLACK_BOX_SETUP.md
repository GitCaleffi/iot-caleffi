# Black Box Barcode Scanner Service

This is a completely automated barcode scanner service that runs without any user interaction. It operates as a true "black box" - you set it up once and it runs automatically forever.

## 🚀 Quick Setup (One-Time Only)

### On your Raspberry Pi:

```bash
ssh pi@10.0.1.68
cd /var/www/html/abhimanyu/barcode_scanner_clean
sudo ./setup_automation.sh
sudo reboot
```

**That's it!** The service will start automatically after reboot and run forever.

## 🤖 How It Works Automatically

### 1. **Boot Process**
- Raspberry Pi boots up
- Systemd automatically starts the barcode scanner service
- Service runs in background (no terminal needed)
- LEDs indicate service status

### 2. **Device Registration (Automatic)**
- Service auto-generates unique device ID
- Automatically registers with IoT Hub
- No user input required
- Saves configuration for future use

### 3. **Barcode Processing (Silent)**
- Continuously monitors for barcode scanner input
- Processes barcodes silently in background
- Sends data to API and IoT Hub automatically
- Only uses LED indicators for feedback

### 4. **Error Recovery (Self-Healing)**
- Automatically restarts if service crashes
- Handles network disconnections gracefully
- Retries failed operations automatically
- Logs all issues for monitoring

## 💡 LED Status Indicators

Since the service runs silently, it uses LEDs to show status:

- **🟢 Green LED**: Success (barcode processed successfully)
- **🟡 Yellow LED**: Warning (offline mode, saved locally)
- **🔴 Red LED**: Error (invalid barcode or processing failed)
- **LEDs Off**: Service idle, waiting for barcode

## 📊 Service Management

### Check if service is running:
```bash
sudo systemctl status barcode-scanner
```

### View live logs:
```bash
sudo journalctl -u barcode-scanner -f
```

### Manual control (if needed):
```bash
# Start service
sudo systemctl start barcode-scanner

# Stop service
sudo systemctl stop barcode-scanner

# Restart service
sudo systemctl restart barcode-scanner
```

### Easy management script:
```bash
./service_control.sh status    # Check status
./service_control.sh logs      # View logs
./service_control.sh restart   # Restart service
```

## 📁 Log Files

All activity is logged to files (no console output):

- **System logs**: `sudo journalctl -u barcode-scanner`
- **Application logs**: `tail -f scanner.log`
- **Cron logs**: `tail -f /home/pi/logs/cronlog`

## 🔧 Service Features

### ✅ **Completely Autonomous**
- No user interaction required
- Starts automatically on boot
- Runs continuously in background
- Self-recovers from errors

### ✅ **Silent Operation**
- No console output during operation
- No prompts or user input requests
- Only LED indicators for status
- All logging to files

### ✅ **Robust & Reliable**
- Automatic restart on failure
- Handles network issues gracefully
- Processes barcodes continuously
- Maintains local backup when offline

### ✅ **Professional Service**
- Systemd service integration
- Proper daemon operation
- Resource efficient
- Production ready

## 🔄 Automatic Startup Process

1. **Pi boots** → Systemd starts service
2. **Service starts** → Auto-registers device
3. **Device ready** → Waits for barcodes
4. **Barcode scanned** → Processes automatically
5. **Continues forever** → No intervention needed

## 🛠️ Troubleshooting

### Service not starting:
```bash
sudo systemctl status barcode-scanner
sudo journalctl -u barcode-scanner
```

### Check if process is running:
```bash
ps aux | grep keyboard_scanner
```

### Restart service:
```bash
sudo systemctl restart barcode-scanner
```

### View recent logs:
```bash
tail -50 scanner.log
```

## 🚫 What You DON'T Need to Do

- ❌ No manual startup required
- ❌ No user input during operation
- ❌ No terminal monitoring needed
- ❌ No manual device registration
- ❌ No configuration changes
- ❌ No maintenance tasks

## ✅ What Happens Automatically

- ✅ Starts on boot
- ✅ Registers device
- ✅ Processes barcodes
- ✅ Sends to IoT Hub
- ✅ Handles errors
- ✅ Logs activity
- ✅ Restarts if needed
- ✅ Runs forever

## 🎯 Perfect Black Box Operation

Once set up, the service operates completely independently:

1. **Set it up once** with the setup script
2. **Reboot the Pi** to activate
3. **Walk away** - it runs automatically
4. **Scan barcodes** - they're processed silently
5. **Check LEDs** for status if needed
6. **View logs** only if troubleshooting

The service is designed to run 24/7 without any human intervention, making it a true "black box" solution for barcode scanning operations.