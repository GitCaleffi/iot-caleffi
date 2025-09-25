#!/bin/bash
# Setup USB HID Gadget for Barcode Scanner
# This script configures the Raspberry Pi as a USB HID keyboard device

set -e

echo "🔧 Setting up USB HID Gadget for POS forwarding..."

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "❌ This script must run on Raspberry Pi hardware"
    exit 1
fi

# 1. Enable dwc2 overlay in /boot/config.txt
echo "📝 Configuring /boot/config.txt..."
if ! grep -q "dtoverlay=dwc2" /boot/config.txt; then
    echo "dtoverlay=dwc2" | sudo tee -a /boot/config.txt
    echo "✅ Added dwc2 overlay to /boot/config.txt"
else
    echo "✅ dwc2 overlay already configured"
fi

# 2. Enable libcomposite module
echo "📝 Configuring /etc/modules..."
if ! grep -q "libcomposite" /etc/modules; then
    echo "libcomposite" | sudo tee -a /etc/modules
    echo "✅ Added libcomposite to /etc/modules"
else
    echo "✅ libcomposite already configured"
fi

# 3. Create USB HID gadget setup script
sudo tee /usr/local/bin/setup-hid-gadget.sh > /dev/null << 'EOF'
#!/bin/bash
# USB HID Gadget Setup Script

cd /sys/kernel/config/usb_gadget/
mkdir -p barcode_scanner
cd barcode_scanner

# Device descriptor
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice # v1.0.0
echo 0x0200 > bcdUSB    # USB2

# Device strings
mkdir -p strings/0x409
echo "Caleffi" > strings/0x409/manufacturer
echo "Barcode Scanner HID" > strings/0x409/product
echo "123456789" > strings/0x409/serialnumber

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: HID Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# HID report descriptor for keyboard
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

# Link function to configuration
ln -s functions/hid.usb0 configs/c.1/

# Enable gadget
ls /sys/class/udc > UDC

echo "✅ USB HID gadget configured"
EOF

chmod +x /usr/local/bin/setup-hid-gadget.sh

# 4. Create systemd service for HID gadget
sudo tee /etc/systemd/system/usb-hid-gadget.service > /dev/null << 'EOF'
[Unit]
Description=USB HID Gadget Setup
After=network.target
Before=caleffi-barcode-scanner.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/setup-hid-gadget.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 5. Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable usb-hid-gadget.service

echo ""
echo "🎉 USB HID Gadget setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Reboot the Raspberry Pi: sudo reboot"
echo "2. After reboot, check if /dev/hidg0 exists: ls -la /dev/hidg0"
echo "3. Connect Pi to POS system via USB cable"
echo "4. Test barcode forwarding"
echo ""
echo "⚠️ IMPORTANT: Reboot required to activate USB HID gadget mode"
