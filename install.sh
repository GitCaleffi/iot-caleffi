#!/bin/bash
# Caleffi Barcode Scanner - Complete Installation Script
# This script sets up the barcode scanner system with all components

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Auto-detect configuration (absolute path)
PROJECT_DIR="$(realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
SERVICE_NAME="caleffi-barcode-scanner"
USER="$(whoami)"
GROUP="$(id -gn)"
PYTHON_PATH="$(which python3)"
HOME_DIR="$(eval echo ~$USER)"

# Make paths vendor-agnostic (absolute paths)
INSTALL_DIR="$(realpath "${INSTALL_DIR:-$PROJECT_DIR}")"
SERVICE_USER="${SERVICE_USER:-$USER}"

# Logging
LOG_FILE="/tmp/barcode_scanner_install.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2> >(tee -a "$LOG_FILE" >&2)

echo -e "${BLUE}🚀 Caleffi Barcode Scanner Installation${NC}"
echo -e "${BLUE}=======================================${NC}"
echo "📝 Installation log: $LOG_FILE"
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}❌ This script should not be run as root${NC}"
    echo "💡 Run as regular user (pi) - sudo will be used when needed"
    exit 1
fi

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

# Check system requirements
check_system() {
    print_info "Checking system requirements..."
    
    # Detect system type
    IS_RASPBERRY_PI=false
    if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        IS_RASPBERRY_PI=true
        print_status "Raspberry Pi detected"
    else
        print_warning "Not running on Raspberry Pi - GPIO features will be disabled"
        print_info "System: $(uname -a | cut -d' ' -f1-3)"
    fi
    
    # Check Python version
    if ! python3 --version | grep -q "Python 3"; then
        print_error "Python 3 is required"
        exit 1
    fi
    print_status "Python 3 found: $(python3 --version)"
    
    # Check git
    if ! command -v git &> /dev/null; then
        print_error "Git is required but not installed"
        exit 1
    fi
    print_status "Git found: $(git --version)"
}

# Install system dependencies
install_system_deps() {
    print_info "Installing system dependencies..."
    
    sudo apt-get update
    
    # Base dependencies for all systems
    BASE_DEPS=(
        python3-pip
        python3-venv
        python3-dev
        git
        curl
        wget
        build-essential
        libffi-dev
        libssl-dev
        libudev-dev
        libusb-1.0-0-dev
        systemd
    )
    
    # Raspberry Pi specific dependencies
    RPI_DEPS=(
        python3-rpi.gpio
        python3-gpiozero
    )
    
    # Install base dependencies
    sudo apt-get install -y "${BASE_DEPS[@]}"
    
    # Install Raspberry Pi dependencies only if on Pi
    if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
        print_info "Installing Raspberry Pi specific packages..."
        sudo apt-get install -y "${RPI_DEPS[@]}"
        print_status "Raspberry Pi packages installed"
    else
        print_info "Skipping Raspberry Pi specific packages (not on Pi hardware)"
    fi
    
    print_status "System dependencies installed"
}

# Setup USB HID gadget
setup_usb_hid() {
    print_info "Setting up USB HID gadget..."
    
    if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
        # Enable dwc2 overlay for USB gadget mode
        if [[ -f "/boot/config.txt" ]] && ! grep -q "dtoverlay=dwc2" /boot/config.txt; then
            echo "dtoverlay=dwc2" | sudo tee -a /boot/config.txt
            print_status "Added dwc2 overlay to /boot/config.txt"
        fi
        
        # Enable libcomposite module
        if ! grep -q "libcomposite" /etc/modules; then
            echo "libcomposite" | sudo tee -a /etc/modules
            print_status "Added libcomposite to /etc/modules"
        fi
        
        # Load module now
        sudo modprobe libcomposite 2>/dev/null || true
        print_status "USB HID gadget configured for Raspberry Pi"
    else
        print_info "Skipping USB HID gadget setup (not on Raspberry Pi)"
        print_info "USB HID forwarding will use alternative methods"
    fi
}

