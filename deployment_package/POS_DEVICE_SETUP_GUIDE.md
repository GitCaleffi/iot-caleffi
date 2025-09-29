# POS Device Setup Guide

## Problem: Scanned Barcodes Not Showing on Attached Device

When you attach another device (POS terminal, computer, tablet) to your Raspberry Pi, you want scanned barcodes to automatically appear on that attached device as if someone typed them.

## Solution: Multiple POS Forwarding Methods

The system now supports **4 different methods** to forward barcodes to attached devices:

### 1. 🔌 USB HID Keyboard Emulation (Recommended)
- **How it works**: Raspberry Pi acts as a USB keyboard to the attached device
- **Best for**: POS terminals, computers, tablets connected via USB
- **Advantage**: Works with any device that accepts keyboard input
- **Setup**: Automatic via `setup_pi_pos_system.sh`

### 2. 📡 Serial Port Communication
- **How it works**: Sends barcodes via serial/COM ports
- **Best for**: Industrial POS systems, receipt printers, cash registers
- **Advantage**: Direct hardware communication
- **Setup**: Automatic detection of `/dev/ttyUSB*`, `/dev/ttyACM*` ports

### 3. 🌐 Network Communication
- **How it works**: Sends barcodes via HTTP/TCP to network devices
- **Best for**: Network-connected POS systems, web-based terminals
- **Advantage**: Works over WiFi/Ethernet
- **Setup**: Automatic scanning of common POS IP addresses

### 4. 🖱️ Direct HID Device Communication
- **How it works**: Direct communication with HID devices
- **Best for**: Specialized barcode scanners, input devices
- **Advantage**: Low-level device control
- **Setup**: Automatic detection of `/dev/hidraw*` devices

## Quick Setup (Raspberry Pi)

### Step 1: Copy Setup Files to Raspberry Pi
```bash
# Copy the setup files to your Raspberry Pi
scp setup_pi_pos_system.sh pi@[PI_IP]:~/
scp enhanced_pos_forwarder.py pi@[PI_IP]:~/
```

### Step 2: Run Setup Script
```bash
# SSH to Raspberry Pi
ssh pi@[PI_IP]

# Run the setup script
chmod +x setup_pi_pos_system.sh
./setup_pi_pos_system.sh
```

### Step 3: Connect Your POS Device
- **USB Connection**: Connect POS device to Pi via USB cable
- **Serial Connection**: Connect via USB-to-Serial adapter
- **Network Connection**: Ensure both devices are on same network

### Step 4: Test the Connection
```bash
# Test POS forwarding
python3 enhanced_pos_forwarder.py
```

## Manual Setup (Advanced)

### USB HID Gadget Setup
```bash
# Enable USB gadget modules
sudo modprobe libcomposite

# Create USB HID gadget configuration
sudo mkdir -p /sys/kernel/config/usb_gadget/g1
cd /sys/kernel/config/usb_gadget/g1

# Configure as keyboard device
echo 0x1d6b > idVendor
echo 0x0104 > idProduct
echo "Caleffi Barcode Scanner" > strings/0x409/product

# Create HID function
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol
echo 1 > functions/hid.usb0/subclass
echo 8 > functions/hid.usb0/report_length

# Enable gadget
ls /sys/class/udc > UDC
```

### Install Required Packages
```bash
# Install Python packages
pip3 install pyserial requests

# Install system tools
sudo apt-get update
sudo apt-get install usbutils
```

## How It Works

### When You Scan a Barcode:

1. **Barcode Detection**: Scanner detects barcode (e.g., "8053734093444")

2. **Enhanced POS Forwarding**: System tries multiple methods:
   ```
   📤 Forwarding barcode 8053734093444 to attached devices...
   ⌨️ Forwarding via USB HID keyboard...
   ✅ USB HID keyboard forwarding successful
   📡 Forwarding to serial port /dev/ttyUSB0...
   ✅ Serial port /dev/ttyUSB0 forwarding successful
   ```

