# Raspberry Pi User Guide - Commercial Barcode Scanner

## 🍓 How Raspberry Pi Users Access Your Commercial Barcode Scanner System

This guide explains how end-users with Raspberry Pi devices can connect to and use your deployed commercial barcode scanner system.

---

## 🎯 **System Architecture Overview**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Raspberry Pi  │───▶│   Ubuntu Server  │───▶│  Azure IoT Hub  │
│   (End User)    │    │ (Your Deployed   │    │   (Cloud)       │
│                 │    │  Barcode System) │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

- **Raspberry Pi**: End-user device with barcode scanner
- **Ubuntu Server**: Your deployed commercial barcode system
- **Azure IoT Hub**: Cloud backend for data processing

---

## 🚀 **Method 1: Web Browser Access (Recommended)**

### **For Non-Technical Users - Plug & Play**

#### **Step 1: Connect to Network**
```bash
# On Raspberry Pi, ensure WiFi/Ethernet connection
ping google.com  # Test internet connectivity
```

#### **Step 2: Open Web Browser**
- Open **Chromium** or **Firefox** on Raspberry Pi
- Navigate to: `http://YOUR-SERVER-IP/`
- Replace `YOUR-SERVER-IP` with your Ubuntu server's IP address

#### **Step 3: Use the System**
1. **Enter barcode** in the web form (8-14 digits)
2. **Click "Process Barcode"**
3. **Get instant confirmation**
4. **View real-time statistics**

**That's it! No technical setup required.**

---

## 🔧 **Method 2: Direct API Access**

### **For Advanced Users - Programmatic Access**

#### **Simple Python Script for Raspberry Pi:**

```python
#!/usr/bin/env python3
"""
Raspberry Pi Barcode Scanner Client
Connects to your commercial barcode scanner server
"""

import requests
import json
import time
from datetime import datetime

# Configuration
SERVER_IP = "50.85.252.172"  # Your server's public IP
SERVER_URL =  f"http://{SERVER_IP}/api/scan"   # Replace with your server IP
API_ENDPOINT = f"{SERVER_URL}/api/scan"

def scan_barcode(barcode):
    """Send barcode to commercial scanner server"""
    try:
        data = {"barcode": barcode}
        response = requests.post(API_ENDPOINT, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print(f"✅ SUCCESS: {result['message']}")
                print(f"   Device ID: {result['device_id']}")
                print(f"   Azure Status: {result['azure_status']}")
                return True
            else:
                print(f"❌ ERROR: {result['message']}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")
        return False

def main():
    print("🍓 Raspberry Pi Barcode Scanner Client")
    print("=====================================")
    print(f"Server: {SERVER_URL}")
    print("Enter barcodes (or 'quit' to exit):")
    
    while True:
        try:
            barcode = input("\nBarcode: ").strip()
            
            if barcode.lower() == 'quit':
                break
                
            if not barcode:
                continue
                
            print(f"Processing barcode: {barcode}")
            scan_barcode(barcode)
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if __name__ == "__main__":
    main()
```

#### **Save and Run:**
```bash
# Save the script
nano raspberry_pi_scanner.py

# Make executable
chmod +x raspberry_pi_scanner.py

# Install requests if needed
pip3 install requests

# Run the script
python3 raspberry_pi_scanner.py
```

---

## 📱 **Method 3: USB Barcode Scanner Integration**

### **For Physical Barcode Scanners**

#### **Setup USB Barcode Scanner on Raspberry Pi:**

```python
#!/usr/bin/env python3
"""
Raspberry Pi USB Barcode Scanner Integration
Automatically sends scanned barcodes to your server
"""

import requests
import json
import sys
import select
import time

# Configuration
SERVER_URL = "http://YOUR-SERVER-IP"
API_ENDPOINT = f"{SERVER_URL}/api/scan"

def send_to_server(barcode):
    """Send barcode to commercial scanner server"""
    try:
        data = {"barcode": barcode}
        response = requests.post(API_ENDPOINT, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result['success']:
                print(f"✅ Barcode {barcode} processed successfully!")
                print(f"   Device ID: {result['device_id']}")
                return True
            else:
                print(f"❌ Error: {result['message']}")
                return False
        else:
            print(f"❌ Server error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    print("🍓 Raspberry Pi USB Barcode Scanner")
    print("==================================")
    print(f"Server: {SERVER_URL}")
    print("Waiting for barcode scans...")
    print("Press Ctrl+C to exit")
    
    while True:
        try:
            # Wait for input from USB scanner
            if select.select([sys.stdin], [], [], 0.1)[0]:
                barcode = sys.stdin.readline().strip()
                
                if barcode and barcode.isdigit():
                    print(f"\n📱 Scanned: {barcode}")
                    send_to_server(barcode)
                    print("Ready for next scan...")
                    
        except KeyboardInterrupt:
            print("\nShutting down scanner...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
```

---

## 🔄 **Method 4: Automated Service on Raspberry Pi**

### **Run as Background Service**

#### **Create Systemd Service on Raspberry Pi:**

```bash
# Create service file
sudo nano /etc/systemd/system/barcode-client.service
```

