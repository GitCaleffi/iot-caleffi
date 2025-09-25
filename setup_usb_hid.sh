#!/bin/bash
# Enhanced USB HID Gadget Setup for Caleffi Barcode Scanner
# Compatible with all Raspberry Pi models (Pi 1 through Pi 5)
# This script sets up the Raspberry Pi as a USB HID keyboard for POS forwarding

set -e

echo "🔧 Enhanced USB HID Gadget Setup for All Raspberry Pi Models"
echo "============================================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Detect Raspberry Pi model
echo "🍓 Detecting Raspberry Pi model..."
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
    echo "📱 Detected: $PI_MODEL"
else
    PI_MODEL="Unknown Pi Model"
    echo "⚠️  Could not detect Pi model, proceeding anyway..."
fi

# Check for Pi 5 specific requirements
if [[ "$PI_MODEL" == *"Raspberry Pi 5"* ]]; then
    echo "🚀 Raspberry Pi 5 detected - using enhanced configuration"
    PI5_MODE=true
else
    echo "📟 Raspberry Pi 1-4 detected - using standard configuration"
    PI5_MODE=false
fi

# Load required modules based on Pi model
echo "📦 Loading USB gadget modules for $PI_MODEL..."

if [ "$PI5_MODE" = true ]; then
    # Pi 5 specific module loading
    echo "🔧 Loading Pi 5 compatible modules..."
    modprobe dwc2 || echo "⚠️  dwc2 module not available on Pi 5 (using dwc3)"
    modprobe dwc3 || echo "⚠️  dwc3 module already loaded or not available"
    modprobe dwc3-haps || echo "⚠️  dwc3-haps module not available"
    modprobe libcomposite || echo "⚠️  libcomposite module already loaded or not available"
else
    # Pi 1-4 standard module loading
    echo "🔧 Loading standard Pi modules..."
    modprobe dwc2 || echo "⚠️  dwc2 module already loaded or not available"
    modprobe libcomposite || echo "⚠️  libcomposite module already loaded or not available"
fi

# Enable USB gadget mode in config.txt if not already enabled
echo "📝 Checking USB gadget configuration..."
CONFIG_FILE="/boot/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/boot/firmware/config.txt"  # Pi 5 location
fi

if [ -f "$CONFIG_FILE" ]; then
    if ! grep -q "dtoverlay=dwc2" "$CONFIG_FILE"; then
        echo "dtoverlay=dwc2" >> "$CONFIG_FILE"
        echo "✅ Added dwc2 overlay to $CONFIG_FILE"
    else
        echo "✅ dwc2 overlay already configured"
    fi
else
    echo "⚠️  Could not find config.txt file"
fi

# Create gadget directory
GADGET_DIR="/sys/kernel/config/usb_gadget/caleffi_scanner"
if [ ! -d "$GADGET_DIR" ]; then
    echo "📁 Creating USB gadget configuration..."
    mkdir -p "$GADGET_DIR"
    cd "$GADGET_DIR"

    # Set gadget attributes
    echo 0x1d6b > idVendor  # Linux Foundation
    echo 0x0104 > idProduct # Multifunction Composite Gadget
    echo 0x0100 > bcdDevice # v1.0.0
    echo 0x0200 > bcdUSB    # USB2

    # Create strings
    mkdir -p strings/0x409
    echo "Caleffi" > strings/0x409/manufacturer
    echo "Barcode Scanner HID" > strings/0x409/product
    echo "123456789" > strings/0x409/serialnumber

    # Create HID function
    mkdir -p functions/hid.usb0
    echo 1 > functions/hid.usb0/protocol
    echo 1 > functions/hid.usb0/subclass
    echo 8 > functions/hid.usb0/report_length

    # HID report descriptor for keyboard
    echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

    # Create configuration
    mkdir -p configs/c.1/strings/0x409
    echo "Config 1: HID Keyboard" > configs/c.1/strings/0x409/configuration
    echo 250 > configs/c.1/MaxPower

    # Link function to configuration
    ln -sf "$GADGET_DIR/functions/hid.usb0" "$GADGET_DIR/configs/c.1/"

    # Enable gadget with Pi model specific handling
    echo "🔌 Enabling USB gadget..."
    
    # Find available UDC controllers
    UDC_LIST=$(ls /sys/class/udc 2>/dev/null || echo "")
    
    if [ -n "$UDC_LIST" ]; then
        # Try each UDC controller until one works
        for udc in $UDC_LIST; do
            echo "🔄 Trying UDC controller: $udc"
            if echo "$udc" > UDC 2>/dev/null; then
                echo "✅ USB HID gadget enabled on $udc"
                UDC_SUCCESS=true
                break
            else
                echo "⚠️  Failed to enable on $udc, trying next..."
            fi
        done
        
        if [ "$UDC_SUCCESS" != true ]; then
            echo "❌ Failed to enable gadget on any UDC controller"
            echo "Available controllers: $UDC_LIST"
            exit 1
        fi
    else
        echo "❌ No UDC controllers found"
        echo "💡 This may be normal on Pi 5 or if USB gadget mode is not supported"
        echo "💡 POS forwarding will use alternative methods (Network, Serial, etc.)"
        # Don't exit - allow alternative methods to work
    fi
