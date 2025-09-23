# Plug & Play Installation Guide - Caleffi Barcode Scanner

This guide provides complete step-by-step installation commands for deploying the Caleffi Barcode Scanner system in any vendor environment.

## 🚀 One-Command Installation

### Quick Setup (Recommended)
```bash
# 1. Navigate to your installation directory
cd project_path

# 2. Copy the barcode scanner system
cp -r /source/barcode_scanner_clean ./barcode_scanner

# 3. Navigate to installation
cd barcode_scanner

# 4. Run plug & play setup
./setup_vendor.sh

# 5. Start the service
sudo systemctl start caleffi-barcode-scanner
```

## 📋 Detailed Step-by-Step Installation

### Step 1: System Requirements
```bash
# Check Python 3 is installed
python3 --version

# Check systemd is available
systemctl --version

# Ensure you have sudo access
sudo whoami
```

### Step 2: Copy Installation Files
```bash
# Create vendor directory (replace with your path)
VENDOR_PATH="/opt/vendor/barcode_system"
sudo mkdir -p "$VENDOR_PATH"

# Copy all files
sudo cp -r /source/barcode_scanner_clean/* "$VENDOR_PATH/"

# Set ownership
sudo chown -R $(whoami):$(id -gn) "$VENDOR_PATH"

# Navigate to installation
cd "$VENDOR_PATH"
```

### Step 3: Configure System
```bash
# Make setup script executable
chmod +x setup_vendor.sh

# Run vendor configuration (handles all setup automatically)
./setup_vendor.sh
```

### Step 4: Start Service
```bash
# Start the barcode scanner service
sudo systemctl start caleffi-barcode-scanner

# Enable auto-start on boot
sudo systemctl enable caleffi-barcode-scanner

# Check service status
sudo systemctl status caleffi-barcode-scanner
```

### Step 5: Verify Installation
```bash
# Check service is running
./vendor_update.sh status

# Verify all paths are correct
./update_paths.sh verify

# View real-time logs
sudo journalctl -u caleffi-barcode-scanner -f
```

## 🔧 Custom Installation Options

### Custom Installation Directory
```bash
# Set custom installation path
export INSTALL_DIR="/custom/vendor/path"
./setup_vendor.sh
```

### Custom Service User
```bash
# Set custom service user
export SERVICE_USER="vendoruser"
./setup_vendor.sh
```

### Environment Variables
```bash
# All available environment variables
export INSTALL_DIR="/custom/path"           # Custom installation directory
export SERVICE_USER="customuser"            # Custom service user
export SERVICE_NAME="vendor-barcode"        # Custom service name (optional)

# Run setup with custom environment
./setup_vendor.sh
```

## 🛠️ Service Management Commands

### Basic Service Control
```bash
# Start service
sudo systemctl start caleffi-barcode-scanner

# Stop service
sudo systemctl stop caleffi-barcode-scanner

# Restart service
sudo systemctl restart caleffi-barcode-scanner

# Check status
sudo systemctl status caleffi-barcode-scanner

# View logs
sudo journalctl -u caleffi-barcode-scanner -f
```

### Using Helper Scripts
```bash
# Service control helper
./service_control.sh start      # Start service
./service_control.sh stop       # Stop service
./service_control.sh restart    # Restart service
./service_control.sh status     # Check status
./service_control.sh logs       # View logs
```

## 🔄 Update and Maintenance

### System Updates
```bash
# Check system status
./vendor_update.sh status

# Full system update (with backup)
./vendor_update.sh

# Rollback if needed
./vendor_update.sh rollback
```

### Path Management
```bash
# Check for path issues
./update_paths.sh check

# Fix any path problems
./update_paths.sh fix

# Verify all paths are correct
./update_paths.sh verify
```

## 📁 Directory Structure

After installation, your directory will contain:

```
barcode_scanner/
├── keyboard_scanner.py              # Main barcode scanner application
├── start_scanner_service.sh         # Service wrapper script
├── setup_vendor.sh                  # Vendor setup script
├── vendor_update.sh                 # Update system with backup/rollback
├── update_paths.sh                  # Path detection and correction
├── service_control.sh               # Service management helper
├── caleffi-barcode-scanner.service.template  # Service template
├── device_config.json               # Device configuration
├── update_config.json               # Update settings
├── src/                             # Source modules
│   ├── utils/                       # Utility modules
│   ├── api/                         # API modules
│   ├── database/                    # Database modules
│   └── iot/                         # IoT integration modules
└── deployment_package/              # Deployment modules
    └── src/
        ├── barcode_scanner_app.py   # Web application
        └── database/                # Database modules
```

