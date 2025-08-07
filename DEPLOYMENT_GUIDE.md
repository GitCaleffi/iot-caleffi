# Commercial Barcode Scanner - Ubuntu Server Deployment Guide

## 🚀 Production Deployment for 1000+ Devices

This guide will help you deploy the Commercial Barcode Scanner System on an Ubuntu server for plug-and-play access via web interface.

---

## 📋 Prerequisites

### System Requirements
- **Ubuntu Server 20.04 LTS or later**
- **Python 3.8+**
- **4GB RAM minimum (8GB recommended for 1000+ devices)**
- **20GB disk space**
- **Internet connection for Azure IoT Hub**

### Required Services
- **Nginx** (web server)
- **Systemd** (service management)
- **SQLite** (local database)

---

## 🛠️ Installation Steps

### Step 1: System Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nginx sqlite3 git

# Create application user
sudo useradd -m -s /bin/bash barcode-scanner
sudo usermod -aG www-data barcode-scanner
```

### Step 2: Application Setup

```bash
# Switch to application user
sudo su - barcode-scanner

# Create application directory
mkdir -p /home/barcode-scanner/app
cd /home/barcode-scanner/app

# Copy your application files here
# (Copy the entire barcode_scanner_clean directory)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Step 3: Configuration

```bash
# Create production configuration
cp config_template.json config.json

# Edit configuration with your Azure IoT Hub details
nano config.json
```

**config.json example:**
```json
{
  "iot_hub": {
    "connection_string": "HostName=YourIoTHub.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=YourKey",
    "deviceId": "auto-generated-from-barcode"
  },
  "web_server": {
    "host": "0.0.0.0",
    "port": 5000,
    "debug": false
  },
  "commercial_deployment": {
    "auto_registration": true,
    "plug_and_play": true,
    "max_devices": 10000,
    "batch_processing": true
  }
}
```

### Step 4: Database Setup

```bash
# Create database directories
mkdir -p /home/barcode-scanner/data
mkdir -p /var/log/barcode-scanner

# Set permissions
sudo chown -R barcode-scanner:barcode-scanner /home/barcode-scanner/
sudo chown -R barcode-scanner:barcode-scanner /var/log/barcode-scanner/
```

---

## 🌐 Web Interface Setup

### Step 1: Create Flask Web Application

The system includes a web interface at `web_app.py` that provides:
- **Barcode scanning via web form**
- **Real-time statistics dashboard**
- **Device registration status**
- **System health monitoring**

### Step 2: Create Systemd Service

```bash
# Create service file
sudo nano /etc/systemd/system/barcode-scanner.service
```

**Service file content:**
```ini
[Unit]
Description=Commercial Barcode Scanner Web Service
After=network.target

[Service]
Type=simple
User=barcode-scanner
Group=barcode-scanner
WorkingDirectory=/home/barcode-scanner/app
Environment=PATH=/home/barcode-scanner/app/venv/bin
ExecStart=/home/barcode-scanner/app/venv/bin/python web_app.py
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=barcode-scanner

[Install]
WantedBy=multi-user.target
```

### Step 3: Configure Nginx

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/barcode-scanner
```

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or IP

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static {
        alias /home/barcode-scanner/app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
```

### Step 4: Enable Services

```bash
# Enable Nginx site
sudo ln -s /etc/nginx/sites-available/barcode-scanner /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site

# Test Nginx configuration
sudo nginx -t

# Start services
sudo systemctl daemon-reload
sudo systemctl enable barcode-scanner
sudo systemctl enable nginx

sudo systemctl start barcode-scanner
sudo systemctl start nginx
```

---

## 🔧 Main Application Files

### Primary Entry Points

1. **Web Interface (Recommended for Production):**
   ```bash
   python3 web_app.py
   ```
   - **URL:** `http://your-server-ip/`
   - **Features:** Web-based barcode scanning, dashboard, statistics
   - **Best for:** End-user access, plug-and-play operation

2. **Command Line Interface:**
   ```bash
   python3 src/barcode_main.py
   ```
   - **Features:** Interactive terminal-based scanning
   - **Best for:** Direct server access, debugging

3. **Registration Management:**
   ```bash
   python3 src/register_device.py --commercial-test
   python3 src/register_device.py --status
   python3 src/register_device.py --barcode 1234567890123
   ```

