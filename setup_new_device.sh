#!/bin/bash

# Barcode Scanner System - Automated Setup Script
# This script automates the installation process for new Raspberry Pi devices

set -e  # Exit on any error

echo "=========================================="
echo "  Barcode Scanner System Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    print_error "Please do not run this script as root (don't use sudo)"
    exit 1
fi

# Get current user
CURRENT_USER=$(whoami)
PROJECT_DIR="/var/www/html/$CURRENT_USER/iot-caleffi/src"

print_step "Starting setup for user: $CURRENT_USER"
print_step "Project will be installed to: $PROJECT_DIR"

# Step 1: Update system
print_step "1/8 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Step 2: Install dependencies
print_step "2/8 Installing required packages..."
sudo apt install python3-pip python3-venv git nginx libffi-dev libssl-dev -y

# Step 3: Create project directory
print_step "3/8 Creating project directory..."
sudo mkdir -p "$PROJECT_DIR"
sudo chown -R $CURRENT_USER:$CURRENT_USER "/var/www/html/$CURRENT_USER/"

# Step 4: Copy files (if source directory exists)
if [ -d "/var/www/html/abhimanyu/barcode_scanner_clean" ]; then
    print_step "4/8 Copying system files..."
    cp -r /var/www/html/abhimanyu/barcode_scanner_clean/* "$PROJECT_DIR/"
    print_status "Files copied successfully"
else
    print_warning "Source files not found. You'll need to copy the system files manually."
    print_warning "Copy all files to: $PROJECT_DIR"
    echo ""
    read -p "Press Enter when you have copied the files..."
fi

# Step 5: Set up Python environment
print_step "5/8 Setting up Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Step 6: Create configuration file
print_step "6/8 Creating configuration file..."
if [ ! -f "$PROJECT_DIR/config.json" ]; then
    cat > "$PROJECT_DIR/config.json" << EOF
{
  "iot_hub": {
    "connection_string": "REPLACE_WITH_YOUR_IOT_HUB_CONNECTION_STRING"
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
EOF
    print_warning "Configuration file created with placeholder values."
    print_warning "You MUST edit config.json with your actual IoT Hub connection string!"
fi

# Step 7: Create and install systemd service
print_step "7/8 Setting up system service..."
sudo tee /etc/systemd/system/barcode-scanner.service > /dev/null << EOF
[Unit]
Description=Commercial Barcode Scanner Web Service
After=network.target
Wants=network.target


[Service]
Type=simple
User=$CURRENT_USER
Group=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python web_app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable barcode-scanner

# Step 8: Configure Nginx
print_step "8/8 Configuring web server..."
sudo tee /etc/nginx/sites-available/barcode-scanner > /dev/null << EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Remove default nginx site and enable barcode scanner
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/barcode-scanner /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

print_status "Setup completed successfully!"
echo ""
echo "=========================================="
echo "  IMPORTANT: NEXT STEPS"
echo "=========================================="
echo ""
print_warning "1. Edit the configuration file:"
echo "   nano $PROJECT_DIR/config.json"
echo "   Replace 'REPLACE_WITH_YOUR_IOT_HUB_CONNECTION_STRING' with your actual connection string"
echo ""
print_warning "2. Start the service:"
echo "   sudo systemctl start barcode-scanner"
echo ""
print_warning "3. Check service status:"
echo "   sudo systemctl status barcode-scanner"
echo ""
print_warning "4. Access the web interface:"
echo "   http://localhost (on this device)"
echo "   http://$(hostname -I | awk '{print $1}') (from other devices)"
echo ""
echo "=========================================="
echo "  TESTING COMMANDS"
echo "=========================================="
echo ""
echo "Test health check:"
echo "curl http://localhost/health"
echo ""
echo "Generate registration token:"
echo "curl -X POST http://localhost/api/register/token"
echo ""
echo "Register device:"
echo "curl -X POST http://localhost/api/register/confirm \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"token\": \"YOUR_TOKEN\", \"device_id\": \"test-device-001\"}'"
echo ""
echo "Scan barcode:"
echo "curl -X POST http://localhost/api/scan \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"barcode\": \"1234567890123\", \"device_id\": \"test-device-001\"}'"
echo ""
echo "=========================================="
print_status "Setup script completed!"
print_warning "Don't forget to configure your IoT Hub connection string!"
echo "=========================================="
