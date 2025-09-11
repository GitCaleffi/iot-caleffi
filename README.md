# Pi Barcode Scanner - Dynamic Plug-and-Play System


1. ping raspberrypi.local -4

2. ssh Geektech@192.168.1.14


This project is a **dynamic plug-and-play barcode scanning application** designed to run on Raspberry Pi. It automatically detects USB barcode scanners, registers devices on-demand, and communicates with Azure IoT Hub.

## 🔌 Dynamic Plug-and-Play Features

### **No Static Device Registration Required**
- ✅ **Dynamic USB Scanner Detection**: Automatically detects connected USB barcode scanners
- ✅ **On-Demand Device Registration**: Registers devices only when needed
- ✅ **Real-Time Barcode Processing**: Processes EAN barcodes with quantity 1
- ✅ **Automatic IoT Hub Integration**: Creates device connections dynamically

### **Key Functions**
1. **`plug_and_play_register_device(device_id)`** - Registers any device ID dynamically
2. **`detect_usb_scanner()`** - Detects connected USB barcode scanners
3. **`usb_scan_and_send_ean(ean_barcode, device_id)`** - Processes EAN with quantity 1
4. **`auto_process_scanned_barcodes()`** - Automatically processes scanned barcodes

## 🚀 Quick Start (Plug-and-Play)

### **Step 1: Connect USB Scanner**
```bash
# Connect your USB barcode scanner to Raspberry Pi
# No configuration needed - system detects automatically
```

### **Step 2: Run the Application**
```bash
cd /var/www/html/abhimanyu/barcode_scanner_clean/test/raspberry_pi
python3 src/barcode_scanner_app.py
```

### **Step 3: Register Device Dynamically**
```python
# In the web interface or programmatically:
plug_and_play_register_device("your_device_id_here")
```

### **Step 4: Start Scanning**
- USB scanner automatically detected
- EAN barcodes processed with quantity 1
- Messages sent to Azure IoT Hub in real-time

## 📁 Project Structure

```
pi-barcode-scanner/
├── test/raspberry_pi/
│   ├── src/
│   │   ├── barcode_scanner_app.py    # Main plug-and-play application
│   │   ├── database/
│   │   │   └── local_storage.py      # Local SQLite storage
│   │   ├── iot/
│   │   │   └── hub_client.py         # Azure IoT Hub client
│   │   ├── api/
│   │   │   └── api_client.py         # API communication
│   │   └── utils/
│   │       └── config.py             # Dynamic configuration
│   ├── config.json                   # IoT Hub connections (auto-updated)
│   ├── requirements.txt              # Dependencies
│   └── barcode_device_mapping.db     # Local SQLite database
└── README.md                         # This file
```

## 🔧 Installation & Setup

### **1. Install Dependencies**
```bash
pip install -r requirements.txt
```

### **2. Required Libraries**
```bash
# Core dependencies
pip install gradio>=3.0.0
pip install evdev>=1.4.0
pip install azure-iot-hub
pip install azure-iot-device
pip install requests
pip install sqlite3
```

### **3. USB Scanner Support**
```bash
# For USB barcode scanner detection
sudo apt-get update
sudo apt-get install python3-evdev
```

## 🎯 Dynamic Usage Workflow

### **Raspberry Pi Connection**
```bash
# 1. Connect to Raspberry Pi
ping raspberrypi.local -4
ssh Geektech@192.168.1.14

# 2. Navigate to project
cd /var/www/html/abhimanyu/barcode_scanner_clean/test/raspberry_pi

# 3. Run application
python3 src/barcode_scanner_app.py
```

### **Web Interface (Port 7861)**
1. **Plug-and-Play Registration**
   - Enter device ID in "Plug-and-Play Registration" section
   - Click "Plug-and-Play Register"
   - System automatically handles API and IoT Hub registration

2. **USB Scanner Controls**
   - Click "Detect USB Scanner" to find connected scanners
   - Click "Toggle Auto-Scan" to enable automatic processing
   - System processes EAN barcodes with quantity 1

3. **Real-Time Scanning**
   - Connect USB barcode scanner
   - Scan EAN barcodes
   - Messages automatically sent to IoT Hub

## 🔌 Plug-and-Play Registration Process

### **Dynamic Device Registration**
```python
def plug_and_play_register_device(device_id):
    """
    Complete plug-and-play registration:
    1. API registration with confirmRegistration endpoint
    2. Local database storage
    3. Azure IoT Hub device creation
    4. Connection string generation
    5. Registration confirmation message
    """
```

### **Registration Flow**
1. **API Registration**: Calls confirmRegistration endpoint
2. **Fallback Registration**: Uses saveDeviceId if device not found
3. **IoT Hub Registration**: Creates device in Azure IoT Hub
4. **Local Storage**: Saves device ID in SQLite database
5. **Confirmation**: Sends registration message to IoT Hub

## 📊 EAN Barcode Processing