3. **Attached Device Receives**: 
   - **USB HID**: Barcode appears as typed text: `8053734093444`
   - **Serial**: Barcode sent via serial: `8053734093444\r\n`
   - **Network**: HTTP POST to POS system with barcode data

### Example Output:
```
📊 Forwarding results:
  ✅ Successful: USB_HID, SERIAL_/dev/ttyUSB0
  ❌ Failed: NETWORK_192.168.1.100
```

## Supported Device Types

### ✅ Compatible Devices:
- **POS Terminals**: Most USB-connected POS systems
- **Computers/Laptops**: Windows, Mac, Linux via USB
- **Tablets**: Android/iPad with USB OTG support
- **Receipt Printers**: Serial-connected thermal printers
- **Cash Registers**: Serial/USB connected registers
- **Barcode Displays**: Customer-facing displays
- **Industrial Terminals**: Rugged POS hardware

### ⚠️ Device-Specific Notes:
- **Windows POS**: May require driver installation for USB HID
- **Android Tablets**: Need USB OTG adapter and keyboard app
- **Serial Devices**: Check baud rate (default: 9600)
- **Network POS**: Verify IP address and API endpoints

## Troubleshooting

### No Barcodes Appearing on Attached Device

1. **Check USB Connection**:
   ```bash
   lsusb  # Should show connected device
   ls /dev/hidg0  # Should exist if HID gadget working
   ```

2. **Check Serial Ports**:
   ```bash
   ls /dev/ttyUSB* /dev/ttyACM*  # Should show serial devices
   ```

3. **Test Forwarding Methods**:
   ```bash
   python3 enhanced_pos_forwarder.py
   # Enter test barcode when prompted
   ```

4. **Check Logs**:
   ```bash
   journalctl -u caleffi-barcode-scanner.service -f
   ```

### Common Issues:

**"USB HID gadget not available"**
- Solution: Run `setup_pi_pos_system.sh` with sudo privileges
- Check: `sudo modprobe libcomposite`

**"No serial ports found"**
- Solution: Check USB-to-Serial adapter connection
- Check: `dmesg | grep tty` for device detection

**"All POS methods failed"**
- Solution: Verify device connections and compatibility
- Check: Device accepts keyboard input or serial data

## Configuration Files

### Enhanced POS Forwarder Config
Location: `/tmp/pos_device_config.json`
```json
{
  "detected_devices": {
    "serial_ports": ["/dev/ttyUSB0"],
    "usb_keyboards": ["usb-keyboard-device"],
    "network_terminals": ["192.168.1.100"]
  },
  "forwarding_methods": ["USB_HID", "SERIAL", "NETWORK"]
}
```

### Service Configuration
The barcode scanner service automatically uses enhanced POS forwarding:
```bash
sudo systemctl status caleffi-barcode-scanner.service
```

## Advanced Features

### Custom Serial Settings
Edit `enhanced_pos_forwarder.py` to modify serial parameters:
```python
# Change baud rate, parity, etc.
with serial.Serial(port, 19200, timeout=2) as ser:  # 19200 baud
```

### Custom Network Endpoints
Add your POS system's IP/URL:
```python
endpoints = [
    'http://your-pos-system:8080/api/barcode',
    'http://192.168.1.50/scan',
]
```

### Multiple Device Support
The system automatically detects and forwards to ALL attached devices simultaneously.

## Testing Commands

```bash
# Test all methods
python3 enhanced_pos_forwarder.py

# Test specific barcode
python3 -c "
from enhanced_pos_forwarder import EnhancedPOSForwarder
forwarder = EnhancedPOSForwarder()
forwarder.forward_to_attached_devices('1234567890123')
"

# Check device detection
python3 setup_pos_forwarding.py
```

## Support

If barcodes still don't appear on your attached device:

1. **Verify device compatibility** - Test with manual keyboard input
2. **Check connection type** - USB, Serial, or Network
3. **Review logs** - Look for forwarding success/failure messages
4. **Test with simple device** - Try with a basic computer first

The enhanced POS forwarding system supports multiple simultaneous devices and automatically chooses the best method for each attached device.