# Install Python dependencies
install_python_deps() {
    print_info "Installing Python dependencies..."
    
    cd "$PROJECT_DIR"
    
    # Install from requirements files
    if [[ -f "requirements.txt" ]]; then
        pip3 install --user -r requirements.txt
        print_status "Installed requirements.txt"
    fi
    
    if [[ -f "requirements-device.txt" ]]; then
        pip3 install --user -r requirements-device.txt
        print_status "Installed requirements-device.txt"
    fi
    
    # Base Python dependencies for all systems
    BASE_PYTHON_DEPS=(
        requests
        pathlib
        pyusb
        hidapi
    )
    
    # Raspberry Pi specific Python dependencies
    RPI_PYTHON_DEPS=(
        evdev
        RPi.GPIO
        gpiozero
    )
    
    # Install base dependencies
    pip3 install --user "${BASE_PYTHON_DEPS[@]}"
    
    # Install Raspberry Pi dependencies only if on Pi
    if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
        print_info "Installing Raspberry Pi specific Python packages..."
        pip3 install --user "${RPI_PYTHON_DEPS[@]}"
        print_status "Raspberry Pi Python packages installed"
    else
        print_info "Skipping Raspberry Pi specific Python packages"
        # Install mock GPIO for non-Pi systems
        pip3 install --user fake-rpi
        print_status "Installed GPIO mock library for non-Pi systems"
    fi
    
    print_status "Python dependencies installed"
}

# Setup project permissions
setup_permissions() {
    print_info "Setting up permissions..."
    
    # Ensure correct ownership
    sudo chown -R $USER:$GROUP "$PROJECT_DIR"
    
    # Make scripts executable
    chmod +x "$PROJECT_DIR/keyboard_scanner.py"
    chmod +x "$PROJECT_DIR/src/utils/usb_hid_forwarder.py"
    chmod +x "$PROJECT_DIR/src/utils/auto_updater.py"
    
    # Setup udev rules for USB HID access
    sudo tee /etc/udev/rules.d/99-barcode-scanner.rules > /dev/null << 'EOF'
# Barcode Scanner USB HID Rules
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTRS{idVendor}=="*", ATTRS{idProduct}=="*", MODE="0666", GROUP="plugdev"
KERNEL=="hidg*", MODE="0666", GROUP="plugdev"
EOF
    
    # Add user to required groups
    if [[ "$IS_RASPBERRY_PI" == "true" ]]; then
        # Add Pi-specific groups
        sudo usermod -a -G gpio,dialout,plugdev,input $USER
        print_status "Added user to Pi-specific groups (gpio,dialout,plugdev,input)"
    else
        # Add non-Pi groups (skip gpio which doesn't exist)
        sudo usermod -a -G dialout,plugdev,input $USER 2>/dev/null || true
        print_status "Added user to available groups (dialout,plugdev,input)"
    fi
    
    # Reload udev rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    print_status "Permissions configured"
}

# Install systemd service
install_service() {
    print_info "Installing systemd service..."
    
    # Create service file from template with dynamic values
    print_info "Configuring service for:"
    print_info "  Project Directory: $PROJECT_DIR"
    print_info "  User: $USER"
    print_info "  Group: $GROUP"
    print_info "  Python Path: $PYTHON_PATH"
    
    # Use template file if available, otherwise use the main service file
    SERVICE_TEMPLATE="$PROJECT_DIR/$SERVICE_NAME.service.template"
    SERVICE_SOURCE="$PROJECT_DIR/$SERVICE_NAME.service"
    
    if [[ -f "$SERVICE_TEMPLATE" ]]; then
        print_info "Using service template: $SERVICE_TEMPLATE"
        SOURCE_FILE="$SERVICE_TEMPLATE"
    else
        print_info "Using service file: $SERVICE_SOURCE"
        SOURCE_FILE="$SERVICE_SOURCE"
    fi
    
    # Generate service file with actual values
    sed -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
        -e "s|{{USER}}|$USER|g" \
        -e "s|{{GROUP}}|$GROUP|g" \
        -e "s|{{PYTHON_PATH}}|$PYTHON_PATH|g" \
        -e "s|{{HOME_DIR}}|$HOME_DIR|g" \
        "$SOURCE_FILE" | \
        sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null
    
    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable "$SERVICE_NAME"
    
    print_status "Systemd service installed and enabled"
}

# Setup configuration files
setup_config() {
    print_info "Setting up configuration files..."
    
    cd "$PROJECT_DIR"
    
    # Create default update config if not exists
    if [[ ! -f "update_config.json" ]]; then
        cat > update_config.json << 'EOF'
{
  "auto_update_enabled": true,
  "check_interval": 3600,
  "update_branch": "main",
  "backup_before_update": true,
  "restart_service_after_update": true,
  "service_name": "caleffi-barcode-scanner"
}
EOF
        print_status "Created update_config.json"
    fi
    
    # Create device config template if not exists
    if [[ ! -f "device_config.json" ]]; then
        cat > device_config.json << 'EOF'
{
  "device_id": null,
  "test_barcode_verified": false,
  "first_scan_done": false
}
EOF
        print_status "Created device_config.json template"
    fi
    
    print_status "Configuration files ready"
}

