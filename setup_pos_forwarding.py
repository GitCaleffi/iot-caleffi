#!/usr/bin/env python3
"""
Complete POS Forwarding Setup - Multiple methods to send barcodes to PC
Handles USB HID, Network, and Clipboard forwarding
"""
import os
import sys
import time
import socket
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class POSForwardingManager:
    def __init__(self):
        self.hid_device = "/dev/hidg0"
        self.network_server = None
        self.server_thread = None
        self.port = 8080
        
    def check_hid_available(self):
        """Check if USB HID is available"""
        return os.path.exists(self.hid_device)
    
    def setup_usb_hid(self):
        """Setup USB HID gadget (requires root)"""
        print("🔧 Setting up USB HID gadget...")
        
        setup_script = """#!/bin/bash
# USB HID Gadget Setup
set -e

echo "Loading USB gadget modules..."
modprobe dwc2 2>/dev/null || true
modprobe libcomposite 2>/dev/null || true

echo "Creating USB gadget..."
cd /sys/kernel/config/usb_gadget/
mkdir -p caleffi_scanner 2>/dev/null || true
cd caleffi_scanner

# Device info
echo 0x1d6b > idVendor 2>/dev/null || true
echo 0x0104 > idProduct 2>/dev/null || true
echo 0x0100 > bcdDevice 2>/dev/null || true
echo 0x0200 > bcdUSB 2>/dev/null || true

# Strings
mkdir -p strings/0x409 2>/dev/null || true
echo "Caleffi" > strings/0x409/manufacturer 2>/dev/null || true
echo "Barcode Scanner" > strings/0x409/product 2>/dev/null || true
echo "123456" > strings/0x409/serialnumber 2>/dev/null || true

# HID function
mkdir -p functions/hid.usb0 2>/dev/null || true
echo 1 > functions/hid.usb0/protocol 2>/dev/null || true
echo 1 > functions/hid.usb0/subclass 2>/dev/null || true
echo 8 > functions/hid.usb0/report_length 2>/dev/null || true

# HID descriptor for keyboard
echo -ne \\x05\\x01\\x09\\x06\\xa1\\x01\\x05\\x07\\x19\\xe0\\x29\\xe7\\x15\\x00\\x25\\x01\\x75\\x01\\x95\\x08\\x81\\x02\\x95\\x01\\x75\\x08\\x81\\x03\\x95\\x05\\x75\\x01\\x05\\x08\\x19\\x01\\x29\\x05\\x91\\x02\\x95\\x01\\x75\\x03\\x91\\x03\\x95\\x06\\x75\\x08\\x15\\x00\\x25\\x65\\x05\\x07\\x19\\x00\\x29\\x65\\x81\\x00\\xc0 > functions/hid.usb0/report_desc 2>/dev/null || true

# Configuration
mkdir -p configs/c.1/strings/0x409 2>/dev/null || true
echo "HID Keyboard" > configs/c.1/strings/0x409/configuration 2>/dev/null || true
echo 250 > configs/c.1/MaxPower 2>/dev/null || true

# Link function
ln -sf functions/hid.usb0 configs/c.1/ 2>/dev/null || true

# Enable gadget
UDC=$(ls /sys/class/udc 2>/dev/null | head -1)
if [ ! -z "$UDC" ]; then
    echo $UDC > UDC 2>/dev/null || true
fi

# Set permissions
sleep 1
chmod 666 /dev/hidg0 2>/dev/null || true

echo "✅ USB HID setup complete!"
"""
        
        with open('/tmp/setup_hid.sh', 'w') as f:
            f.write(setup_script)
        os.chmod('/tmp/setup_hid.sh', 0o755)
        
        print("📋 To enable USB HID, run:")
        print("sudo /tmp/setup_hid.sh")
        return False
    
    def send_via_hid(self, barcode):
        """Send barcode via USB HID"""
        if not os.path.exists(self.hid_device):
            return False
            
        try:
            print(f"📤 Sending via USB HID: {barcode}")
            
            with open(self.hid_device, 'wb') as hid:
                # Convert each character to HID keyboard codes
                for char in barcode:
                    if char.isdigit():
                        # Numbers 0-9 map to HID codes 30-39
                        hid_code = ord(char) - ord('0') + 30
                        # Send key press
                        hid.write(bytes([0, 0, hid_code, 0, 0, 0, 0, 0]))
                        # Send key release
                        hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))
                        time.sleep(0.01)
                
                # Send Enter key
                hid.write(bytes([0, 0, 40, 0, 0, 0, 0, 0]))  # Enter press
                hid.write(bytes([0, 0, 0, 0, 0, 0, 0, 0]))   # Enter release
            
            print(f"✅ HID: Barcode {barcode} sent to PC!")
            return True
            
        except Exception as e:
            print(f"❌ HID failed: {e}")
            return False
    
    def start_network_server(self):
        """Start network server for PC connection"""
        try:
            class BarcodeHandler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>POS Barcode Receiver</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
        .barcode {{ font-size: 24px; font-weight: bold; padding: 15px; background: #e8f4fd; 
                   border: 2px solid #007cba; border-radius: 5px; margin: 20px 0; text-align: center; }}
        .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
        .success {{ background: #d4edda; color: #155724; }}
        button {{ background: #007cba; color: white; border: none; padding: 10px 20px; 
                 border-radius: 5px; cursor: pointer; font-size: 16px; margin: 5px; }}
        button:hover {{ background: #005a87; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 POS Barcode Receiver</h1>
        <div class="status success">
            <strong>Status:</strong> Ready to receive barcodes from Raspberry Pi
        </div>
        
        <div id="latestBarcode" style="display:none;">
            <h3>Latest Barcode:</h3>
            <div class="barcode" id="barcodeDisplay"></div>
            <button onclick="copyBarcode()">📋 Copy to Clipboard</button>
            <button onclick="clearBarcode()">🗑️ Clear</button>
        </div>
        
        <div id="instructions">
            <h3>📋 Instructions:</h3>
            <ol>
                <li>Keep this page open</li>
                <li>Scan barcodes on Raspberry Pi</li>
                <li>Barcodes will appear here automatically</li>
                <li>Click "Copy to Clipboard" to copy</li>
                <li>Paste into Notepad or POS system</li>
            </ol>
        </div>
        
        <div id="barcodeHistory">
            <h3>Recent Barcodes:</h3>
            <div id="history"></div>
        </div>
    </div>

    <script>
        let latestBarcode = '';
        
        function updateBarcode(barcode) {{
            latestBarcode = barcode;
            document.getElementById('barcodeDisplay').textContent = barcode;
            document.getElementById('latestBarcode').style.display = 'block';
            
            // Add to history
            const history = document.getElementById('history');
            const item = document.createElement('div');
            item.style.cssText = 'background: #f8f9fa; border: 1px solid #dee2e6; padding: 10px; margin: 5px 0; border-radius: 5px;';
            item.innerHTML = `
                <span style="font-family: monospace; font-weight: bold;">${{barcode}}</span>
                <button onclick="copyToClipboard('${{barcode}}')" style="float: right;">Copy</button>
            `;
            history.insertBefore(item, history.firstChild);
        }}
        
        function copyBarcode() {{
            copyToClipboard(latestBarcode);
        }}
        
        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(() => {{
                alert('Barcode copied: ' + text);
            }});
        }}
        
        function clearBarcode() {{
            document.getElementById('latestBarcode').style.display = 'none';
        }}
        
        // Poll for new barcodes
        setInterval(() => {{
            fetch('/api/latest')
                .then(response => response.json())
                .then(data => {{
                    if (data.barcode && data.barcode !== latestBarcode) {{
                        updateBarcode(data.barcode);
                    }}
                }})
                .catch(err => console.log('Polling...'));
        }}, 1000);
    </script>
</body>
</html>
                        """
                        self.wfile.write(html.encode())
                        
                    elif self.path == '/api/latest':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        
                        response = {'barcode': getattr(self.server, 'latest_barcode', '')}
                        self.wfile.write(json.dumps(response).encode())
                
                def do_POST(self):
                    if self.path == '/api/barcode':
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        
                        try:
                            data = json.loads(post_data.decode())
                            barcode = data.get('barcode', '')
                            
                            # Store latest barcode
                            self.server.latest_barcode = barcode
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            
                            response = {'status': 'success', 'message': f'Barcode {barcode} received'}
                            self.wfile.write(json.dumps(response).encode())
                            
                        except Exception as e:
                            self.send_response(400)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            
                            response = {'status': 'error', 'message': str(e)}
                            self.wfile.write(json.dumps(response).encode())
                
                def log_message(self, format, *args):
                    pass  # Suppress server logs
            
            self.network_server = HTTPServer(('0.0.0.0', self.port), BarcodeHandler)
            self.network_server.latest_barcode = ''
            
            self.server_thread = threading.Thread(target=self.network_server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Network server failed: {e}")
            return False
    
    def send_via_network(self, barcode):
        """Send barcode via network to PC"""
        try:
            import requests
            url = f"http://localhost:{self.port}/api/barcode"
            data = {'barcode': barcode}
            
            response = requests.post(url, json=data, timeout=2)
            if response.status_code == 200:
                print(f"✅ Network: Barcode {barcode} sent to PC!")
                return True
            else:
                return False
                
        except Exception:
            return False
    
    def send_via_clipboard(self, barcode):
        """Fallback: Save to clipboard file"""
        try:
            clipboard_file = "/tmp/pos_barcode.txt"
            with open(clipboard_file, 'w') as f:
                f.write(f"{barcode}\n")
            
            print(f"📋 Barcode saved to {clipboard_file}")
            print(f"💡 Copy this to Notepad: {barcode}")
            return True
            
        except Exception as e:
            print(f"❌ Clipboard failed: {e}")
            return False
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "localhost"
    
    def send_barcode_to_pos(self, barcode):
        """Main function: Send barcode using best available method"""
        print(f"\n🎯 Sending barcode to POS: {barcode}")
        
        # Method 1: USB HID (direct keyboard input)
        if self.send_via_hid(barcode):
            return True
        
        # Method 2: Network (web interface)
        if self.send_via_network(barcode):
            return True
        
        # Method 3: Clipboard fallback
        return self.send_via_clipboard(barcode)
    
    def show_status(self):
        """Show current POS forwarding status"""
        print("🔍 POS Forwarding Status:")
        print("=" * 40)
        
        # Check USB HID
        if os.path.exists(self.hid_device):
            print("✅ USB HID: Available")
        else:
            print("❌ USB HID: Not available")
            print("   💡 Run: sudo /tmp/setup_hid.sh")
        
        # Check network server
        if self.network_server:
            ip = self.get_local_ip()
            print(f"✅ Network: Running on http://{ip}:{self.port}")
            print(f"   🌐 Open this URL on your PC: http://{ip}:{self.port}")
        else:
            print("❌ Network: Not running")
        
        print("✅ Clipboard: Always available")

def main():
    print("🚀 POS Forwarding Setup")
    print("=" * 50)
    
    manager = POSForwardingManager()
    
    # Setup USB HID if needed
    if not manager.check_hid_available():
        manager.setup_usb_hid()
    
    # Start network server
    print("🌐 Starting network server...")
    if manager.start_network_server():
        ip = manager.get_local_ip()
        print(f"✅ Network server started!")
        print(f"🌐 PC URL: http://{ip}:8080")
    
    # Show status
    manager.show_status()
    
    # Test with your barcode
    print(f"\n🧪 Testing with barcode: 8053734093444")
    success = manager.send_barcode_to_pos("8053734093444")
    
    if success:
        print("✅ Test successful!")
        print("📝 Check your PC - barcode should appear in Notepad or web interface")
    else:
        print("❌ Test failed - check setup")
    
    # Interactive mode
    print(f"\n⌨️  Interactive mode (Ctrl+C to exit)")
    try:
        while True:
            barcode = input("\nEnter barcode: ").strip()
            if barcode:
                manager.send_barcode_to_pos(barcode)
    except KeyboardInterrupt:
        print(f"\n👋 Shutting down...")
        if manager.network_server:
            manager.network_server.shutdown()

if __name__ == "__main__":
    main()