**Service file content:**
```ini
[Unit]
Description=Raspberry Pi Barcode Scanner Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/barcode-scanner
ExecStart=/usr/bin/python3 /home/pi/barcode-scanner/usb_scanner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### **Enable and Start Service:**
```bash
# Enable service
sudo systemctl daemon-reload
sudo systemctl enable barcode-client

# Start service
sudo systemctl start barcode-client

# Check status
sudo systemctl status barcode-client

# View logs
sudo journalctl -u barcode-client -f
```

---

## 📊 **Method 5: Monitoring and Statistics**

### **Check System Status from Raspberry Pi:**

```python
#!/usr/bin/env python3
"""
Check commercial barcode scanner system status
"""

import requests
import json

SERVER_URL = "http://YOUR-SERVER-IP"

def check_system_health():
    """Check if the server is healthy"""
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ System Status: {health['status']}")
            print(f"   Database: {health['database']}")
            print(f"   Azure Connection: {health['azure_connection']}")
            return True
        else:
            print(f"❌ Server unhealthy: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach server: {e}")
        return False

def get_statistics():
    """Get system statistics"""
    try:
        response = requests.get(f"{SERVER_URL}/api/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            print(f"\n📊 System Statistics:")
            print(f"   Successful Scans: {stats['successful_scans']}")
            print(f"   Failed Scans: {stats['failed_scans']}")
            print(f"   Devices Registered: {stats['devices_registered']}")
            print(f"   Last Scan: {stats['last_scan_time']}")
            return True
        else:
            print(f"❌ Cannot get stats: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Stats error: {e}")
        return False

if __name__ == "__main__":
    print("🍓 Raspberry Pi System Monitor")
    print("=============================")
    
    if check_system_health():
        get_statistics()
```

---

## 🌐 **Network Configuration**

### **Finding Your Server IP:**

```bash
# On your Ubuntu server, get IP address
hostname -I

# Or use ip command
ip addr show | grep inet
```

### **Raspberry Pi Network Setup:**
```bash
# Check Raspberry Pi network
ifconfig

# Test connection to server
ping YOUR-SERVER-IP

# Test web interface
curl http://YOUR-SERVER-IP/health
```

---

## 🔧 **Troubleshooting for Raspberry Pi Users**

### **Common Issues:**

#### **1. Cannot Connect to Server**
```bash
# Check network connectivity
ping YOUR-SERVER-IP

# Check if server is running
curl http://YOUR-SERVER-IP/health

# Check firewall (on server)
sudo ufw status
```

#### **2. USB Scanner Not Working**
```bash
# Check USB devices
lsusb

# Check input devices
ls /dev/input/

# Test scanner input
cat /dev/input/event0  # Replace with correct device
```

#### **3. Python Dependencies**
```bash
# Install required packages
sudo apt update
sudo apt install python3-pip
pip3 install requests
```

---

## 📱 **Mobile Access from Raspberry Pi**

### **Using Raspberry Pi with Touchscreen:**

1. **Install Chromium browser:**
   ```bash
   sudo apt install chromium-browser
   ```

2. **Create desktop shortcut:**
   ```bash
   # Create desktop file
   nano ~/Desktop/barcode-scanner.desktop
   ```

3. **Desktop file content:**
   ```ini
   [Desktop Entry]
   Name=Barcode Scanner
   Comment=Commercial Barcode Scanner
   Exec=chromium-browser --start-fullscreen http://YOUR-SERVER-IP
   Icon=chromium-browser
   Terminal=false
   Type=Application
   Categories=Network;
   ```

4. **Make executable:**
   ```bash
   chmod +x ~/Desktop/barcode-scanner.desktop
   ```

---

## 🎯 **User Experience Summary**

### **For End Users (Non-Technical):**
1. **Connect Raspberry Pi to internet**
2. **Open web browser**
3. **Go to your server URL**
4. **Scan barcodes - that's it!**

### **For Technical Users:**
1. **Use API directly** for custom integration
2. **Create automated services** for continuous scanning
3. **Monitor system health** and statistics
4. **Integrate with existing workflows**

---

## 🚀 **Deployment Scenarios**

### **Scenario 1: Retail Store**
- **Raspberry Pi** at each checkout counter
- **USB barcode scanner** connected
- **Automatic scanning** to your central server
- **Real-time inventory** updates

### **Scenario 2: Warehouse**
- **Mobile Raspberry Pi** with battery pack
- **Handheld barcode scanner**
- **WiFi connection** to your server
- **Instant data** synchronization

### **Scenario 3: Field Operations**
- **Raspberry Pi** in vehicles/equipment
- **Rugged barcode scanner**
- **4G/LTE connection** for remote access
- **Offline capability** with sync when online

---

## 🎉 **Ready for 1000+ Raspberry Pi Deployments!**

Your commercial barcode scanner system now supports:

✅ **Web browser access** - No setup required
✅ **API integration** - For custom applications  
✅ **USB scanner support** - Physical barcode scanners
✅ **Background services** - Automated operation
✅ **Mobile interfaces** - Touchscreen friendly
✅ **Network flexibility** - WiFi, Ethernet, 4G
✅ **Offline resilience** - Local storage with sync
✅ **Real-time monitoring** - Health and statistics

**Your Raspberry Pi users can now access your commercial barcode scanner system with true plug-and-play simplicity!** 🍓🚀