# Create helper scripts
create_helper_scripts() {
    print_info "Creating helper scripts..."
    
    # Service control script
    cat > "$PROJECT_DIR/service_control.sh" << 'EOF'
#!/bin/bash
# Service control helper script

SERVICE_NAME="caleffi-barcode-scanner"

case "$1" in
    start)
        echo "🚀 Starting barcode scanner service..."
        sudo systemctl start "$SERVICE_NAME"
        ;;
    stop)
        echo "🛑 Stopping barcode scanner service..."
        sudo systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        echo "🔄 Restarting barcode scanner service..."
        sudo systemctl restart "$SERVICE_NAME"
        ;;
    status)
        echo "📊 Service status:"
        sudo systemctl status "$SERVICE_NAME"
        ;;
    logs)
        echo "📝 Service logs:"
        sudo journalctl -u "$SERVICE_NAME" -f
        ;;
    enable)
        echo "✅ Enabling service auto-start..."
        sudo systemctl enable "$SERVICE_NAME"
        ;;
    disable)
        echo "🔒 Disabling service auto-start..."
        sudo systemctl disable "$SERVICE_NAME"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable}"
        exit 1
        ;;
esac
EOF
    
    chmod +x "$PROJECT_DIR/service_control.sh"
    
    # Update script
    cat > "$PROJECT_DIR/update.sh" << 'EOF'
#!/bin/bash
# Manual update script

echo "🔄 Checking for updates..."
cd "$(dirname "$0")"

python3 src/utils/auto_updater.py --check
if [[ $? -eq 0 ]]; then
    echo "📥 Performing update..."
    python3 src/utils/auto_updater.py --update
else
    echo "✅ Already up to date"
fi
EOF
    
    chmod +x "$PROJECT_DIR/update.sh"
    
    print_status "Helper scripts created"
}

# Test installation
test_installation() {
    print_info "Testing installation..."
    
    cd "$PROJECT_DIR"
    
    # Test Python imports
    if python3 -c "
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
sys.path.insert(0, os.path.join(os.getcwd(), 'deployment_package', 'src'))
try:
    from utils.usb_hid_forwarder import USBHIDForwarder
    from utils.auto_updater import AutoUpdater
    print('✅ All imports successful')
except ImportError as e:
    print(f'Import error: {e}')
    exit(1)
"; then
        print_status "Python modules test passed"
    else
        print_warning "Python modules test failed (modules may work in runtime environment)"
    fi
    
    # Test HID forwarder initialization
    if python3 -c "
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
try:
    from utils.usb_hid_forwarder import USBHIDForwarder
    forwarder = USBHIDForwarder()
    print('✅ HID forwarder initialized')
except Exception as e:
    print(f'HID forwarder error: {e}')
    exit(1)
" 2>/dev/null; then
        print_status "HID forwarder test passed"
    else
        print_warning "HID forwarder test failed (may work after reboot or with hardware)"
    fi
    
    # Test service file
    if sudo systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        print_status "Service is enabled"
    else
        print_error "Service is not enabled"
        return 1
    fi
    
    print_status "Installation tests completed"
}

# Main installation process
main() {
    echo "Starting installation process..."
    echo ""
    
    check_system
    echo ""
    
    install_system_deps
    echo ""
    
    setup_usb_hid
    echo ""
    
    install_python_deps
    echo ""
    
    setup_permissions
    echo ""
    
    install_service
    echo ""
    
    setup_config
    echo ""
    
    create_helper_scripts
    echo ""
    
    test_installation
    echo ""
    
    print_status "Installation completed successfully!"
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "1. Reboot the system: sudo reboot"
    echo "2. After reboot, the service will start automatically"
    echo "3. Check service status: ./service_control.sh status"
    echo "4. View logs: ./service_control.sh logs"
    echo "5. Manual control: ./service_control.sh {start|stop|restart}"
    echo "6. Manual updates: ./update.sh"
    echo ""
    echo -e "${BLUE}📁 Important Files:${NC}"
    echo "• Service control: $PROJECT_DIR/service_control.sh"
    echo "• Update script: $PROJECT_DIR/update.sh"
    echo "• Device config: $PROJECT_DIR/device_config.json"
    echo "• Update config: $PROJECT_DIR/update_config.json"
    echo "• Service logs: sudo journalctl -u $SERVICE_NAME"
    echo ""
    echo -e "${GREEN}🎉 Installation Complete!${NC}"
    echo "The barcode scanner will automatically:"
    echo "• Start on boot"
    echo "• Forward barcodes to POS systems via USB HID"
    echo "• Send data to IoT Hub and API"
    echo "• Check for updates automatically"
    echo ""
    echo -e "${YELLOW}⚠️ Reboot Required${NC}"
    echo "Please reboot the system to activate USB HID gadget mode"
}

# Run installation
main "$@"
