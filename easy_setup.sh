#!/bin/bash

# =============================================================================
# BARCODE SCANNER SYSTEM - EASY SETUP SCRIPT
# =============================================================================
# This script automatically sets up the complete barcode scanner system
# No technical knowledge required - just run this script!
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Emojis for better UX
SUCCESS="✅"
ERROR="❌"
WARNING="⚠️"
INFO="ℹ️"
ROCKET="🚀"
GEAR="⚙️"

echo -e "${BLUE}${ROCKET} BARCODE SCANNER SYSTEM - EASY SETUP${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}${SUCCESS} $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}${WARNING} $1${NC}"
}

print_error() {
    echo -e "${RED}${ERROR} $1${NC}"
}

print_info() {
    echo -e "${BLUE}${INFO} $1${NC}"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${INFO} Setup directory: $SCRIPT_DIR"

# Step 1: System Updates and Dependencies
echo ""
echo -e "${GEAR} Step 1: Installing system dependencies..."
print_info "Updating package lists..."

if command_exists apt-get; then
    sudo apt-get update -qq
    print_info "Installing essential packages..."
    sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        libffi-dev \
        build-essential \
        git \
        curl \
        wget \
        nano \
        htop \
        net-tools \
        nmap \
        mosquitto \
        mosquitto-clients \
        nginx
elif command_exists yum; then
    sudo yum update -y -q
    sudo yum install -y \
        python3 \
        python3-pip \
        python3-devel \
        libffi-devel \
        gcc \
        gcc-c++ \
        make \
        git \
        curl \
        wget \
        nano \
        htop \
        net-tools \
        nmap \
        mosquitto \
        nginx
elif command_exists dnf; then
    sudo dnf update -y -q
    sudo dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        libffi-devel \
        gcc \
        gcc-c++ \
        make \
        git \
        curl \
        wget \
        nano \
        htop \
        net-tools \
        nmap \
        mosquitto \
        nginx
else
    print_error "Unsupported package manager. Please install dependencies manually."
    exit 1
fi

print_status "System dependencies installed successfully!"

# Step 2: Python Environment Setup
echo ""
echo -e "${GEAR} Step 2: Setting up Python environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_info "Creating Python virtual environment..."
    python3 -m venv venv
    print_status "Virtual environment created!"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_info "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
if [ -f "requirements-device.txt" ]; then
    print_info "Installing Python dependencies from requirements-device.txt..."
    pip install -r requirements-device.txt
    print_status "Python dependencies installed successfully!"
else
    print_warning "requirements-device.txt not found. Installing basic dependencies..."
    pip install requests>=2.25.1 python-dotenv>=0.19.0 azure-iot-device>=2.7.1 azure-iot-hub>=2.7.0 psutil>=5.9.0 netifaces>=0.11.0 python-json-logger>=2.0.2
fi

# Step 3: Configuration Setup
echo ""
echo -e "${GEAR} Step 3: Setting up configuration..."

# Create deployment package structure if needed
mkdir -p deployment_package/src/{api,database,iot,utils}

# Check if config.json exists
if [ ! -f "deployment_package/config.json" ]; then
    print_info "Creating default configuration file..."
    cat > deployment_package/config.json << 'EOF'
{
    "iot_hub": {
        "connection_string": "YOUR_IOT_HUB_CONNECTION_STRING_HERE",
        "device_id": "barcode-scanner-device"
    },
    "api": {
        "base_url": "https://api2.caleffionline.it",
        "timeout": 30
    },
    "raspberry_pi": {
        "status": "auto",
        "ip": "auto-detect",
        "ssh": {
            "accessible": false
        },
        "force_detection": false,
        "dynamic_discovery": true,
        "remote_connectivity_monitoring": true,
        "live_server_mode": true,
        "cross_network_detection": true
    },
    "scanner": {
        "type": "usb",
        "continuous_mode": true,
        "validation": {
            "min_length": 6,
            "max_length": 20,
            "allow_alphanumeric": true
        }
    },
    "performance": {
        "fast_mode": true,
        "parallel_processing": true,
        "auto_config": true
    },
    "frontend": {
        "notification_url": "https://iot.caleffionline.it/api/registration-notification"
    },
    "mqtt": {
        "broker_host": "localhost",
        "broker_port": 1883,
        "discovery_enabled": true
    }
}
EOF
    print_status "Default configuration created!"
else
    print_info "Configuration file already exists"
fi

# Step 4: Service Setup
echo ""
echo -e "${GEAR} Step 4: Setting up system services..."

# Create systemd service file
print_info "Creating systemd service..."
sudo tee /etc/systemd/system/barcode-scanner.service > /dev/null << EOF
[Unit]
Description=Barcode Scanner Service
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$SCRIPT_DIR/deployment_package
Environment=PATH=$SCRIPT_DIR/venv/bin
ExecStart=$SCRIPT_DIR/venv/bin/python src/barcode_scanner_app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable barcode-scanner.service
print_status "Systemd service configured!"

# Step 5: MQTT Setup
echo ""
echo -e "${GEAR} Step 5: Setting up MQTT broker..."

# Start and enable mosquitto
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Create MQTT configuration
sudo tee /etc/mosquitto/conf.d/barcode-scanner.conf > /dev/null << 'EOF'
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
EOF

sudo systemctl restart mosquitto
print_status "MQTT broker configured and running!"

# Step 6: Web Interface Setup (Optional)
echo ""
echo -e "${GEAR} Step 6: Setting up web interface..."

# Create nginx configuration
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

# Enable the site
sudo ln -sf /etc/nginx/sites-available/barcode-scanner /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
print_status "Web interface configured!"

# Step 7: Permissions and Final Setup
echo ""
echo -e "${GEAR} Step 7: Setting up permissions..."

# Make scripts executable
chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
chmod +x "$SCRIPT_DIR"/deployment_package/src/*.py 2>/dev/null || true

# Add user to dialout group for USB scanner access
sudo usermod -a -G dialout $(whoami)

print_status "Permissions configured!"

# Step 8: Verification
echo ""
echo -e "${GEAR} Step 8: Verifying installation..."

# Test Python imports
print_info "Testing Python dependencies..."
if python3 -c "import requests, azure.iot.device, psutil, netifaces" 2>/dev/null; then
    print_status "Python dependencies working!"
else
    print_error "Some Python dependencies failed to import"
fi

# Test MQTT
print_info "Testing MQTT broker..."
if mosquitto_pub -h localhost -t test -m "test" 2>/dev/null; then
    print_status "MQTT broker working!"
else
    print_warning "MQTT broker test failed"
fi

# Test nginx
print_info "Testing web server..."
if curl -s http://localhost > /dev/null 2>&1; then
    print_status "Web server working!"
else
    print_warning "Web server not responding (this is normal if the app isn't running yet)"
fi

# Final Summary
echo ""
echo -e "${GREEN}${ROCKET} SETUP COMPLETE! ${ROCKET}${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
print_status "Barcode scanner system is ready to use!"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo -e "${INFO} 1. Update IoT Hub connection string in: deployment_package/config.json"
echo -e "${INFO} 2. Start the service: sudo systemctl start barcode-scanner"
echo -e "${INFO} 3. Check status: sudo systemctl status barcode-scanner"
echo -e "${INFO} 4. View logs: sudo journalctl -u barcode-scanner -f"
echo -e "${INFO} 5. Access web interface: http://localhost"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo -e "${INFO} Start service: sudo systemctl start barcode-scanner"
echo -e "${INFO} Stop service: sudo systemctl stop barcode-scanner"
echo -e "${INFO} Restart service: sudo systemctl restart barcode-scanner"
echo -e "${INFO} View logs: sudo journalctl -u barcode-scanner -f"
echo ""
print_warning "Please reboot the system or log out/in to apply group permissions!"
echo ""
echo -e "${GREEN}${SUCCESS} Setup completed successfully! Enjoy your barcode scanner system!${NC}"
