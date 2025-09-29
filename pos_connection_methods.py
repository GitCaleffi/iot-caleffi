#!/usr/bin/env python3
"""
POS System Connection Methods
Complete guide for all ways to connect POS systems to barcode scanner
"""

import os
import sys
import json
import time
import socket
import subprocess
from pathlib import Path

def show_connection_methods():
    """Display all available POS connection methods"""
    
    methods = {
        "1. USB HID (Keyboard Emulation)": {
            "description": "Pi acts as USB keyboard to POS terminal",
            "hardware": "USB cable: Pi → POS USB port",
            "best_for": "Most POS terminals, tablets, computers",
            "advantages": ["Works with any device accepting keyboard input", "Plug and play", "No software needed on POS"],
            "setup": "Already implemented in usb_pos_forwarder.py"
        },
        
        "2. Serial Communication (RS232/RS485)": {
            "description": "Direct serial communication to POS",
            "hardware": "Serial cable: Pi GPIO → POS serial port",
            "best_for": "Industrial POS, receipt printers, cash registers",
            "advantages": ["Direct hardware communication", "Reliable", "Works with legacy systems"],
            "setup": "GPIO pins or USB-to-Serial adapter"
        },
        
        "3. Network/WiFi Connection": {
            "description": "Send barcodes over network to POS software",
            "hardware": "WiFi/Ethernet network connection",
            "best_for": "Modern POS software, cloud-based systems",
            "advantages": ["Wireless operation", "Multiple devices", "Remote monitoring"],
            "setup": "HTTP/TCP/WebSocket communication"
        },
        
        "4. HDMI Display Output": {
            "description": "Show barcodes on external monitor/TV",
            "hardware": "HDMI cable or USB-to-HDMI adapter",
            "best_for": "Customer displays, large screens",
            "advantages": ["Large visual display", "Customer-facing", "Easy to read"],
            "setup": "Already implemented in hdmi_pos_display.py"
        },
        
        "5. Bluetooth Connection": {
            "description": "Wireless Bluetooth communication to POS",
            "hardware": "Bluetooth-enabled POS device",
            "best_for": "Mobile POS, tablets, modern terminals",
            "advantages": ["Wireless", "No cables", "Mobile friendly"],
            "setup": "Bluetooth pairing and communication"
        },
        
        "6. Web Interface": {
            "description": "Web browser-based POS display",
            "hardware": "Any device with web browser",
            "best_for": "Tablets, computers, smart displays",
            "advantages": ["Universal compatibility", "Remote access", "Easy updates"],
            "setup": "Web server on Pi, browser on POS device"
        },
        
        "7. File Sharing (Network Drive)": {
            "description": "Save barcodes to shared network folder",
            "hardware": "Network connection",
            "best_for": "Legacy systems, file-based POS software",
            "advantages": ["Simple integration", "Works with any OS", "No special software"],
            "setup": "SMB/NFS shared folder"
        },
        
        "8. Database Integration": {
            "description": "Direct database connection to POS database",
            "hardware": "Network connection to POS database",
            "best_for": "Enterprise POS systems, SQL-based systems",
            "advantages": ["Real-time updates", "Direct integration", "No middleware"],
            "setup": "Database connection and SQL queries"
        },
        
        "9. API Integration": {
            "description": "REST API calls to POS system",
            "hardware": "Network connection",
            "best_for": "Modern POS with API support",
            "advantages": ["Standard integration", "Secure", "Scalable"],
            "setup": "HTTP API calls with authentication"
        },
        
        "10. Barcode Wedge Emulation": {
            "description": "Emulate barcode scanner input to POS",
            "hardware": "USB connection",
            "best_for": "POS expecting barcode scanner input",
            "advantages": ["Transparent to POS", "No POS changes needed", "Standard protocol"],
            "setup": "HID barcode scanner emulation"
        }
    }
    
    print("🔌 POS System Connection Methods")
    print("=" * 60)
    print("Choose the best method for your POS system:\n")
    
    for method, details in methods.items():
        print(f"📱 {method}")
        print(f"   Description: {details['description']}")
        print(f"   Hardware: {details['hardware']}")
        print(f"   Best for: {details['best_for']}")
        print(f"   Advantages: {', '.join(details['advantages'])}")
        print(f"   Setup: {details['setup']}")
        print()
    
    return methods

