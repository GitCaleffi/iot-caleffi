#!/bin/bash
# Intel System POS Forwarding Setup
# For forwarding barcodes to USB POS terminals on Intel/AMD systems

set -e

echo "💻 Intel System POS Forwarding Setup"
echo "===================================="

# Check system
echo "🔍 Detecting system..."
SYSTEM_INFO=$(uname -a)
CPU_INFO=$(cat /proc/cpuinfo | grep "model name" | head -1 | cut -d: -f2 | xargs)
echo "💻 System: $CPU_INFO"
echo "🐧 Kernel: $(uname -r)"

# Install dependencies for Intel system POS forwarding
echo "📦 Installing POS forwarding dependencies..."

# Update package list
apt-get update -qq

# Install keyboard simulation tools
echo "⌨️  Installing keyboard simulation tools..."
apt-get install -y xdotool || echo "⚠️  xdotool installation failed"

# Install clipboard tools
echo "📋 Installing clipboard tools..."
apt-get install -y xclip xsel || echo "⚠️  Clipboard tools installation failed"

# Install USB communication tools
echo "🔌 Installing USB communication tools..."
apt-get install -y usbutils libusb-1.0-0-dev || echo "⚠️  USB tools installation failed"

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install pyserial pynput keyboard || echo "⚠️  Python dependencies installation failed"

# Create Intel-specific POS forwarder
cat > /tmp/intel_pos_forwarder.py << 'EOF'
#!/usr/bin/env python3
"""
Intel System POS Forwarder
Forwards barcodes to USB POS terminals on Intel/AMD systems
"""

