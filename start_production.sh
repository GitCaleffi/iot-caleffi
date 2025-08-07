#!/bin/bash
# Commercial Barcode Scanner - Production Startup Script
# Ubuntu Server Deployment for 1000+ Devices

set -e

echo "🚀 Starting Commercial Barcode Scanner Production Deployment"
echo "============================================================"

# Configuration
APP_USER="barcode-scanner"
APP_DIR="/home/$APP_USER/app"
SERVICE_NAME="barcode-scanner"
NGINX_SITE="barcode-scanner"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root (use sudo)"
   exit 1
fi

# Step 1: System Update
print_status "Updating system packages..."
apt update && apt upgrade -y

# Step 2: Install Dependencies
print_status "Installing system dependencies..."
apt install -y python3 python3-pip python3-venv nginx sqlite3 git curl

# Step 3: Create Application User
print_status "Creating application user: $APP_USER"
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash $APP_USER
    usermod -aG www-data $APP_USER
    print_success "User $APP_USER created"
else
    print_warning "User $APP_USER already exists"
fi

# Step 4: Setup Application Directory
print_status "Setting up application directory..."
mkdir -p $APP_DIR
mkdir -p /var/log/barcode-scanner
chown -R $APP_USER:$APP_USER $APP_DIR
chown -R $APP_USER:$APP_USER /var/log/barcode-scanner

# Step 5: Copy Application Files
print_status "Copying application files..."
CURRENT_DIR=$(pwd)
cp -r $CURRENT_DIR/* $APP_DIR/
chown -R $APP_USER:$APP_USER $APP_DIR

# Step 6: Setup Python Environment
print_status "Setting up Python virtual environment..."
sudo -u $APP_USER bash -c "
    cd $APP_DIR
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements_production.txt
"

# Step 7: Setup Configuration
print_status "Setting up configuration..."
if [ ! -f "$APP_DIR/config.json" ]; then
    sudo -u $APP_USER cp $APP_DIR/config_template.json $APP_DIR/config.json
    print_warning "Configuration copied from template. Please edit $APP_DIR/config.json with your Azure IoT Hub details."
fi

# Step 8: Test Application
print_status "Testing application..."
sudo -u $APP_USER bash -c "
    cd $APP_DIR
    source venv/bin/activate
    python3 src/register_device.py --status
"

# Step 9: Setup Systemd Service
print_status "Setting up systemd service..."
cp $APP_DIR/barcode-scanner.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable $SERVICE_NAME

# Step 10: Setup Nginx
print_status "Setting up Nginx..."
cat > /etc/nginx/sites-available/$NGINX_SITE << EOF
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static {
        alias $APP_DIR/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
EOF

# Enable Nginx site
ln -sf /etc/nginx/sites-available/$NGINX_SITE /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
nginx -t

# Step 11: Setup Firewall
print_status "Configuring firewall..."
ufw --force enable
ufw allow ssh
ufw allow 80
ufw allow 443

# Step 12: Start Services
print_status "Starting services..."
systemctl start $SERVICE_NAME
systemctl start nginx

# Step 13: Verify Installation
print_status "Verifying installation..."
sleep 5

if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "Barcode Scanner service is running"
else
    print_error "Barcode Scanner service failed to start"
    systemctl status $SERVICE_NAME
fi

if systemctl is-active --quiet nginx; then
    print_success "Nginx is running"
else
    print_error "Nginx failed to start"
    systemctl status nginx
fi

# Step 14: Test Web Interface
print_status "Testing web interface..."
if curl -s http://localhost/health > /dev/null; then
    print_success "Web interface is responding"
else
    print_warning "Web interface may not be ready yet"
fi

# Final Status
echo ""
echo "============================================================"
print_success "🎉 Commercial Barcode Scanner Deployment Complete!"
echo "============================================================"
echo ""
echo "📋 DEPLOYMENT SUMMARY:"
echo "   • Application User: $APP_USER"
echo "   • Application Directory: $APP_DIR"
echo "   • Service Name: $SERVICE_NAME"
echo "   • Web Interface: http://$(hostname -I | awk '{print $1}')"
echo "   • Health Check: http://$(hostname -I | awk '{print $1}')/health"
echo ""
echo "🔧 MANAGEMENT COMMANDS:"
echo "   • Check Status: sudo systemctl status $SERVICE_NAME"
echo "   • View Logs: sudo journalctl -u $SERVICE_NAME -f"
echo "   • Restart Service: sudo systemctl restart $SERVICE_NAME"
echo "   • Test System: sudo -u $APP_USER $APP_DIR/venv/bin/python $APP_DIR/src/register_device.py --status"
echo ""
echo "⚠️  IMPORTANT:"
echo "   • Edit configuration: sudo nano $APP_DIR/config.json"
echo "   • Add your Azure IoT Hub connection string"
echo "   • Restart service after config changes"
echo ""
echo "🌐 ACCESS YOUR BARCODE SCANNER:"
echo "   Open browser: http://$(hostname -I | awk '{print $1}')"
echo ""
print_success "Ready for plug-and-play barcode scanning with 1000+ devices!"
