#!/bin/bash
# Vendor-Agnostic Update Script for Caleffi Barcode Scanner
# This script can update the system regardless of installation path

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Auto-detect current installation (absolute path)
CURRENT_DIR="$(realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
SERVICE_NAME="caleffi-barcode-scanner"
USER="$(whoami)"
BACKUP_DIR="$(realpath "$CURRENT_DIR/backup_$(date +%Y%m%d_%H%M%S)")"

echo -e "${BLUE}🔄 Vendor-Agnostic Update System${NC}"
echo -e "${BLUE}================================${NC}"
echo "📁 Current Installation: $CURRENT_DIR"
echo "👤 User: $USER"
echo "📦 Backup Location: $BACKUP_DIR"
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

# Detect current service installation
detect_service() {
    print_info "Detecting current service installation..."
    
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        SERVICE_ACTIVE=true
        print_info "Service is currently running"
    else
        SERVICE_ACTIVE=false
        print_info "Service is not running"
    fi
    
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        SERVICE_ENABLED=true
        print_info "Service is enabled"
    else
        SERVICE_ENABLED=false
        print_info "Service is not enabled"
    fi
    
    # Get current service file path (absolute)
    SERVICE_FILE="$(realpath "/etc/systemd/system/$SERVICE_NAME.service")"
    if [[ -f "$SERVICE_FILE" ]]; then
        CURRENT_SERVICE_PATH=$(grep "WorkingDirectory=" "$SERVICE_FILE" | cut -d'=' -f2)
        EXEC_START_LINE=$(grep "ExecStart=" "$SERVICE_FILE" | cut -d'=' -f2)
        CURRENT_EXEC_PATH=$(dirname "$EXEC_START_LINE")
        print_info "Service WorkingDirectory: $CURRENT_SERVICE_PATH"
        print_info "Service ExecStart path: $CURRENT_EXEC_PATH"
    else
        print_warning "Service file not found"
        CURRENT_SERVICE_PATH=""
        CURRENT_EXEC_PATH=""
    fi
}

# Create backup
create_backup() {
    print_info "Creating backup..."
    
    mkdir -p "$BACKUP_DIR"
    
    # Backup current installation (using absolute paths)
    cp -r "$CURRENT_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
    
    # Backup service file if exists
    if [[ -f "/etc/systemd/system/$SERVICE_NAME.service" ]]; then
        sudo cp "/etc/systemd/system/$SERVICE_NAME.service" "$BACKUP_DIR/service_backup.service"
    fi
    
    # Backup device config
    if [[ -f "$CURRENT_DIR/device_config.json" ]]; then
        cp "$CURRENT_DIR/device_config.json" "$BACKUP_DIR/device_config_backup.json"
    fi
    
    print_status "Backup created at: $BACKUP_DIR"
}

# Stop service safely
stop_service() {
    if [[ "$SERVICE_ACTIVE" == "true" ]]; then
        print_info "Stopping service..."
        sudo systemctl stop "$SERVICE_NAME"
        print_status "Service stopped"
    fi
}

# Update from source (Git or manual)
update_source() {
    print_info "Updating source code..."
    
    cd "$CURRENT_DIR"
    
    # Check if this is a git repository
    if [[ -d ".git" ]]; then
        print_info "Git repository detected, pulling latest changes..."
        git fetch origin
        git pull origin main || git pull origin master
        print_status "Git update completed"
    else
        print_warning "Not a git repository"
        print_info "For manual updates:"
        echo "1. Download new version to temporary location"
        echo "2. Copy new files over current installation"
        echo "3. Run this script again to reconfigure"
        
        read -p "Have you manually updated the files? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Update cancelled"
            exit 1
        fi
    fi
}

# Preserve important configurations
preserve_configs() {
    print_info "Preserving configurations..."
    
    # Preserve device config if backup exists
    if [[ -f "$BACKUP_DIR/device_config_backup.json" ]]; then
        cp "$BACKUP_DIR/device_config_backup.json" "$CURRENT_DIR/device_config.json"
        print_status "Device configuration preserved"
    fi
    
    # Preserve any custom configurations
    for config_file in "update_config.json" "config.json" "barcode_device_mapping.db"; do
        if [[ -f "$BACKUP_DIR/$config_file" ]]; then
            cp "$BACKUP_DIR/$config_file" "$CURRENT_DIR/"
            print_status "Preserved $config_file"
        fi
    done
}

# Reconfigure for current environment
reconfigure_system() {
    print_info "Reconfiguring system for current environment..."
    
    cd "$CURRENT_DIR"
    
    # Run vendor setup to reconfigure paths
    if [[ -f "setup_vendor.sh" ]]; then
        chmod +x setup_vendor.sh
        ./setup_vendor.sh
        print_status "System reconfigured"
    else
        print_warning "setup_vendor.sh not found, manual reconfiguration needed"
        
        # Manual reconfiguration
        print_info "Performing manual reconfiguration..."
        
        # Update service file
        if [[ -f "caleffi-barcode-scanner.service.template" ]]; then
            PYTHON_PATH="$(which python3)"
            HOME_DIR="$(eval echo ~$USER)"
            GROUP="$(id -gn)"
            
            sed -e "s|{{PROJECT_DIR}}|$CURRENT_DIR|g" \
                -e "s|{{USER}}|$USER|g" \
                -e "s|{{GROUP}}|$GROUP|g" \
                -e "s|{{PYTHON_PATH}}|$PYTHON_PATH|g" \
                -e "s|{{HOME_DIR}}|$HOME_DIR|g" \
                "caleffi-barcode-scanner.service.template" > "caleffi-barcode-scanner.service"
            
            # Install updated service
            sudo cp "caleffi-barcode-scanner.service" "/etc/systemd/system/"
            sudo systemctl daemon-reload
            
            print_status "Service reconfigured manually"
        fi
        
        # Set permissions
        chmod +x *.sh *.py 2>/dev/null || true
        print_status "Permissions updated"
    fi
}