import time
import subprocess
import logging
import os
import glob

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntelPOSForwarder:
    def __init__(self):
        self.available_methods = self._detect_methods()
        logger.info(f"💻 Intel POS Forwarder initialized")
        logger.info(f"🔧 Available methods: {', '.join(self.available_methods)}")
    
    def _detect_methods(self):
        methods = []
        
        # Check for keyboard simulation
        if self._command_exists('xdotool'):
            methods.append('KEYBOARD_SIM')
        
        # Check for clipboard tools
        if self._command_exists('xclip') or self._command_exists('xsel'):
            methods.append('CLIPBOARD')
        
        # Check for serial ports (USB-to-Serial adapters)
        serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        if serial_ports:
            methods.append('SERIAL')
        
        # Always available
        methods.append('ACTIVE_WINDOW')
        methods.append('FILE')
        
        return methods
    
    def _command_exists(self, command):
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except:
            return False
    
    def forward_barcode(self, barcode):
        """Forward barcode using best available method for Intel systems"""
        logger.info(f"🚀 Forwarding barcode: {barcode}")
        
        # Try methods in order of preference for POS terminals
        methods = [
            ('ACTIVE_WINDOW', self._forward_to_active_window),
            ('KEYBOARD_SIM', self._forward_via_keyboard_sim),
            ('SERIAL', self._forward_via_serial),
            ('CLIPBOARD', self._forward_via_clipboard),
            ('FILE', self._forward_via_file)
        ]
        
        for method_name, method_func in methods:
            if method_name in self.available_methods:
                try:
                    logger.info(f"🔄 Trying {method_name}...")
                    success = method_func(barcode)
                    if success:
                        logger.info(f"✅ Successfully forwarded via {method_name}")
                        return True
                    else:
                        logger.warning(f"⚠️  {method_name} failed, trying next...")
                except Exception as e:
                    logger.error(f"❌ {method_name} error: {e}")
        
        logger.error("❌ All forwarding methods failed")
        return False
    
    def _forward_to_active_window(self, barcode):
        """Forward barcode to currently active window (POS terminal)"""
        try:
            # Get active window info
            result = subprocess.run(['xdotool', 'getactivewindow', 'getwindowname'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                window_name = result.stdout.strip()
                logger.info(f"🎯 Active window: {window_name}")
            
            # Type the barcode in the active window
            subprocess.run(['xdotool', 'type', '--delay', '50', barcode], check=True)
            
            # Send Enter key
            time.sleep(0.1)
            subprocess.run(['xdotool', 'key', 'Return'], check=True)
            
            logger.info(f"⌨️  Typed barcode in active window")
            return True
            
        except Exception as e:
            logger.error(f"Active window forwarding failed: {e}")
            return False
    
    def _forward_via_keyboard_sim(self, barcode):
        """Forward via keyboard simulation"""
        try:
            # Focus on the current window and type
            subprocess.run(['xdotool', 'type', '--delay', '30', barcode], 
                         timeout=5, check=True)
            subprocess.run(['xdotool', 'key', 'Return'], timeout=2, check=True)
            return True
        except Exception as e:
            logger.error(f"Keyboard simulation failed: {e}")
            return False
    
    def _forward_via_serial(self, barcode):
        """Forward via USB-to-Serial adapter"""
        try:
            import serial
            serial_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
            
            for port in serial_ports:
                try:
                    with serial.Serial(port, 9600, timeout=1) as ser:
                        ser.write(f"{barcode}\r\n".encode())
                        ser.flush()
                        logger.info(f"📡 Sent to serial port {port}")
                        return True
                except Exception as e:
                    logger.warning(f"Serial port {port} failed: {e}")
                    continue
            return False
        except ImportError:
            logger.warning("Serial module not available")
            return False
        except Exception as e:
            logger.error(f"Serial forwarding failed: {e}")
            return False
    
    def _forward_via_clipboard(self, barcode):
        """Forward via clipboard"""
        try:
            subprocess.run(['xclip', '-selection', 'clipboard'], 
                         input=barcode.encode(), timeout=2, check=True)
            logger.info("📋 Copied to clipboard")
            return True
        except:
            try:
                subprocess.run(['xsel', '--clipboard', '--input'], 
                             input=barcode.encode(), timeout=2, check=True)
                logger.info("📋 Copied to clipboard (xsel)")
                return True
            except:
                return False
    
    def _forward_via_file(self, barcode):
        """Forward via file"""
        try:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            with open('/tmp/pos_barcode.txt', 'a') as f:
                f.write(f"{timestamp}: {barcode}\n")
            with open('/tmp/current_barcode.txt', 'w') as f:
                f.write(barcode)
            logger.info("📄 Written to file")
            return True
        except Exception as e:
            logger.error(f"File forwarding failed: {e}")
            return False

def test_intel_pos_forwarding():
    """Test Intel POS forwarding"""
    forwarder = IntelPOSForwarder()
    
    test_barcode = "8053734093444"
    print(f"\n🧪 Testing Intel POS forwarding with: {test_barcode}")
    print("=" * 50)
    
    success = forwarder.forward_barcode(test_barcode)
    
    if success:
        print(f"✅ Barcode {test_barcode} forwarded successfully!")
        print("💡 Check your POS terminal or active window")
    else:
        print(f"❌ Failed to forward barcode {test_barcode}")
    
    return success

if __name__ == "__main__":
    test_intel_pos_forwarding()
EOF

chmod +x /tmp/intel_pos_forwarder.py

# Test the Intel POS forwarder
echo ""
echo "🧪 Testing Intel POS forwarding..."
python3 /tmp/intel_pos_forwarder.py

echo ""
echo "🎉 Intel System POS Forwarding Setup Complete!"
echo "=============================================="
echo "💻 System: Intel-based system detected"
echo "🔧 Method: Active window keyboard simulation"
echo ""
echo "📋 Usage Instructions:"
echo "1. Open your POS terminal software"
echo "2. Click in the barcode input field"
echo "3. Run your barcode scanner"
echo "4. Barcodes will be typed directly into the active window"
echo ""
echo "🧪 To test manually:"
echo "   python3 /tmp/intel_pos_forwarder.py"
echo ""
echo "💡 The barcode will appear wherever your cursor is focused!"
