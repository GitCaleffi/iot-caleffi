#!/bin/bash
# Raspberry Pi 5 Specific USB HID Setup for POS Forwarding
# Addresses Pi 5's different USB architecture and kernel modules

set -e

echo "🚀 Raspberry Pi 5 USB HID Setup for POS Forwarding"
echo "=================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Detect Pi model
echo "🍓 Detecting Raspberry Pi model..."
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model | tr -d '\0')
    echo "📱 Detected: $PI_MODEL"
else
    PI_MODEL="Unknown Pi Model"
    echo "⚠️  Could not detect Pi model"
fi

# Pi 5 specific configuration
echo "🔧 Configuring for Raspberry Pi 5..."

# Enable USB gadget mode in config.txt
CONFIG_FILE="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="/boot/config.txt"
fi

echo "📝 Updating boot configuration..."
if [ -f "$CONFIG_FILE" ]; then
    # Add Pi 5 specific USB gadget configuration
    if ! grep -q "dtoverlay=dwc2" "$CONFIG_FILE"; then
        echo "dtoverlay=dwc2" >> "$CONFIG_FILE"
        echo "✅ Added dwc2 overlay"
    fi
    
    if ! grep -q "dwc2.dr_mode=peripheral" "$CONFIG_FILE"; then
        echo "dwc2.dr_mode=peripheral" >> "$CONFIG_FILE"
        echo "✅ Added peripheral mode"
    fi
    
    # Pi 5 specific USB configuration
    if ! grep -q "usb_max_current_enable=1" "$CONFIG_FILE"; then
        echo "usb_max_current_enable=1" >> "$CONFIG_FILE"
        echo "✅ Added USB max current"
    fi
else
    echo "❌ Could not find config.txt file"
    exit 1
fi

# Load kernel modules for Pi 5
echo "📦 Loading Pi 5 USB gadget modules..."
modprobe libcomposite || echo "⚠️  libcomposite already loaded"

# Try different USB controller modules for Pi 5
modprobe dwc2 || echo "⚠️  dwc2 not available"
modprobe dwc3 || echo "⚠️  dwc3 not available" 
modprobe dwc3-haps || echo "⚠️  dwc3-haps not available"

# Create USB gadget configuration
GADGET_DIR="/sys/kernel/config/usb_gadget/pi5_pos_scanner"
echo "📁 Creating Pi 5 USB gadget configuration..."

# Remove existing gadget if present
if [ -d "$GADGET_DIR" ]; then
    echo "🗑️  Removing existing gadget configuration..."
    # Disable gadget first
    if [ -f "$GADGET_DIR/UDC" ]; then
        echo "" > "$GADGET_DIR/UDC" 2>/dev/null || true
    fi
    # Remove configuration links
    rm -f "$GADGET_DIR/configs/c.1/hid.usb0" 2>/dev/null || true
    # Remove directories
    rmdir "$GADGET_DIR/functions/hid.usb0" 2>/dev/null || true
    rmdir "$GADGET_DIR/configs/c.1/strings/0x409" 2>/dev/null || true
    rmdir "$GADGET_DIR/configs/c.1" 2>/dev/null || true
    rmdir "$GADGET_DIR/strings/0x409" 2>/dev/null || true
    rmdir "$GADGET_DIR" 2>/dev/null || true
fi

# Create new gadget
mkdir -p "$GADGET_DIR"
cd "$GADGET_DIR"

# Set Pi 5 specific gadget attributes
echo 0x1d6b > idVendor  # Linux Foundation
echo 0x0104 > idProduct # Multifunction Composite Gadget
echo 0x0100 > bcdDevice # v1.0.0
echo 0x0200 > bcdUSB    # USB2

# Create strings
mkdir -p strings/0x409
echo "Caleffi" > strings/0x409/manufacturer
echo "Pi5 POS Scanner HID" > strings/0x409/product
echo "pi5-$(date +%s)" > strings/0x409/serialnumber

# Create HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# Enhanced HID report descriptor for Pi 5
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