---

## 📊 Monitoring and Management

### System Status Commands

```bash
# Check service status
sudo systemctl status barcode-scanner
sudo systemctl status nginx

# View logs
sudo journalctl -u barcode-scanner -f
sudo tail -f /var/log/barcode-scanner/app.log

# Check system statistics
python3 src/register_device.py --status
```

### Health Monitoring

The web application provides these endpoints:
- `GET /health` - System health check
- `GET /api/stats` - System statistics JSON
- `GET /api/devices` - Registered devices list

---

## 🔒 Security Configuration

### Firewall Setup

```bash
# Enable UFW firewall
sudo ufw enable

# Allow SSH, HTTP, and HTTPS
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443

# Check status
sudo ufw status
```

### SSL Certificate (Optional but Recommended)

```bash
# Install Certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

---

## 🚀 Production Deployment Checklist

### Before Going Live:

- [ ] **Configuration verified** - Azure IoT Hub connection string correct
- [ ] **Database permissions** - SQLite databases writable
- [ ] **Services enabled** - barcode-scanner and nginx auto-start
- [ ] **Firewall configured** - Only necessary ports open
- [ ] **SSL certificate** - HTTPS enabled (recommended)
- [ ] **Monitoring setup** - Log rotation and monitoring
- [ ] **Backup strategy** - Database backup plan

### Testing Deployment:

```bash
# Test barcode registration
python3 src/register_device.py --barcode 1234567890123

# Test web interface
curl http://localhost/health

# Test barcode scanning via API
curl -X POST http://localhost/api/scan \
  -H "Content-Type: application/json" \
  -d '{"barcode": "1234567890123"}'
```

---

## 📱 User Access Instructions

### For End Users (Plug-and-Play):

1. **Open web browser**
2. **Navigate to:** `http://your-server-ip/`
3. **Enter barcode** in the input field
4. **Click "Scan Barcode"**
5. **System automatically:**
   - Generates device ID from barcode
   - Registers device with Azure IoT Hub
   - Sends data to cloud
   - Shows confirmation

### No Technical Knowledge Required:
- ✅ No device ID input needed
- ✅ No configuration required
- ✅ Automatic registration
- ✅ Real-time feedback
- ✅ Works on any device with web browser

---

## 🔧 Troubleshooting

### Common Issues:

1. **Service won't start:**
   ```bash
   sudo journalctl -u barcode-scanner -n 50
   ```

2. **Database permission errors:**
   ```bash
   sudo chown -R barcode-scanner:barcode-scanner /home/barcode-scanner/
   ```

3. **Azure IoT Hub connection issues:**
   - Verify connection string in config.json
   - Check internet connectivity
   - Verify Azure IoT Hub permissions

4. **Web interface not accessible:**
   ```bash
   sudo systemctl status nginx
   sudo nginx -t
   ```

---

## 📈 Scaling for 1000+ Devices

### Performance Optimization:

1. **Database optimization:**
   - Regular SQLite VACUUM operations
   - Index optimization for large datasets

2. **Connection pooling:**
   - Azure IoT Hub connection reuse
   - Batch processing for multiple scans

3. **Monitoring:**
   - Set up log rotation
   - Monitor disk space usage
   - Track Azure IoT Hub quotas

### Load Testing:

```bash
# Test with multiple concurrent barcodes
python3 src/register_device.py --batch-file large_barcode_list.txt
```

---

## 🎯 Production Ready Features

✅ **Plug-and-Play Operation** - No manual device ID input
✅ **Commercial Scale** - Supports 1000+ devices  
✅ **Web Interface** - User-friendly browser access
✅ **Automatic Registration** - Azure IoT Hub integration
✅ **Real-time Monitoring** - Statistics and health checks
✅ **Robust Error Handling** - Retry mechanisms and logging
✅ **Production Security** - Firewall, SSL, user isolation
✅ **Service Management** - Systemd integration for reliability

---

## 📞 Support

For deployment issues or questions:
1. Check logs: `sudo journalctl -u barcode-scanner -f`
2. Verify configuration: `python3 src/register_device.py --status`
3. Test connectivity: `python3 src/register_device.py --commercial-test`

**Your Commercial Barcode Scanner System is now ready for production deployment!** 🚀
