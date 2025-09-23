#!/bin/bash
# Path Update Detection and Correction Script
# Automatically finds and updates any missed hardcoded paths

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

echo -e "${BLUE}🔍 Path Update Detection System${NC}"
echo -e "${BLUE}===============================${NC}"
echo "📁 Current Installation: $CURRENT_DIR"
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

# Find hardcoded paths that need updating
find_hardcoded_paths() {
    print_info "Scanning for hardcoded paths..."
    
    local found_issues=false
    
    # Common hardcoded path patterns to look for
    local patterns=(
        "/var/www/html/abhimanyu/barcode_scanner_clean"
        "/home/gt39112"
        "/usr/local/bin/barcode_scanner"
        "/opt/barcode_scanner"
    )
    
    # Files to check
    local files_to_check=(
        "*.py"
        "*.sh" 
        "*.service"
        "*.json"
        "*.conf"
        "*.cfg"
    )
    
    echo "🔍 Checking for hardcoded paths..."
    
    for pattern in "${patterns[@]}"; do
        print_info "Searching for: $pattern"
        
        for file_pattern in "${files_to_check[@]}"; do
            if find "$CURRENT_DIR" -name "$file_pattern" -type f -exec grep -l "$pattern" {} \; 2>/dev/null | head -5; then
                found_issues=true
                print_warning "Found hardcoded path '$pattern' in files above"
            fi
        done
    done
    
    # Check for user-specific paths
    print_info "Checking for user-specific paths..."
    if find "$CURRENT_DIR" -name "*.py" -o -name "*.sh" -o -name "*.service" | xargs grep -l "/home/[a-zA-Z0-9_-]*" 2>/dev/null; then
        found_issues=true
        print_warning "Found user-specific home directory paths"
    fi
    
    if [[ "$found_issues" == "false" ]]; then
        print_status "No hardcoded paths found"
        return 0
    else
        return 1
    fi
}

# Fix common hardcoded paths
fix_hardcoded_paths() {
    print_info "Fixing hardcoded paths..."
    
    local current_user="$(whoami)"
    local current_home="$(eval echo ~$current_user)"
    
    # Fix start_scanner_service.sh if it has hardcoded paths
    if [[ -f "$CURRENT_DIR/start_scanner_service.sh" ]]; then
        print_info "Checking start_scanner_service.sh..."
        
        # Replace any hardcoded project directory
        sed -i.bak "s|PROJECT_DIR=\"/[^\"]*\"|PROJECT_DIR=\"\$(cd \"\$(dirname \"\${BASH_SOURCE[0]}\")\" && pwd)\"|g" "$CURRENT_DIR/start_scanner_service.sh"
        
        # Replace hardcoded home directory
        sed -i "s|/home/[a-zA-Z0-9_-]*|\$USER_HOME|g" "$CURRENT_DIR/start_scanner_service.sh"
        
        print_status "Updated start_scanner_service.sh"
    fi
    
    # Fix launcher.sh if it exists
    if [[ -f "$CURRENT_DIR/launcher.sh" ]]; then
        print_info "Checking launcher.sh..."
        
        sed -i.bak "s|PROJECT_DIR=\"/[^\"]*\"|PROJECT_DIR=\"\$(cd \"\$(dirname \"\${BASH_SOURCE[0]}\")\" && pwd)\"|g" "$CURRENT_DIR/launcher.sh"
        
        print_status "Updated launcher.sh"
    fi
    
    # Fix any Python files with hardcoded paths
    find "$CURRENT_DIR" -name "*.py" -type f | while read -r py_file; do
        if grep -q "/var/www/html/abhimanyu/barcode_scanner_clean\|/home/gt39112" "$py_file" 2>/dev/null; then
            print_info "Fixing Python file: $(basename "$py_file")"
            
            # Create backup
            cp "$py_file" "$py_file.bak"
            
            # Replace hardcoded paths with dynamic detection
            sed -i "s|'/var/www/html/abhimanyu/barcode_scanner_clean'|str(Path(__file__).resolve().parent)|g" "$py_file"
            sed -i "s|\"/var/www/html/abhimanyu/barcode_scanner_clean\"|str(Path(__file__).resolve().parent)|g" "$py_file"
            sed -i "s|/home/gt39112|os.path.expanduser('~')|g" "$py_file"
            
            print_status "Updated $(basename "$py_file")"
        fi
    done
    
    # Fix service file if it exists and has hardcoded paths
    if [[ -f "$CURRENT_DIR/caleffi-barcode-scanner.service" ]]; then
        if grep -q "/var/www/html/abhimanyu/barcode_scanner_clean" "$CURRENT_DIR/caleffi-barcode-scanner.service"; then
            print_info "Service file has hardcoded paths, regenerating..."
            
            # Regenerate service file using template
            if [[ -f "$CURRENT_DIR/setup_vendor.sh" ]]; then
                ./setup_vendor.sh
                print_status "Service file regenerated"
            else
                print_warning "Cannot regenerate service file - setup_vendor.sh not found"
            fi
        fi
    fi
}

