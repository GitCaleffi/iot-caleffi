#!/usr/bin/env python3
"""
Network POS Forwarder - Send barcodes to PC over network
Works without USB HID gadget mode
"""
import socket
import time
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import os

class POSServer(BaseHTTPRequestHandler):
    """HTTP server to receive barcode data and display for copying"""
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>POS Barcode Receiver</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            background: #f5f5f5;
        }
        .container { 
            max-width: 600px; 
            margin: 0 auto; 
            background: white; 
            padding: 30px; 
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .barcode { 
            font-size: 24px; 
            font-weight: bold; 
            padding: 15px; 
            background: #e8f4fd; 
            border: 2px solid #007cba;
            border-radius: 5px;
            margin: 20px 0;
            text-align: center;
            font-family: 'Courier New', monospace;
        }
        .status { 
            padding: 10px; 
            margin: 10px 0; 
            border-radius: 5px;
        }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
        button {
            background: #007cba;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 5px;
        }
        button:hover { background: #005a87; }
        #barcodeList { margin-top: 20px; }
        .barcode-item {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 POS Barcode Receiver</h1>
        <div class="status info">
            <strong>Status:</strong> Ready to receive barcodes from Raspberry Pi
        </div>
        
        <div id="latestBarcode" style="display:none;">
            <h3>Latest Barcode:</h3>
            <div class="barcode" id="barcodeDisplay"></div>
            <button onclick="copyBarcode()">📋 Copy to Clipboard</button>
            <button onclick="clearBarcode()">🗑️ Clear</button>
        </div>
        
        <div id="barcodeList">
            <h3>Received Barcodes:</h3>
            <div id="barcodes"></div>
        </div>
    </div>

    <script>
        let latestBarcode = '';
        
        function updateBarcode(barcode) {
            latestBarcode = barcode;
            document.getElementById('barcodeDisplay').textContent = barcode;
            document.getElementById('latestBarcode').style.display = 'block';
            
            // Add to list
            const barcodeList = document.getElementById('barcodes');
            const item = document.createElement('div');
            item.className = 'barcode-item';
            item.innerHTML = `
                <span style="font-family: 'Courier New', monospace; font-weight: bold;">${barcode}</span>
                <button onclick="copyToClipboard('${barcode}')">Copy</button>
            `;
            barcodeList.insertBefore(item, barcodeList.firstChild);
        }
        
        function copyBarcode() {
            copyToClipboard(latestBarcode);
        }
        
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert('Barcode copied to clipboard: ' + text);
            });
        }
        
        function clearBarcode() {
            document.getElementById('latestBarcode').style.display = 'none';
        }
        
        // Poll for new barcodes
        setInterval(() => {
            fetch('/api/latest')
                .then(response => response.json())
                .then(data => {
                    if (data.barcode && data.barcode !== latestBarcode) {
                        updateBarcode(data.barcode);
                    }
                })
                .catch(err => console.log('Polling error:', err));
        }, 1000);
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
                
                print(f"✅ Barcode received: {barcode}")
                
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'status': 'error', 'message': str(e)}
                self.wfile.write(json.dumps(response).encode())

class NetworkPOSForwarder:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.server_thread = None
        
    def start_server(self):
        """Start the POS receiver server"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), POSServer)
            self.server.latest_barcode = ''
            
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            print(f"🚀 POS Server started on port {self.port}")
            print(f"🌐 Open this URL on your PC: http://{self.get_local_ip()}:{self.port}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "localhost"
    
    def send_barcode(self, barcode):
        """Send barcode to the server (for local testing)"""
        try:
            import requests
            url = f"http://localhost:{self.port}/api/barcode"
            data = {'barcode': barcode}
            
            response = requests.post(url, json=data, timeout=5)
            if response.status_code == 200:
                print(f"✅ Barcode {barcode} sent to POS system")
                return True
            else:
                print(f"❌ Failed to send barcode: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending barcode: {e}")
            return False
    
    def stop_server(self):
        """Stop the server"""
        if self.server:
            self.server.shutdown()
            print("🛑 POS Server stopped")

def send_to_pos_network(barcode, server_ip="localhost", port=8080):
    """Send barcode to network POS system"""
    try:
        import requests
        url = f"http://{server_ip}:{port}/api/barcode"
        data = {'barcode': barcode}
        
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            print(f"📤 Barcode {barcode} sent to POS at {server_ip}:{port}")
            return True
        else:
            print(f"❌ POS send failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Network POS error: {e}")
        print(f"💡 Make sure POS server is running at {server_ip}:{port}")
        return False

def main():
    print("🚀 Network POS Forwarder")
    print("=" * 40)
    
    pos_forwarder = NetworkPOSForwarder()
    
    if pos_forwarder.start_server():
        ip = pos_forwarder.get_local_ip()
        print(f"\n✅ POS System Ready!")
        print(f"🌐 PC URL: http://{ip}:8080")
        print(f"📱 Mobile URL: http://{ip}:8080")
        print("\n📋 Instructions:")
        print("1. Open the URL above on your PC/phone browser")
        print("2. Barcodes will appear automatically when scanned")
        print("3. Click 'Copy to Clipboard' to copy barcode")
        print("4. Paste into your POS system")
        
        try:
            # Test with sample barcode
            print(f"\n🧪 Testing with barcode: 8053734093444")
            time.sleep(2)
            pos_forwarder.send_barcode("8053734093444")
            
            print(f"\n⌨️  Interactive mode (Ctrl+C to exit)")
            while True:
                barcode = input("Enter barcode: ").strip()
                if barcode:
                    pos_forwarder.send_barcode(barcode)
                    
        except KeyboardInterrupt:
            print(f"\n👋 Shutting down...")
            pos_forwarder.stop_server()

if __name__ == "__main__":
    main()
