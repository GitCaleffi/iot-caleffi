#!/bin/bash
# Fix POS forwarding by setting up USB HID gadget
# Run as: sudo ./fix_pos.sh

set -e

echo "🔧 Setting up USB HID gadget for POS forwarding..."

# Load modules
modprobe dwc2 || true
modprobe libcomposite || true

# Create gadget
cd /sys/kernel/config/usb_gadget/
mkdir -p caleffi_scanner
cd caleffi_scanner

# Basic config
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

# Strings
mkdir -p strings/0x409
echo "Caleffi" > strings/0x409/manufacturer
echo "Barcode Scanner" > strings/0x409/product
echo "123456" > strings/0x409/serialnumber

# HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# HID descriptor for keyboard
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc

# Configuration
mkdir -p configs/c.1/strings/0x409
echo "HID Keyboard" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

# Link function
ln -sf functions/hid.usb0 configs/c.1/

# Enable
UDC=$(ls /sys/class/udc | head -1)
echo $UDC > UDC

# Set permissions
sleep 1
chmod 666 /dev/hidg0

echo "✅ USB HID gadget configured!"
echo "📱 Device /dev/hidg0 should now exist"
echo "🎯 POS forwarding will now work for barcode: 8053734093444"