# Restart service
restart_service() {
    if [[ "$SERVICE_ENABLED" == "true" ]]; then
        print_info "Restarting service..."
        sudo systemctl daemon-reload
        sudo systemctl start "$SERVICE_NAME"
        
        # Wait a moment and check status
        sleep 2
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_status "Service restarted successfully"
        else
            print_error "Service failed to start"
            print_info "Check logs: sudo journalctl -u $SERVICE_NAME --no-pager"
            return 1
        fi
    else
        print_info "Service was not enabled, skipping restart"
    fi
}

# Verify update
verify_update() {
    print_info "Verifying update..."
    
    # Check if service is running
    if [[ "$SERVICE_ENABLED" == "true" ]]; then
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            print_status "Service is running"
        else
            print_warning "Service is not running"
        fi
    fi
    
    # Check if files are in place
    local required_files=("keyboard_scanner.py" "start_scanner_service.sh")
    for file in "${required_files[@]}"; do
        if [[ -f "$CURRENT_DIR/$file" ]]; then
            print_status "$file is present"
        else
            print_error "$file is missing"
        fi
    done
    
    # Test import with proper PYTHONPATH
    cd "$CURRENT_DIR"
    if PYTHONPATH="$CURRENT_DIR/src:$CURRENT_DIR/deployment_package/src" python3 -c "
try:
    from utils.usb_hid_forwarder import USBHIDForwarder
    print('✅ Python modules working')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
" 2>/dev/null; then
        print_status "Python modules test passed"
    else
        print_warning "Python modules test failed"
    fi
}

# Cleanup old backups (keep last 5)
cleanup_backups() {
    print_info "Cleaning up old backups..."
    
    local backup_base_dir="$(dirname "$BACKUP_DIR")"
    local backup_count=$(find "$backup_base_dir" -maxdepth 1 -name "backup_*" -type d | wc -l)
    
    if [[ $backup_count -gt 5 ]]; then
        find "$backup_base_dir" -maxdepth 1 -name "backup_*" -type d | sort | head -n $((backup_count - 5)) | xargs rm -rf
        print_status "Old backups cleaned up"
    else
        print_info "No cleanup needed (${backup_count} backups)"
    fi
}

# Rollback function
rollback() {
    print_error "Rolling back to previous version..."
    
    if [[ -d "$BACKUP_DIR" ]]; then
        # Stop service
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        
        # Restore files
        cp -r "$BACKUP_DIR"/* "$CURRENT_DIR/"
        
        # Restore service file
        if [[ -f "$BACKUP_DIR/service_backup.service" ]]; then
            sudo cp "$BACKUP_DIR/service_backup.service" "/etc/systemd/system/$SERVICE_NAME.service"
            sudo systemctl daemon-reload
        fi
        
        # Restart service
        if [[ "$SERVICE_ENABLED" == "true" ]]; then
            sudo systemctl start "$SERVICE_NAME"
        fi
        
        print_status "Rollback completed"
    else
        print_error "No backup found for rollback"
        exit 1
    fi
}

# Main update process
main() {
    case "${1:-update}" in
        "update")
            print_info "Starting update process..."
            
            detect_service
            create_backup
            
            # Trap for rollback on error
            trap 'print_error "Update failed, rolling back..."; rollback' ERR
            
            stop_service
            update_source
            preserve_configs
            reconfigure_system
            restart_service
            verify_update
            cleanup_backups
            
            # Remove trap
            trap - ERR
            
            echo ""
            print_status "Update completed successfully!"
            echo ""
            print_info "📋 Update Summary:"
            echo "• Installation path: $CURRENT_DIR"
            echo "• Backup location: $BACKUP_DIR"
            echo "• Service status: $(systemctl is-active $SERVICE_NAME 2>/dev/null || echo 'inactive')"
            echo ""
            print_info "📝 Next steps:"
            echo "• Check logs: sudo journalctl -u $SERVICE_NAME -f"
            echo "• Test scanning: Check device functionality"
            echo "• Remove backup: rm -rf $BACKUP_DIR (if everything works)"
            ;;
            
        "rollback")
            rollback
            ;;
            
        "status")
            detect_service
            verify_update
            ;;
            
        *)
            echo "Usage: $0 [update|rollback|status]"
            echo ""
            echo "Commands:"
            echo "  update   - Update system (default)"
            echo "  rollback - Rollback to previous version"
            echo "  status   - Check current status"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
