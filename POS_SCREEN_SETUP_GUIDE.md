# 🖥️ POS Screen Connection Guide for Raspberry Pi

## Overview
This guide shows you how to connect a POS screen/terminal to your Raspberry Pi so that scanned barcodes appear directly on the POS display.

## 🔌 Connection Methods

### Method 1: USB HID Gadget (Recommended)
**Best for**: Most POS terminals, tablets, computers
**How it works**: Pi acts as a USB keyboard to the POS device

#### Setup Steps:
1. **Connect Hardware**:
   ```
   Raspberry Pi USB-C/Micro-USB → USB Cable → POS Terminal USB Port
   ```

2. **Enable USB Gadget Mode** (Run on Raspberry Pi):
   ```bash
   # Copy setup script to Pi
   scp setup_pi_pos_system.sh pi@[PI_IP]:~/
   
   # SSH to Pi and run setup
   ssh pi@[PI_IP]
   chmod +x setup_pi_pos_system.sh
   sudo ./setup_pi_pos_system.sh
   ```

3. **Test Connection**:
   ```bash
   # On Raspberry Pi - test if HID gadget is working
   echo "TEST123" | sudo tee /dev/hidg0
   ```
   This should type "TEST123" on your POS screen!

### Method 2: Serial Connection
**Best for**: Industrial POS systems, receipt printers
**How it works**: Direct serial communication

#### Setup Steps:
1. **Connect Hardware**:
   ```
   Pi GPIO Pins → Serial Cable → POS Serial Port
   Pi Pin 8 (TX) → POS RX
   Pi Pin 10 (RX) → POS TX  
   Pi Pin 6 (GND) → POS GND
   ```

2. **Configure Serial** (Run on Raspberry Pi):
   ```bash
   # Enable serial port
   sudo raspi-config
   # Go to: Interface Options → Serial Port → Enable
   
   # Test serial connection
   sudo minicom -D /dev/ttyS0 -b 9600
   ```

### Method 3: Network Connection
**Best for**: WiFi/Ethernet connected POS systems
**How it works**: HTTP/TCP communication

#### Setup Steps:
1. **Find POS IP Address**:
   ```bash
   # Scan network for POS devices
   nmap -sn 192.168.1.0/24
   ```

2. **Configure Network POS**:
   ```bash
   # Test HTTP connection to POS
   curl -X POST http://[POS_IP]:8080/barcode -d "barcode=123456789"
   ```

## 🖥️ POS Screen Types & Setup

### Type 1: Touch Screen POS Terminal
```bash
# Connect via USB HID - Pi acts as keyboard
# Barcodes will appear in active text field on POS
```

### Type 2: Receipt Printer with Display
```bash
# Connect via Serial (RS232/USB-Serial)
# Barcodes printed and/or displayed
```

### Type 3: Customer Display (Pole Display)
```bash
# Connect via Serial or USB
# Barcodes shown on customer-facing screen
```

### Type 4: Tablet/Computer POS Software
```bash
# Connect via USB HID or Network
# Barcodes appear in POS software input fields
```

## 🔧 Quick Setup Script

Create this script on your Raspberry Pi:

```bash
#!/bin/bash
# pos_display_setup.sh

echo "🖥️ POS Display Setup"
echo "===================="

# Method 1: USB HID Test
if [ -e /dev/hidg0 ]; then
    echo "✅ USB HID available - testing..."
    echo "BARCODE_TEST_$(date +%s)" | sudo tee /dev/hidg0
    echo "   → Check if 'BARCODE_TEST_xxx' appeared on POS screen"
else
    echo "❌ USB HID not available - run setup_pi_pos_system.sh first"
fi

# Method 2: Serial Test
echo ""
echo "📡 Testing Serial Ports..."
for port in /dev/ttyUSB* /dev/ttyACM* /dev/ttyS0; do
    if [ -e "$port" ]; then
        echo "✅ Found: $port"
        echo "SERIAL_TEST_$(date +%s)" > "$port" 2>/dev/null && echo "   → Data sent to $port"
    fi
done

# Method 3: Network Test
echo ""
echo "🌐 Scanning for Network POS..."
# Common POS IP ranges
for ip in 192.168.1.{100..110} 192.168.0.{100..110}; do
    if ping -c 1 -W 1 "$ip" >/dev/null 2>&1; then
        echo "✅ Found device at: $ip"
        # Test common POS ports
        for port in 8080 9100 23; do
            if nc -z -w1 "$ip" "$port" 2>/dev/null; then
                echo "   → Port $port open on $ip"
            fi
        done
    fi
done

echo ""
echo "🎯 Setup complete! Connect your POS device and test."
```

## 🧪 Testing Your Setup

### Test 1: Manual Barcode Send
```bash
# On Raspberry Pi - send test barcode
python3 -c "
from deployment_package.enhanced_pos_forwarder import EnhancedPOSForwarder
forwarder = EnhancedPOSForwarder()
result = forwarder.forward_to_attached_devices('TEST123456789')
print('Results:', result)
"
```

### Test 2: Real Barcode Scanner Integration
```bash
# Run your barcode scanner and scan a barcode
python3 keyboard_scanner.py
# Scan any barcode - it should appear on POS screen
```

## 🔍 Troubleshooting

### Issue: Nothing appears on POS screen
**Solutions**:
1. Check USB cable connection
2. Verify POS is in "keyboard input" mode
3. Test with `echo "TEST" | sudo tee /dev/hidg0`

### Issue: Serial connection not working
**Solutions**:
1. Check baud rate (try 9600, 19200, 115200)
2. Verify TX/RX wires not swapped
3. Test with `sudo minicom -D /dev/ttyS0`

### Issue: Network POS not responding
**Solutions**:
1. Check IP address and port
2. Verify firewall settings
3. Test with `telnet [POS_IP] [PORT]`

## 📋 Hardware Requirements

### For USB HID Method:
- Raspberry Pi with USB OTG support (Pi Zero, Pi 4)
- USB cable (Pi to POS)
- POS device that accepts USB keyboard input

### For Serial Method:
- Raspberry Pi with GPIO pins
- Serial cable or USB-to-Serial adapter
- POS device with serial port

### For Network Method:
- Raspberry Pi with WiFi/Ethernet
- Network-connected POS system
- Same network/VLAN access

## 🎯 Expected Results

When properly configured:
1. **Scan barcode** with your scanner
2. **Barcode appears** on POS screen immediately
3. **POS software** processes the barcode as keyboard input
4. **Transaction** continues normally in POS system

Your barcode scanner becomes a seamless input device for your POS system!