# Update configuration files
update_configs() {
    print_info "Updating configuration files..."
    
    # Update update_config.json with current path
    if [[ -f "$CURRENT_DIR/update_config.json" ]]; then
        # Use Python to safely update JSON
        python3 -c "
import json
import sys
import os

config_file = '$CURRENT_DIR/update_config.json'
try:
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Update project path
    config['project_path'] = '$CURRENT_DIR'
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print('✅ Updated update_config.json')
except Exception as e:
    print(f'❌ Error updating config: {e}')
    sys.exit(1)
"
        print_status "Updated update_config.json"
    fi
}

# Verify all paths are correct
verify_paths() {
    print_info "Verifying path corrections..."
    
    local issues_found=false
    
    # Check service file paths
    if [[ -f "/etc/systemd/system/$SERVICE_NAME.service" ]]; then
        local service_working_dir=$(grep "WorkingDirectory=" "/etc/systemd/system/$SERVICE_NAME.service" | cut -d'=' -f2)
        local service_exec_start=$(grep "ExecStart=" "/etc/systemd/system/$SERVICE_NAME.service" | cut -d'=' -f2)
        
        if [[ "$service_working_dir" != "$CURRENT_DIR" ]]; then
            print_warning "Service WorkingDirectory mismatch: $service_working_dir vs $CURRENT_DIR"
            issues_found=true
        fi
        
        if [[ ! "$service_exec_start" =~ ^$CURRENT_DIR ]]; then
            print_warning "Service ExecStart path mismatch: $service_exec_start"
            issues_found=true
        fi
    fi
    
    # Test Python imports with current paths
    cd "$CURRENT_DIR"
    if PYTHONPATH="$CURRENT_DIR/src:$CURRENT_DIR/deployment_package/src" python3 -c "
try:
    from utils.usb_hid_forwarder import USBHIDForwarder
    print('✅ Python imports working with current paths')
except ImportError as e:
    print(f'❌ Import error: {e}')
    exit(1)
" 2>/dev/null; then
        print_status "Python imports verified"
    else
        print_warning "Python import issues detected"
        issues_found=true
    fi
    
    if [[ "$issues_found" == "false" ]]; then
        print_status "All paths verified successfully"
        return 0
    else
        return 1
    fi
}

# Main function
main() {
    case "${1:-check}" in
        "check")
            print_info "Checking for path issues..."
            if find_hardcoded_paths; then
                print_status "No path issues found"
            else
                print_warning "Path issues detected - run '$0 fix' to correct them"
                exit 1
            fi
            ;;
            
        "fix")
            print_info "Fixing path issues..."
            
            # Create backup (absolute path)
            backup_dir="$(realpath "$CURRENT_DIR/path_fix_backup_$(date +%Y%m%d_%H%M%S)")"
            mkdir -p "$backup_dir"
            cp -r "$CURRENT_DIR"/* "$backup_dir/" 2>/dev/null || true
            print_info "Backup created: $backup_dir"
            
            fix_hardcoded_paths
            update_configs
            
            if verify_paths; then
                print_status "All paths fixed successfully"
                
                # Restart service if it was running
                if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
                    print_info "Restarting service with updated paths..."
                    sudo systemctl daemon-reload
                    sudo systemctl restart "$SERVICE_NAME"
                    print_status "Service restarted"
                fi
            else
                print_error "Some path issues remain"
                exit 1
            fi
            ;;
            
        "verify")
            verify_paths
            ;;
            
        *)
            echo "Usage: $0 [check|fix|verify]"
            echo ""
            echo "Commands:"
            echo "  check  - Check for hardcoded path issues (default)"
            echo "  fix    - Fix detected path issues"
            echo "  verify - Verify all paths are correct"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
