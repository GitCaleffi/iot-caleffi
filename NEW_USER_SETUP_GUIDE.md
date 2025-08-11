# Complete Setup Guide for New Users
## Barcode Scanner System Deployment on Raspberry Pi

This guide will help you set up the complete barcode scanner system on a new Raspberry Pi device. **No coding experience required!**

## 📋 What You Need

### Hardware Requirements
- **Raspberry Pi 4** (recommended) or Raspberry Pi 3B+
- **MicroSD Card** (32GB or larger, Class 10)
- **USB Barcode Scanner** (any standard USB barcode scanner)
- **Internet Connection** (Wi-Fi or Ethernet)
- **Power Supply** for Raspberry Pi
- **Monitor, Keyboard, Mouse** (for initial setup only)

### Accounts You'll Need
- **Azure IoT Hub Account** (your IT admin will provide connection details)
- **API Access** (your IT admin will provide API endpoints)

---

## 🚀 Step-by-Step Installation

### Step 1: Prepare Your Raspberry Pi

1. **Download Raspberry Pi Imager**
   - Go to https://www.raspberrypi.org/software/
   - Download and install Raspberry Pi Imager on your computer

2. **Flash Raspberry Pi OS**
   - Insert your MicroSD card into your computer
   - Open Raspberry Pi Imager
   - Choose "Raspberry Pi OS (64-bit)" 
   - Select your SD card
   - Click "Write" and wait for completion (takes 5-10 minutes)

3. **Initial Setup**
   - Insert SD card into Raspberry Pi
   - Connect monitor, keyboard, mouse, and power
   - Follow the setup wizard (choose your country, create user account, connect to Wi-Fi)
   - **Important**: Enable SSH in Preferences > Raspberry Pi Configuration > Interfaces
   - Update the system: Open Terminal and run: `sudo apt update && sudo apt upgrade -y`

### Step 2: Install Required Software

Open Terminal (black icon in taskbar) and copy-paste these commands one by one:

```bash
# Install Python and web server
sudo apt install python3-pip python3-venv git nginx -y

# Install system dependencies
sudo apt install libffi-dev libssl-dev -y
```

### Step 3: Download the Barcode Scanner System

```bash
# Go to the web directory
cd /var/www/html

# Create your project folder (replace 'pi' with your username if different)
sudo mkdir -p /var/www/html/pi/barcode_scanner_clean

# Give yourself permission to use this folder
sudo chown -R $USER:$USER /var/www/html/pi/

# Copy the barcode scanner files here
# (Your IT administrator will provide you with the files to copy)
```

### Step 4: Set Up the Python Environment

```bash
# Go to your project folder
cd /var/www/html/pi/barcode_scanner_clean

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install required Python packages
pip install -r requirements.txt
```

### Step 5: Configure Your System

1. **Create your configuration file**
   ```bash
   nano config.json
   ```

2. **Add your configuration** (your IT admin will provide the actual values):
   ```json
   {
     "iot_hub": {
       "connection_string": "HostName=YourIoTHub.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=YOUR_ACTUAL_KEY_HERE"
     },
     "api": {
       "base_url": "https://api2.caleffionline.it/api/v1",
       "timeout": 30
     },
     "web_server": {
       "host": "0.0.0.0",
       "port": 5000,
       "debug": false
     },
     "database": {
       "path": "barcode_scans.db"
     }
   }
   ```
   
   **To save and exit**: Press `Ctrl+X`, then `Y`, then `Enter`

### Step 6: Set Up the System Service (Auto-Start)

1. **Create the service file**
   ```bash
   sudo nano /etc/systemd/system/barcode-scanner.service
   ```

2. **Add this configuration** (replace 'pi' with your actual username):
   ```ini
   [Unit]
   Description=Commercial Barcode Scanner Web Service
   After=network.target
   Wants=network.target

   [Service]
   Type=simple
   User=pi
   Group=pi
   WorkingDirectory=/var/www/html/pi/barcode_scanner_clean
   Environment=PATH=/var/www/html/pi/barcode_scanner_clean/venv/bin
   ExecStart=/var/www/html/pi/barcode_scanner_clean/venv/bin/python web_app.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable barcode-scanner
   sudo systemctl start barcode-scanner
   ```

### Step 7: Set Up the Web Server (Nginx)

1. **Create nginx configuration**
   ```bash
   sudo nano /etc/nginx/sites-available/barcode-scanner
   ```

2. **Add this configuration**:
   ```nginx
   server {
       listen 80;
       server_name localhost;

       location / {
           proxy_pass http://127.0.0.1:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

3. **Enable the site**
   ```bash
   sudo ln -s /etc/nginx/sites-available/barcode-scanner /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

---

## ✅ Testing Your Setup

### 1. Check if Everything is Running
```bash
# Check if your service is running
sudo systemctl status barcode-scanner

# Should show "Active: active (running)"
```

### 2. Test the Web Interface
- Open a web browser on your Raspberry Pi
- Go to `http://localhost`
- You should see the barcode scanner interface

