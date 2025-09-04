#!/usr/bin/env python3

import json
import requests
from datetime import datetime

def handle_scan_with_auto_register(client, device_id, barcode, api_url):
    """Send scan and auto-register device if not registered"""
    
    # Try to send scan first
    payload = {
        "device_id": device_id,
        "barcode": barcode,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Publish scan
    client.publish("barcode/scan", json.dumps(payload))
    
    # If device not registered, the IoT server should respond with registration request
    # This would typically be handled by your IoT server's MQTT handler like this:
    
def iot_server_mqtt_handler(topic, message):
    """Example IoT server handler that auto-registers unknown devices"""
    
    if topic == "barcode/scan":
        data = json.loads(message)
        device_id = data["device_id"]
        
        # Check if device exists in database
        if not device_exists(device_id):
            # Auto-register the device
            register_device(device_id)
            print(f"Auto-registered device: {device_id}")
        
        # Process the scan
        process_barcode_scan(data)

def device_exists(device_id):
    """Check if device exists in your database"""
    # Your database check logic here
    pass

def register_device(device_id):
    """Register new device in your system"""
    # Your device registration logic here
    pass

def process_barcode_scan(scan_data):
    """Process the barcode scan"""
    # Your scan processing logic here
    pass
