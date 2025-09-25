#!/bin/bash
# USB HID Gadget Setup for Caleffi Barcode Scanner
# This script sets up the Raspberry Pi as a USB HID keyboard for POS forwarding

set -e

echo "🔧 Setting up USB HID gadget for POS forwarding..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Load required modules
echo "📦 Loading USB gadget modules..."
modprobe dwc2 || echo "⚠️  dwc2 module already loaded or not available"
modprobe libcomposite || echo "⚠️  libcomposite module already loaded or not available"

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

    # Enable gadget
    UDC=$(ls /sys/class/udc | head -1)
    if [ -n "$UDC" ]; then
        echo "$UDC" > UDC
        echo "✅ USB HID gadget enabled on $UDC"
    else
        echo "❌ No UDC controller found"
        exit 1
    fi
else
    echo "✅ USB HID gadget already configured"
fi

# Check if HID device is available
if [ -c /dev/hidg0 ]; then
    echo "✅ HID device /dev/hidg0 is ready"
    chmod 666 /dev/hidg0
    echo "✅ Set permissions on /dev/hidg0"
else
    echo "❌ HID device /dev/hidg0 not found"
    exit 1
fi

echo "🎉 USB HID setup complete! POS forwarding is now available."