## 🔍 Troubleshooting

### Service Won't Start
```bash
# Check service status
sudo systemctl status caleffi-barcode-scanner

# View detailed logs
sudo journalctl -u caleffi-barcode-scanner --no-pager

# Check file permissions
ls -la keyboard_scanner.py start_scanner_service.sh

# Reconfigure system
./setup_vendor.sh
```

### Permission Issues
```bash
# Fix ownership
sudo chown -R $(whoami):$(id -gn) /your/installation/path

# Fix script permissions
chmod +x *.sh *.py

# Reconfigure service
./setup_vendor.sh
```

### Path Issues
```bash
# Check for hardcoded paths
./update_paths.sh check

# Fix path problems
./update_paths.sh fix

# Verify corrections
./update_paths.sh verify
```

### Import Errors
```bash
# Test Python imports
cd /your/installation/path
PYTHONPATH="$PWD/src:$PWD/deployment_package/src" python3 -c "
try:
    from utils.usb_hid_forwarder import USBHIDForwarder
    print('✅ Imports working')
except ImportError as e:
    print(f'❌ Import error: {e}')
"

# If imports fail, reconfigure
./setup_vendor.sh
```

## 📊 System Health Check

### Complete System Verification
```bash
# Run all verification checks
echo "🔍 Checking service status..."
sudo systemctl is-active caleffi-barcode-scanner

echo "🔍 Checking system status..."
./vendor_update.sh status

echo "🔍 Checking paths..."
./update_paths.sh verify

echo "🔍 Checking recent logs..."
sudo journalctl -u caleffi-barcode-scanner --since "5 minutes ago" --no-pager
```

## 🎯 Quick Commands Reference

| Task | Command |
|------|---------|
| **Install** | `./setup_vendor.sh` |
| **Start Service** | `sudo systemctl start caleffi-barcode-scanner` |
| **Check Status** | `./vendor_update.sh status` |
| **View Logs** | `sudo journalctl -u caleffi-barcode-scanner -f` |
| **Update System** | `./vendor_update.sh` |
| **Fix Paths** | `./update_paths.sh fix` |
| **Service Control** | `./service_control.sh [start\|stop\|restart\|status]` |

## 🚨 Emergency Commands

### Quick Recovery
```bash
# Stop service
sudo systemctl stop caleffi-barcode-scanner

# Reconfigure everything
./setup_vendor.sh

# Start service
sudo systemctl start caleffi-barcode-scanner

# Check status
sudo systemctl status caleffi-barcode-scanner
```

### Complete Reinstall
```bash
# Stop and disable service
sudo systemctl stop caleffi-barcode-scanner
sudo systemctl disable caleffi-barcode-scanner

# Remove service file
sudo rm -f /etc/systemd/system/caleffi-barcode-scanner.service

# Reload systemd
sudo systemctl daemon-reload

# Reconfigure from scratch
./setup_vendor.sh

# Start service
sudo systemctl start caleffi-barcode-scanner
```

## ✅ Installation Success Indicators

Your installation is successful when:
- ✅ Service status shows "active (running)"
- ✅ `./vendor_update.sh status` shows all green checkmarks
- ✅ `./update_paths.sh verify` shows "All paths verified successfully"
- ✅ Logs show barcode processing and IoT Hub connections
- ✅ No error messages in `sudo journalctl -u caleffi-barcode-scanner`

## 📞 Support

If you encounter issues:
1. Run the system health check above
2. Check the troubleshooting section
3. Provide the output of `./vendor_update.sh status` when requesting support
4. Include recent logs: `sudo journalctl -u caleffi-barcode-scanner --since "1 hour ago"`

---

**🎉 Your Caleffi Barcode Scanner system is now ready for production use!**



# Install packages in the virtual environment (no --user flag needed)
pip install gradio
pip install evdev  
pip install azure-iot-device
pip install requests

# After installation, restart the service
sudo systemctl restart caleffi-barcode-scanner

# Check status
sudo systemctl status caleffi-barcode-scanner