# Create configuration
mkdir -p configs/c.1/strings/0x409
echo "Config 1: Pi5 HID Keyboard" > configs/c.1/strings/0x409/configuration
echo 500 > configs/c.1/MaxPower  # Higher power for Pi 5

# Link function to configuration
ln -sf "$GADGET_DIR/functions/hid.usb0" "$GADGET_DIR/configs/c.1/"

# Find and enable UDC for Pi 5
echo "🔌 Enabling USB gadget on Pi 5..."
UDC_LIST=$(ls /sys/class/udc 2>/dev/null || echo "")

if [ -n "$UDC_LIST" ]; then
    for udc in $UDC_LIST; do
        echo "🔄 Trying UDC controller: $udc"
        if echo "$udc" > UDC 2>/dev/null; then
            echo "✅ Pi 5 USB HID gadget enabled on $udc"
            UDC_SUCCESS=true
            break
        else
            echo "⚠️  Failed to enable on $udc"
        fi
    done
    
    if [ "$UDC_SUCCESS" != true ]; then
        echo "❌ Failed to enable gadget on any UDC controller"
        echo "Available controllers: $UDC_LIST"
    fi
else
    echo "❌ No UDC controllers found"
    echo "💡 This may require a reboot to load Pi 5 USB modules"
fi

# Wait for device creation
echo "⏳ Waiting for HID device creation..."
sleep 3

# Check if HID device is available
if [ -c /dev/hidg0 ]; then
    echo "✅ Pi 5 HID device /dev/hidg0 is ready!"
    chmod 666 /dev/hidg0
    echo "✅ Set permissions on /dev/hidg0"
    
    # Test the HID device
    echo "🧪 Testing Pi 5 HID device..."
    echo -ne \\x00\\x00\\x04\\x00\\x00\\x00\\x00\\x00 > /dev/hidg0  # Send 'a'
    echo -ne \\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00 > /dev/hidg0  # Release
    echo "✅ Pi 5 HID test successful!"
    
else
    echo "⚠️  HID device /dev/hidg0 not found"
    echo "💡 A reboot may be required for Pi 5 USB gadget mode"
    echo "💡 Run: sudo reboot"
fi

# Create Pi 5 specific test script
cat > /tmp/test_pi5_hid.py << 'EOF'
#!/usr/bin/env python3
import time
import os

def test_pi5_hid_barcode(barcode="8053734093444"):
    """Test Pi 5 HID with barcode"""
    if not os.path.exists('/dev/hidg0'):
        print("❌ /dev/hidg0 not found - reboot may be required")
        return False
    
    try:
        with open('/dev/hidg0', 'wb') as hid:
            print(f"🚀 Sending barcode {barcode} via Pi 5 HID...")
            
            # HID codes for digits
            hid_codes = {'0': 39, '1': 30, '2': 31, '3': 32, '4': 33, '5': 34, '6': 35, '7': 36, '8': 37, '9': 38}
            
            for char in barcode:
                if char in hid_codes:
                    code = hid_codes[char]
                    # Press key
                    hid.write(bytes([0, 0, code, 0, 0, 0, 0, 0]))
                    # Release key
                    hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))
                    time.sleep(0.01)
            
            # Send Enter
            hid.write(bytes([0, 0, 40, 0, 0, 0, 0, 0]))  # Enter press
            hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))   # Enter release
            
        print(f"✅ Pi 5 HID barcode {barcode} sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Pi 5 HID test failed: {e}")
        return False

if __name__ == "__main__":
    test_pi5_hid_barcode()
EOF

chmod +x /tmp/test_pi5_hid.py

echo ""
echo "🎉 Pi 5 USB HID Setup Complete!"
echo "==============================="
echo "📱 Pi Model: $PI_MODEL"
echo "🔌 HID Device: $([ -c /dev/hidg0 ] && echo '✅ Available' || echo '⚠️  Requires reboot')"
echo ""
echo "🧪 To test Pi 5 HID barcode forwarding:"
echo "   python3 /tmp/test_pi5_hid.py"
echo ""
echo "🚀 To use with barcode scanner:"
echo "   python3 keyboard_scanner.py"
echo ""
echo "⚠️  If HID device not found, reboot Pi 5:"
echo "   sudo reboot"