def create_bluetooth_pos():
    """Create Bluetooth POS connection"""
    
    bluetooth_code = '''#!/usr/bin/env python3
"""
Bluetooth POS Connection
Send barcodes via Bluetooth to POS devices
"""

import bluetooth
import time
import json

class BluetoothPOS:
    def __init__(self):
        self.connected_devices = []
        self.active_connection = None
    
    def scan_devices(self):
        """Scan for nearby Bluetooth devices"""
        print("🔍 Scanning for Bluetooth devices...")
        try:
            devices = bluetooth.discover_devices(duration=8, lookup_names=True)
            self.connected_devices = devices
            
            print(f"📱 Found {len(devices)} Bluetooth device(s):")
            for addr, name in devices:
                print(f"   {name} - {addr}")
            
            return devices
        except Exception as e:
            print(f"❌ Bluetooth scan failed: {e}")
            return []
    
    def connect_to_device(self, address):
        """Connect to specific Bluetooth device"""
        try:
            sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            sock.connect((address, 1))  # Port 1 for RFCOMM
            self.active_connection = sock
            print(f"✅ Connected to {address}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def send_barcode(self, barcode):
        """Send barcode via Bluetooth"""
        if not self.active_connection:
            print("❌ No active Bluetooth connection")
            return False
        
        try:
            message = f"{barcode}\\n"
            self.active_connection.send(message.encode())
            print(f"✅ Sent via Bluetooth: {barcode}")
            return True
        except Exception as e:
            print(f"❌ Bluetooth send failed: {e}")
            return False

if __name__ == "__main__":
    bt_pos = BluetoothPOS()
    devices = bt_pos.scan_devices()
    
    if devices:
        # Try to connect to first device
        addr, name = devices[0]
        if bt_pos.connect_to_device(addr):
            bt_pos.send_barcode("TEST123456789")
'''
    
    with open('bluetooth_pos.py', 'w') as f:
        f.write(bluetooth_code)
    
    print("✅ Created bluetooth_pos.py")

def create_web_pos():
    """Create Web-based POS interface"""
    
    web_pos_code = '''#!/usr/bin/env python3
"""
Web POS Interface
Web browser-based barcode display for POS systems
"""

from flask import Flask, render_template, jsonify
import threading
import time
from pathlib import Path

app = Flask(__name__)
latest_barcode = {"barcode": "Ready for scan...", "timestamp": ""}

@app.route('/')
def pos_display():
    """Main POS display page"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Web POS Display</title>
    <style>
        body { 
            background: black; 
            color: lime; 
            font-family: Arial, sans-serif; 
            text-align: center;
            margin: 0;
            padding: 20px;
        }
        .title { 
            font-size: 48px; 
            color: cyan; 
            margin-bottom: 30px;
        }
        .barcode { 
            font-size: 72px; 
            font-family: Courier, monospace; 
            margin: 50px 0;
            padding: 20px;
            border: 3px solid lime;
            display: inline-block;
            min-width: 400px;
        }
        .status { 
            font-size: 24px; 
            color: yellow; 
        }
        .flash { 
            background: darkgreen !important; 
            transition: background 0.3s;
        }
    </style>
</head>
<body>
    <div class="title">CALEFFI POS SYSTEM</div>
    <div id="barcode" class="barcode">Ready for scan...</div>
    <div id="status" class="status">Waiting for barcode...</div>
    
    <script>
        function updateDisplay() {
            fetch('/api/barcode')
                .then(response => response.json())
                .then(data => {
                    if (data.barcode && data.barcode !== "Ready for scan...") {
                        document.getElementById('barcode').textContent = data.barcode;
                        document.getElementById('status').textContent = 
                            `✅ Scanned: ${data.timestamp}`;
                        
                        // Flash effect
                        document.getElementById('barcode').classList.add('flash');
                        setTimeout(() => {
                            document.getElementById('barcode').classList.remove('flash');
                        }, 500);
                        
                        // Auto-clear after 8 seconds
                        setTimeout(() => {
                            document.getElementById('barcode').textContent = "Ready for scan...";
                            document.getElementById('status').textContent = "Waiting for barcode...";
                        }, 8000);
                    }
                })
                .catch(error => console.error('Error:', error));
        }
        
        // Check for updates every second
        setInterval(updateDisplay, 1000);
    </script>
</body>
</html>
    '''

@app.route('/api/barcode')
def get_barcode():
    """API endpoint to get latest barcode"""
    return jsonify(latest_barcode)

def monitor_barcodes():
    """Monitor barcode files and update web display"""
    global latest_barcode
    last_barcode = ""
    
    while True:
        try:
            barcode_files = [
                '/tmp/pos_barcode.txt',
                '/tmp/latest_barcode.txt',
                '/tmp/current_barcode.txt'
            ]
            
            for file_path in barcode_files:
                if Path(file_path).exists():
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read().strip()
                            if content and ':' in content:
                                barcode = content.split(':', 1)[1].strip()
                                if barcode and len(barcode) > 5 and barcode != last_barcode:
                                    last_barcode = barcode
                                    latest_barcode = {
                                        "barcode": barcode,
                                        "timestamp": time.strftime('%H:%M:%S')
                                    }
                                    print(f"🌐 Web POS: {barcode}")
                                    break
                    except:
                        pass
            
            time.sleep(1)
        except:
            time.sleep(1)

