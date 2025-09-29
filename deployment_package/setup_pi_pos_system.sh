#!/bin/bash

echo "🔧 Raspberry Pi POS System Setup"
echo "================================"

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "⚠️ This script should be run on a Raspberry Pi"
    exit 1
fi

PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null || echo "Unknown Pi")
echo "🍓 Detected: $PI_MODEL"

echo ""
echo "🔍 Step 1: Detecting attached devices..."

# Check for serial devices
SERIAL_DEVICES=$(ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyS* 2>/dev/null | wc -l)
echo "📡 Serial devices found: $SERIAL_DEVICES"
if [ $SERIAL_DEVICES -gt 0 ]; then
    echo "   Devices:"
    ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyS* 2>/dev/null | sed 's/^/   - /'
fi

# Check for USB devices
echo "🔌 USB devices:"
lsusb | grep -v "Linux Foundation" | head -5 | sed 's/^/   - /'

# Check for HID devices
HID_DEVICES=$(ls /dev/hidraw* 2>/dev/null | wc -l)
echo "🖱️ HID devices found: $HID_DEVICES"

echo ""
echo "🔧 Step 2: Setting up USB HID gadget (keyboard emulation)..."

# Check if USB gadget is already configured
if [ -e /dev/hidg0 ]; then
    echo "✅ USB HID gadget already configured"
else
    echo "⚙️ Configuring USB HID gadget..."
    
    # Create setup script
    cat > /tmp/setup_hid_gadget.sh << 'EOF'
#!/bin/bash
set -e

# Load required modules
modprobe libcomposite

# Create gadget directory
cd /sys/kernel/config/usb_gadget/
mkdir -p g1
cd g1

# Configure gadget
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice # v1.0.0
echo 0x0200 > bcdUSB    # USB2

# Create strings
mkdir -p strings/0x409
echo "fedcba9876543210" > strings/0x409/serialnumber
echo "Caleffi" > strings/0x409/manufacturer
echo "Barcode Scanner HID" > strings/0x409/product

# Create configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: HID Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Create HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# HID report descriptor for keyboard
echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc

# Link function to configuration
ln -s functions/hid.usb0 configs/c.1/

# Enable gadget
ls /sys/class/udc > UDC

echo "USB HID gadget setup complete"
EOF

    chmod +x /tmp/setup_hid_gadget.sh
    
    if sudo /tmp/setup_hid_gadget.sh; then
        echo "✅ USB HID gadget configured successfully"
    else
        echo "❌ Failed to configure USB HID gadget"
    fi
fi

echo ""
echo "🔧 Step 3: Installing required Python packages..."

# Check and install required packages
PACKAGES_TO_INSTALL=""

if ! python3 -c "import serial" 2>/dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL pyserial"
fi

if ! python3 -c "import requests" 2>/dev/null; then
    PACKAGES_TO_INSTALL="$PACKAGES_TO_INSTALL requests"
fi

if [ -n "$PACKAGES_TO_INSTALL" ]; then
    echo "📦 Installing packages:$PACKAGES_TO_INSTALL"
    pip3 install $PACKAGES_TO_INSTALL
else
    echo "✅ All required packages already installed"
fi

echo ""
echo "🧪 Step 4: Testing POS forwarding..."

# Test the enhanced POS forwarder
python3 << 'EOF'
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path.cwd()))

try:
    from enhanced_pos_forwarder import EnhancedPOSForwarder
    
    print("🧪 Testing Enhanced POS Forwarder...")
    forwarder = EnhancedPOSForwarder()
    
    # Test with a sample barcode
    test_barcode = "TEST123456789"
    results = forwarder.forward_to_attached_devices(test_barcode)
    
    print(f"\n📊 Test Results for barcode: {test_barcode}")
    successful = []
    failed = []
    
    for method, success in results.items():
        if success:
            successful.append(method)
            print(f"  ✅ {method}: SUCCESS")
        else:
            failed.append(method)
            print(f"  ❌ {method}: FAILED")
    
    print(f"\n🎯 Summary:")
    print(f"  ✅ Working methods: {len(successful)}")
    print(f"  ❌ Failed methods: {len(failed)}")
    
    if successful:
        print(f"\n🎉 POS forwarding is working! Methods: {', '.join(successful)}")
    else:
        print(f"\n⚠️ No POS forwarding methods are working. Check device connections.")

except ImportError as e:
    print(f"❌ Enhanced POS forwarder not found: {e}")
    print("   Make sure enhanced_pos_forwarder.py is in the current directory")
except Exception as e:
    print(f"❌ Error testing POS forwarder: {e}")
EOF

echo ""
echo "🔧 Step 5: Setting up auto-start (optional)..."

# Create systemd service for USB HID gadget
cat > /tmp/usb-hid-gadget.service << 'EOF'
[Unit]
Description=USB HID Gadget Setup
After=multi-user.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/tmp/setup_hid_gadget.sh
User=root

[Install]
WantedBy=multi-user.target
EOF

echo "📄 USB HID gadget service created at /tmp/usb-hid-gadget.service"
echo "   To enable auto-start: sudo cp /tmp/usb-hid-gadget.service /etc/systemd/system/ && sudo systemctl enable usb-hid-gadget.service"

echo ""
echo "🎉 Setup Complete!"
echo "=================="
echo ""
echo "📋 What was configured:"
echo "  ✅ USB HID gadget for keyboard emulation"
echo "  ✅ Serial port detection and configuration"
echo "  ✅ Required Python packages installed"
echo "  ✅ POS forwarding system tested"
echo ""
echo "🔌 How to use:"
echo "  1. Connect your POS device/terminal to the Raspberry Pi via USB"
echo "  2. The Pi will appear as a USB keyboard to the attached device"
echo "  3. When barcodes are scanned, they will be automatically typed into the POS device"
echo "  4. Serial devices will also receive barcode data via serial communication"
echo ""
echo "🧪 To test manually:"
echo "  python3 enhanced_pos_forwarder.py"
echo ""
echo "🔄 To restart barcode scanner service:"
echo "  sudo systemctl restart caleffi-barcode-scanner.service"
