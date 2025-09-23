#!/bin/bash
# Vendor-Agnostic Setup Script for Caleffi Barcode Scanner
# This script configures the system for any vendor environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo -e "${BLUE}🔧 Vendor-Agnostic Barcode Scanner Setup${NC}"
echo -e "${BLUE}=========================================${NC}"
echo "📁 Installation Directory: $PROJECT_DIR"
echo "👤 User: $USER"
echo "🐍 Python: $PYTHON_PATH"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Setup permissions
setup_permissions() {
    print_info "Setting up permissions..."
    
    # Ensure correct ownership
    sudo chown -R $USER:$GROUP "$PROJECT_DIR"
    
    # Make scripts executable
    chmod +x "$PROJECT_DIR"/*.sh 2>/dev/null || true
    chmod +x "$PROJECT_DIR"/*.py 2>/dev/null || true
    
    # Add user to required groups
    if grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
        sudo usermod -a -G gpio,dialout,plugdev,input $USER
        print_status "Added user to Pi-specific groups"
    else
        sudo usermod -a -G dialout,plugdev,input $USER 2>/dev/null || true
        print_status "Added user to available groups"
    fi
    
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
    
    # Use template file if available
    SERVICE_TEMPLATE="$PROJECT_DIR/$SERVICE_NAME.service.template"
    
    if [[ -f "$SERVICE_TEMPLATE" ]]; then
        print_info "Using service template: $SERVICE_TEMPLATE"
        SOURCE_FILE="$SERVICE_TEMPLATE"
    else
        print_error "Service template not found: $SERVICE_TEMPLATE"
        return 1
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
        cat > update_config.json << EOF
{
  "auto_update_enabled": true,
  "check_interval": 3600,
  "update_branch": "main",
  "backup_before_update": true,
  "restart_service_after_update": true,
  "service_name": "caleffi-barcode-scanner",
  "project_path": "$PROJECT_DIR"
}
EOF
        print_status "Created update_config.json"
    else
        # Update project path in existing config
        python3 -c "
import json
try:
    with open('update_config.json', 'r') as f:
        config = json.load(f)
    config['project_path'] = '$PROJECT_DIR'
    with open('update_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print('Updated project path in update_config.json')
except Exception as e:
    print(f'Error updating config: {e}')
"
    fi
    
    # Create device config template if not exists
    if [[ ! -f "device_config.json" ]]; then
        cat > device_config.json << EOF
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

# Test installation
test_installation() {
    print_info "Testing installation..."
    
    cd "$PROJECT_DIR"
    
    # Test service file
    if sudo systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
        print_status "Service is enabled"
    else
        print_error "Service is not enabled"
        return 1
    fi
    
    # Test if main files exist
    if [[ -f "keyboard_scanner.py" ]]; then
        print_status "Main scanner application found"
    else
        print_warning "keyboard_scanner.py not found"
    fi
    
    if [[ -f "start_scanner_service.sh" ]]; then
        print_status "Service wrapper found"
    else
        print_warning "start_scanner_service.sh not found"
    fi
    
    print_status "Installation tests completed"
}

# Main setup process
main() {
    print_info "Starting vendor setup process..."
    echo ""
    
    setup_permissions
    echo ""
    
    install_service
    echo ""
    
    setup_config
    echo ""
    
    test_installation
    echo ""
    
    print_status "Vendor setup completed successfully!"
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "1. Start service: sudo systemctl start $SERVICE_NAME"
    echo "2. Check status: sudo systemctl status $SERVICE_NAME"
    echo "3. View logs: sudo journalctl -u $SERVICE_NAME -f"
    echo "4. Service control: ./service_control.sh {start|stop|restart|status|logs}"
    echo ""
    echo -e "${GREEN}🎉 Setup Complete!${NC}"
    echo "The barcode scanner is ready for use in your vendor environment."
}

# Run setup
main "$@"