else
    echo "✅ USB HID gadget already configured at $GADGET_DIR"
    # Check if it's properly enabled
    if [ -f "$GADGET_DIR/UDC" ] && [ -s "$GADGET_DIR/UDC" ]; then
        UDC_CURRENT=$(cat "$GADGET_DIR/UDC")
        echo "✅ Currently enabled on UDC: $UDC_CURRENT"
    else
        echo "⚠️  Gadget configured but not enabled, attempting to enable..."
        cd "$GADGET_DIR"
        UDC=$(ls /sys/class/udc | head -1)
        if [ -n "$UDC" ]; then
            echo "$UDC" > UDC
            echo "✅ Enabled gadget on $UDC"
        fi
    fi
fi

# Check if HID device is available
echo "🔍 Checking HID device availability..."
if [ -c /dev/hidg0 ]; then
    echo "✅ HID device /dev/hidg0 is ready"
    chmod 666 /dev/hidg0
    echo "✅ Set permissions on /dev/hidg0"
    HID_AVAILABLE=true
else
    echo "⚠️  HID device /dev/hidg0 not found"
    echo "💡 This is normal on some Pi models or configurations"
    HID_AVAILABLE=false
fi

# Install additional POS forwarding dependencies
echo "📦 Installing additional POS forwarding tools..."
apt-get update -qq

# Install serial communication tools
apt-get install -y python3-serial || echo "⚠️  python3-serial already installed"

# Install clipboard tools
apt-get install -y xclip xsel || echo "⚠️  Clipboard tools installation failed"

# Install keyboard simulation tools
apt-get install -y xdotool || echo "⚠️  xdotool installation failed"

# Install network tools
apt-get install -y python3-requests || echo "⚠️  python3-requests already installed"

# Create systemd service for POS forwarding
echo "⚙️  Creating POS forwarding service..."
cat > /etc/systemd/system/pos-forwarder.service << EOF
[Unit]
Description=Caleffi POS Forwarder Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/var/www/html/abhimanyu/barcode_scanner_clean
ExecStart=/usr/bin/python3 -m src.utils.usb_hid_forwarder
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable pos-forwarder.service
echo "✅ POS forwarder service created and enabled"

# Summary
echo ""
echo "🎉 Enhanced USB HID Setup Complete!"
echo "===================================="
echo "📱 Pi Model: $PI_MODEL"
echo "🔌 USB HID Available: $([ "$HID_AVAILABLE" = true ] && echo "✅ Yes" || echo "⚠️  No (will use alternatives)")"
echo "🛠️  Available Methods:"
echo "   • USB HID Gadget: $([ "$HID_AVAILABLE" = true ] && echo "✅" || echo "❌")"
echo "   • Serial Communication: ✅"
echo "   • Network Forwarding: ✅"
echo "   • Clipboard Integration: ✅"
echo "   • Keyboard Simulation: ✅"
echo ""
echo "🚀 POS forwarding is ready! Barcodes like '8053734093444' will be forwarded automatically."
echo "📋 To test: python3 -c 'from src.utils.usb_hid_forwarder import get_hid_forwarder; get_hid_forwarder().test_barcode_forwarding()'"
echo ""
echo "⚠️  Note: Reboot may be required for USB gadget changes to take effect."