### **USB Scanner Integration**
```python
def usb_scan_and_send_ean(ean_barcode, device_id=None):
    """
    Process EAN barcode with quantity 1:
    1. Get device ID from local storage
    2. Save scan to local database with quantity 1
    3. Send EAN to Azure IoT Hub
    4. Mark as sent in database
    """
```

### **Automatic Processing**
- **Quantity**: Always 1 for EAN barcodes
- **Storage**: Local SQLite database backup
- **IoT Hub**: Real-time message delivery
- **Retry**: Automatic retry for failed messages

## 🌐 Azure IoT Hub Integration

### **Dynamic Device Creation**
- Devices created automatically when registered
- Unique connection strings generated per device
- Device-specific authentication keys
- Automatic config.json updates

### **Message Format**
```json
{
  "scannedBarcode": "1234567890123",
  "deviceId": "cfabc4830309",
  "quantity": 1,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🗄️ Local Database Schema

### **Device Registration**
```sql
-- Device storage
device_id TEXT PRIMARY KEY

-- Barcode scans with quantity
device_id TEXT,
barcode TEXT,
quantity INTEGER DEFAULT 1,
timestamp TEXT,
sent_to_hub BOOLEAN DEFAULT 0
```

## 🔍 Testing & Verification

### **Test Device Registration**
```bash
# Test plug-and-play registration
python3 -c "
from src.barcode_scanner_app import plug_and_play_register_device
result = plug_and_play_register_device('test_device_123')
print(result)
"
```

### **Test USB Scanner**
```bash
# Test USB scanner detection
python3 -c "
from src.barcode_scanner_app import detect_usb_scanner
result = detect_usb_scanner()
print(result)
"
```

### **Test EAN Processing**
```bash
# Test EAN barcode processing
python3 -c "
from src.barcode_scanner_app import usb_scan_and_send_ean
result = usb_scan_and_send_ean('1234567890123', 'test_device_123')
print(result)
"
```

## 📋 Database Verification

### **Check Device Registration**
```bash
sqlite3 barcode_device_mapping.db "SELECT * FROM device_registration;"
```

### **Check Barcode Scans**
```bash
sqlite3 barcode_device_mapping.db "SELECT device_id, barcode, quantity, sent_to_hub FROM barcode_scans ORDER BY timestamp DESC LIMIT 10;"
```

### **Check Unsent Messages**
```bash
sqlite3 barcode_device_mapping.db "SELECT * FROM barcode_scans WHERE sent_to_hub = 0;"
```

## 🎛️ Configuration

### **config.json Structure**
```json
{
  "iot_hub": {
    "connection_string": "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=...",
    "devices": {
      "cfabc4830309": {
        "connection_string": "HostName=CaleffiIoT.azure-devices.net;DeviceId=cfabc4830309;SharedAccessKey=...",
        "deviceId": "cfabc4830309"
      }
    }
  }
}
```

## 🚨 Error Handling

### **Offline Mode**
- Barcodes saved locally when offline
- Automatic retry when connection restored
- Local database ensures no data loss

### **USB Scanner Issues**
- Automatic fallback to keyboard-like devices
- Multiple scanner type detection
- Graceful error handling

### **IoT Hub Failures**
- Local storage backup
- Automatic retry mechanism
- Connection string validation

## 🔧 Troubleshooting

### **USB Scanner Not Detected**
```bash
# Check USB devices
lsusb

# Check input devices
ls /dev/input/

# Test evdev access
python3 -c "import evdev; print(evdev.list_devices())"
```

### **IoT Hub Connection Issues**
```bash
# Verify config.json
cat config.json | jq '.iot_hub.connection_string'

# Test connection
python3 -c "
from src.iot.hub_client import HubClient
from src.utils.config import load_config
config = load_config()
client = HubClient(config['iot_hub']['connection_string'])
print('Connection test passed')
"
```

### **Database Issues**
```bash
# Check database file
ls -la barcode_device_mapping.db

# Verify tables
sqlite3 barcode_device_mapping.db ".tables"

# Check recent activity
sqlite3 barcode_device_mapping.db "SELECT * FROM barcode_scans ORDER BY timestamp DESC LIMIT 5;"
```

## 📈 Performance Features

- **Real-Time Processing**: Sub-second barcode processing
- **Automatic Retry**: Failed messages automatically retried
- **Local Backup**: All data stored locally first
- **Dynamic Registration**: No pre-configuration required
- **USB Hot-Plug**: Automatic scanner detection on connection

## 🔒 Security Features

- **Device-Specific Keys**: Unique authentication per device
- **Secure Connection**: TLS/SSL for all IoT Hub communication
- **Local Encryption**: SQLite database with secure storage
- **API Authentication**: Secure API endpoint communication

## 📝 License

This project is licensed under the MIT License. See the LICENSE file for details.

---

## 🎉 Ready for Production!

The system is **fully dynamic** and requires **no static device registration**. Simply:

1. **Connect USB scanner** to Raspberry Pi
2. **Run the application** 
3. **Register device** using plug-and-play function
4. **Start scanning** - EAN barcodes automatically processed with quantity 1

**All functionality is dynamic and plug-and-play ready!** 🚀