if __name__ == "__main__":
    # Start barcode monitoring in background
    monitor_thread = threading.Thread(target=monitor_barcodes, daemon=True)
    monitor_thread.start()
    
    print("🌐 Starting Web POS Display...")
    print("📱 Access at: http://[PI_IP]:5000")
    print("💻 Open this URL in any web browser on your POS device")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
'''
    
    with open('web_pos.py', 'w') as f:
        f.write(web_pos_code)
    
    print("✅ Created web_pos.py")

def create_network_pos():
    """Create Network POS connection"""
    
    network_code = '''#!/usr/bin/env python3
"""
Network POS Connection
Send barcodes over network to POS systems
"""

import socket
import requests
import json
import time

class NetworkPOS:
    def __init__(self):
        self.pos_endpoints = []
    
    def scan_network_pos(self):
        """Scan network for POS systems"""
        print("🔍 Scanning network for POS systems...")
        
        # Common POS IP ranges
        ip_ranges = ["192.168.1.", "192.168.0.", "10.0.0."]
        common_ports = [8080, 9100, 23, 80, 443, 3000, 5000]
        
        found_devices = []
        
        for ip_base in ip_ranges:
            for i in range(100, 111):  # Scan .100 to .110
                ip = f"{ip_base}{i}"
                
                for port in common_ports:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex((ip, port))
                        if result == 0:
                            found_devices.append(f"{ip}:{port}")
                            print(f"📍 Found: {ip}:{port}")
                        sock.close()
                    except:
                        pass
        
        self.pos_endpoints = found_devices
        return found_devices
    
    def send_via_http(self, ip, port, barcode):
        """Send barcode via HTTP POST"""
        try:
            url = f"http://{ip}:{port}/barcode"
            data = {"barcode": barcode, "timestamp": time.time()}
            
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                print(f"✅ HTTP sent to {ip}:{port} - {barcode}")
                return True
        except Exception as e:
            print(f"❌ HTTP failed {ip}:{port}: {e}")
        return False
    
    def send_via_tcp(self, ip, port, barcode):
        """Send barcode via raw TCP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((ip, port))
            
            message = f"{barcode}\\n"
            sock.send(message.encode())
            sock.close()
            
            print(f"✅ TCP sent to {ip}:{port} - {barcode}")
            return True
        except Exception as e:
            print(f"❌ TCP failed {ip}:{port}: {e}")
        return False
    
    def broadcast_barcode(self, barcode):
        """Send barcode to all found POS systems"""
        success_count = 0
        
        for endpoint in self.pos_endpoints:
            ip, port = endpoint.split(':')
            port = int(port)
            
            # Try HTTP first, then TCP
            if self.send_via_http(ip, port, barcode):
                success_count += 1
            elif self.send_via_tcp(ip, port, barcode):
                success_count += 1
        
        print(f"📊 Sent to {success_count}/{len(self.pos_endpoints)} POS systems")
        return success_count > 0

if __name__ == "__main__":
    net_pos = NetworkPOS()
    devices = net_pos.scan_network_pos()
    
    if devices:
        net_pos.broadcast_barcode("TEST123456789")
    else:
        print("❌ No network POS systems found")
'''
    
    with open('network_pos.py', 'w') as f:
        f.write(network_code)
    
    print("✅ Created network_pos.py")

def main():
    print("🔌 Complete POS Connection Methods Guide")
    print("=" * 60)
    
    # Show all connection methods
    methods = show_connection_methods()
    
    print("🛠️ Creating Additional Connection Tools...")
    print("=" * 60)
    
    # Create additional connection tools
    create_bluetooth_pos()
    create_web_pos() 
    create_network_pos()
    
    print("\n🎯 All POS Connection Methods Ready!")
    print("📁 Created Files:")
    print("   - bluetooth_pos.py (Bluetooth connection)")
    print("   - web_pos.py (Web browser interface)")
    print("   - network_pos.py (Network TCP/HTTP)")
    print("   - usb_pos_forwarder.py (USB HID - already created)")
    print("   - hdmi_pos_display.py (HDMI display - already created)")
    
    print("\n📋 Quick Setup Guide:")
    print("1. **USB HID**: python3 usb_pos_forwarder.py")
    print("2. **HDMI Display**: python3 hdmi_pos_display.py")
    print("3. **Web Interface**: python3 web_pos.py (access at http://PI_IP:5000)")
    print("4. **Network POS**: python3 network_pos.py")
    print("5. **Bluetooth**: python3 bluetooth_pos.py")
    
    print("\n💡 Recommendation by POS Type:")
    print("📱 **Modern POS Tablets**: USB HID or Web Interface")
    print("🖥️ **Desktop POS**: HDMI Display or USB HID")
    print("🏪 **Legacy Cash Registers**: Serial/Network")
    print("📲 **Mobile POS**: Bluetooth or Web Interface")
    print("☁️ **Cloud POS**: Network/API Integration")

if __name__ == "__main__":
    main()