### 3. Test from Another Computer
- Find your Raspberry Pi's IP address: `hostname -I`
- On another computer on the same network, go to `http://[PI-IP-ADDRESS]`

### 4. Test the System Functions

**Generate a registration token:**
```bash
curl -X POST http://localhost/api/register/token
```
You should get a response with a token.

**Register a test device:**
```bash
curl -X POST http://localhost/api/register/confirm \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_TOKEN_FROM_ABOVE", "device_id": "test-device-001"}'
```

**Test barcode scanning:**
```bash
curl -X POST http://localhost/api/scan \
  -H "Content-Type: application/json" \
  -d '{"barcode": "1234567890123", "device_id": "test-device-001"}'
```

---

## 🎯 How to Use the System (For End Users)

### First Time Setup
1. **Open your web browser**
2. **Go to** `http://[raspberry-pi-ip-address]`
3. **Click "Generate Registration Token"**
4. **Enter a device name** (like "warehouse-scanner-01")
5. **Click "Confirm Registration"**
6. **Your device is now ready!**

### Daily Usage
1. **Connect your USB barcode scanner** to the Raspberry Pi
2. **Open the web interface** in your browser
3. **Scan barcodes** - they will automatically appear and be sent to the cloud
4. **View your scan history** on the web interface

---

## 🔧 Troubleshooting

### Common Problems and Solutions

**Problem: Web interface won't load**
```bash
# Check if the service is running
sudo systemctl status barcode-scanner

# If not running, start it
sudo systemctl start barcode-scanner

# Check nginx
sudo systemctl status nginx
```

**Problem: Barcode scanner not working**
- Unplug and reconnect the USB scanner
- Check if it's detected: `lsusb` (should show your scanner)
- Test in a text editor - scan should type numbers

**Problem: Can't connect to cloud/IoT Hub**
- Check your internet connection: `ping google.com`
- Verify your config.json has the correct connection string
- Contact your IT administrator

**Problem: Service won't start**
```bash
# Check the logs to see what's wrong
sudo journalctl -u barcode-scanner -n 20

# Common fix: reinstall Python packages
cd /var/www/html/pi/barcode_scanner_clean
source venv/bin/activate
pip install -r requirements.txt
```

### Getting Help
If you're stuck:
1. **Check the logs**: `sudo journalctl -u barcode-scanner -n 50`
2. **Take a screenshot** of any error messages
3. **Contact your IT administrator** with:
   - What you were trying to do
   - What error message you saw
   - The log output from the command above

---

## 📱 Quick Reference for Daily Users

### Web Interface Quick Guide
- **Home Page**: Shows current status and scan interface
- **Generate Token**: For registering new devices
- **Device Registration**: One-time setup for each scanner
- **Scan Barcode**: Main interface for scanning
- **Statistics**: View your scanning history and stats

### Useful URLs (bookmark these!)
- **Main Interface**: `http://[pi-ip]/`
- **Health Check**: `http://[pi-ip]/health`
- **Statistics**: `http://[pi-ip]/api/stats`

---

## 🔄 Maintenance

### Weekly Checks
```bash
# Check system status
sudo systemctl status barcode-scanner nginx

# Check disk space
df -h

# View recent activity
sudo journalctl -u barcode-scanner --since "24 hours ago"
```

### Monthly Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
cd /var/www/html/pi/barcode_scanner_clean
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Restart service after updates
sudo systemctl restart barcode-scanner
```

### Backup Important Files
Make copies of these files:
- `/var/www/html/pi/barcode_scanner_clean/config.json`
- `/var/www/html/pi/barcode_scanner_clean/barcode_scans.db`
- `/etc/systemd/system/barcode-scanner.service`

---

## 🎉 You're All Set!

Your barcode scanner system is now ready to use. Here's what you can do:

✅ **Scan barcodes** with any USB barcode scanner  
✅ **View data in real-time** through the web interface  
✅ **Automatically sync** to the cloud (Azure IoT Hub)  
✅ **Track statistics** and scan history  
✅ **Register multiple devices** for different locations  

### Support Contacts
- **Technical Issues**: Your IT Administrator
- **User Questions**: Check this guide first, then contact support
- **Hardware Problems**: Check connections, restart Raspberry Pi

---

## 📞 Emergency Troubleshooting

If nothing works:

1. **Restart everything**:
   ```bash
   sudo systemctl restart barcode-scanner
   sudo systemctl restart nginx
   ```

2. **Reboot the Raspberry Pi**:
   ```bash
   sudo reboot
   ```

3. **Check if files are in the right place**:
   ```bash
   ls -la /var/www/html/pi/barcode_scanner_clean/
   ```

4. **Run the application manually to see errors**:
   ```bash
   cd /var/www/html/pi/barcode_scanner_clean
   source venv/bin/activate
   python web_app.py
   ```

Remember: When in doubt, contact your IT administrator with specific error messages!
