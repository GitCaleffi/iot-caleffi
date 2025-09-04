#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta
import json

app = Flask(__name__)

# In-memory storage (use database in production)
devices = {}
scans = []

HTML_DASHBOARD = '''
<!DOCTYPE html>
<html>
<head>
    <title>Live Scanner Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial; margin: 20px; }
        .device { border: 1px solid #ccc; margin: 10px; padding: 15px; border-radius: 5px; }
        .online { background-color: #e8f5e8; }
        .offline { background-color: #ffe8e8; }
        .scan { background-color: #f0f8ff; margin: 5px 0; padding: 10px; border-radius: 3px; }
        h1 { color: #333; }
        .status { font-weight: bold; }
    </style>
</head>
<body>
    <h1>🔍 Live Barcode Scanner Dashboard</h1>
    
    <h2>Connected Devices ({{ device_count }})</h2>
    {% for device_id, device in devices.items() %}
    <div class="device {{ 'online' if device.is_online else 'offline' }}">
        <h3>{{ device_id }}</h3>
        <p><strong>IP:</strong> {{ device.ip }}</p>
        <p><strong>Platform:</strong> {{ device.platform }}</p>
        <p><strong>Last Seen:</strong> {{ device.last_seen }}</p>
        <p class="status">Status: {{ 'ONLINE' if device.is_online else 'OFFLINE' }}</p>
    </div>
    {% endfor %}
    
    <h2>Recent Scans ({{ scan_count }})</h2>
    {% for scan in recent_scans %}
    <div class="scan">
        <strong>{{ scan.barcode }}</strong> - Device: {{ scan.device_id }} - {{ scan.timestamp }}
    </div>
    {% endfor %}
</body>
</html>
'''

class Device:
    def __init__(self, device_id, data):
        self.device_id = device_id
        self.ip = data.get('ip', 'unknown')
        self.hostname = data.get('hostname', 'unknown')
        self.platform = data.get('platform', 'unknown')
        self.last_seen = datetime.utcnow()
        self.registered_at = datetime.utcnow()
    
    @property
    def is_online(self):
        return (datetime.utcnow() - self.last_seen).seconds < 60
    
    def update_heartbeat(self):
        self.last_seen = datetime.utcnow()

@app.route('/')
def dashboard():
    # Clean up old scans
    cutoff = datetime.utcnow() - timedelta(hours=1)
    recent_scans = [s for s in scans if s['timestamp_obj'] > cutoff]
    
    return render_template_string(HTML_DASHBOARD, 
                                devices=devices,
                                device_count=len(devices),
                                recent_scans=recent_scans[-20:],  # Last 20 scans
                                scan_count=len(recent_scans))

@app.route('/api/device/register', methods=['POST'])
def register_device():
    data = request.json
    device_id = data.get('device_id')
    
    if not device_id:
        return jsonify({'error': 'device_id required'}), 400
    
    # Register or update device
    devices[device_id] = Device(device_id, data)
    
    print(f"✓ Device registered: {device_id} ({data.get('ip', 'unknown')})")
    
    return jsonify({
        'status': 'registered',
        'device_id': device_id,
        'server_time': datetime.utcnow().isoformat()
    })

@app.route('/api/device/status', methods=['POST'])
def device_heartbeat():
    data = request.json
    device_id = data.get('device_id')
    
    if device_id in devices:
        devices[device_id].update_heartbeat()
        return jsonify({'status': 'ok'})
    
    return jsonify({'error': 'device not registered'}), 404

@app.route('/api/device/scan', methods=['POST'])
def receive_scan():
    data = request.json
    device_id = data.get('device_id')
    barcode = data.get('barcode')
    
    if not device_id or not barcode:
        return jsonify({'error': 'device_id and barcode required'}), 400
    
    # Store scan
    scan_record = {
        'device_id': device_id,
        'barcode': barcode,
        'timestamp': data.get('timestamp', datetime.utcnow().isoformat()),
        'timestamp_obj': datetime.utcnow(),
        'ip': data.get('ip', 'unknown')
    }
    
    scans.append(scan_record)
    
    # Update device heartbeat
    if device_id in devices:
        devices[device_id].update_heartbeat()
    
    print(f"📦 Scan received: {barcode} from {device_id}")
    
    return jsonify({
        'status': 'received',
        'scan_id': len(scans),
        'processed_at': datetime.utcnow().isoformat()
    })

@app.route('/api/devices')
def list_devices():
    device_list = []
    for device_id, device in devices.items():
        device_list.append({
            'device_id': device_id,
            'ip': device.ip,
            'hostname': device.hostname,
            'platform': device.platform,
            'last_seen': device.last_seen.isoformat(),
            'is_online': device.is_online,
            'registered_at': device.registered_at.isoformat()
        })
    
    return jsonify({'devices': device_list, 'count': len(device_list)})

@app.route('/api/scans')
def list_scans():
    return jsonify({'scans': scans[-50:], 'count': len(scans)})  # Last 50 scans

if __name__ == '__main__':
    print("🚀 Starting Live Scanner Server...")
    print("📊 Dashboard: http://localhost:3000")
    print("🔌 API Base: http://localhost:3000/api")
    
    app.run(host='0.0.0.0', port=3000, debug=True)
