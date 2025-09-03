# Client Deployment Package - Complete Guide

## Problem Solved: Cross-Network Pi Discovery & Barcode Registration

Your current system works locally (Pi at 192.168.1.18 connects to server at 10.0.0.4), but when deploying to client's server, Pi devices need to:

1. **Find the server** across different networks
2. **Register via barcode scan** (plug-and-play)
3. **Send IoT messages** from anywhere

## Solution: Enhanced Plug-and-Play System

### **Pi Client Flow:**
```
Pi boots → Connects to Wi-Fi → Discovers server → Waits for barcode scan → 
Registers with scanned barcode → Starts sending IoT messages
```

### **Server Discovery Priority:**
1. `https://iot.caleffionline.it` (client's production server)
2. `http://iot.caleffionline.it` (HTTP fallback)
3. Local network discovery (10.0.0.4, 192.168.1.1, etc.)
4. Cloud API fallback

## Deployment Steps for Client's Server

### **1. Server-Side Deployment**

Copy these files to client's server:

```bash
# Core system files
src/api/pi_registration_api.py
src/database/local_storage.py
src/iot/dynamic_registration_service.py
web_app.py (with Pi API integrated)

# Configuration
config.json (update server URLs)
```

**Update client's web_app.py:**
```python
from src.api.pi_registration_api import pi_api
app.register_blueprint(pi_api)
```

**Required API endpoints on client's server:**
- `POST /api/register_device` - Pi registration
- `GET /api/health` - Server discovery
- `POST /api/v1/raspberry/barcodeScan` - Barcode processing
- `GET /api/ota/check_update` - Update checking

### **2. Pi Device Preparation**

**For each Raspberry Pi device:**

```bash
# 1. Copy deployment files to Pi
scp pi_plug_and_play_client.py pi@192.168.1.18:/home/pi/
scp install_plug_and_play.sh pi@192.168.1.18:/home/pi/

# 2. SSH into Pi and install
ssh pi@192.168.1.18
sudo ./install_plug_and_play.sh

# 3. Setup Wi-Fi (if needed)
sudo /opt/pi-plug-play/setup_wifi.sh

# 4. Start the system
sudo systemctl start pi-plug-play
```

### **3. Customer Experience (Zero Configuration)**

**Customer receives Pi device:**
1. **Connect to Wi-Fi** (if not Ethernet)
2. **Connect USB barcode scanner**
3. **Power on Pi**
4. **Scan ANY barcode** → Device registers automatically
5. **Start scanning** → Quantity updates sent to IoT Hub

**No technical knowledge required!**

## Cross-Network Discovery Solution

### **How Pi Finds Client's Server:**

```python
server_candidates = [
    "https://iot.caleffionline.it",    # Client's production server
    "http://iot.caleffionline.it",     # HTTP fallback
    "http://10.0.0.4:5000",           # Your current server
    "http://192.168.1.1:5000",        # Common router IPs
    "http://192.168.0.1:5000",
    "http://10.0.0.1:5000"
]
```

**Discovery process:**
1. Try each server URL
2. Check `/api/health` endpoint
3. Verify response contains `"service": "barcode_scanner_server"`
4. Use first working server

### **Barcode Registration Flow:**

```python
# Pi waits for barcode scan
barcode = scan_barcode()  # e.g., "1234567890"

# Generate unique device ID
device_id = f"pi-{barcode[-4:]}-{hardware_hash}"  # e.g., "pi-7890-a1b2c3d4"

# Register with server
registration_data = {
    "device_id": device_id,
    "registration_barcode": barcode,
    "device_type": "raspberry_pi_plug_play",
    "system_info": get_system_info()
}

# Server responds with IoT Hub connection string
response = server.register_device(registration_data)
connection_string = response["connection_string"]

# Pi connects to IoT Hub and starts working
```

## Testing Cross-Network Deployment

### **Test Scenario 1: Local Network**
```bash
# Pi on 192.168.1.18, Server on 10.0.0.4
# Should discover server automatically
sudo /opt/pi-plug-play/start_plug_play.sh
```

### **Test Scenario 2: Client's Server**
```bash
# Deploy server code to iot.caleffionline.it
# Pi should discover https://iot.caleffionline.it automatically
sudo systemctl start pi-plug-play
```

### **Test Scenario 3: Different Networks**
```bash
# Pi on customer's network, server on cloud
# Should work through internet discovery
```

## Deployment Package Creation

**Create package for client distribution:**

<function_calls>
<invoke name="run_command">
<parameter name="CommandLine">chmod +x /var/www/html/abhimanyu/barcode_scanner_clean/install_plug_and_play.sh
