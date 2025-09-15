#!/usr/bin/env python3

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from iot.hub_client import HubClient
from utils.config import load_config
from database.local_storage import LocalStorage
import time

def simulate_barcode_to_iot(barcode):
    """Simulate barcode scan and send directly to IoT Hub"""
    print(f"🔍 Simulating barcode scan: {barcode}")
    
    # Load config
    config = load_config()
    devices = config.get("iot_hub", {}).get("devices", {})
    
    device_id = "pi-c1323007"
    
    if device_id not in devices:
        print(f"❌ Device {device_id} not found in config")
        return
    
    connection_string = devices[device_id].get("connection_string")
    
    # Save locally first
    local_db = LocalStorage()
    timestamp = local_db.save_scan(device_id, barcode, 1)
    print(f"💾 Saved locally: {device_id}, {barcode}")
    
    # Send to IoT Hub
    try:
        hub_client = HubClient(connection_string, device_id)
        
        if hub_client.connect():
            print("✅ Connected to IoT Hub")
            
            success = hub_client.send_message(barcode, device_id)
            
            if success:
                print(f"✅ Barcode sent to IoT Hub: {barcode}")
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                print("✅ Marked as sent in local database")
            else:
                print("❌ Failed to send to IoT Hub")
        else:
            print("❌ Failed to connect to IoT Hub")
            
    except Exception as e:
        print(f"❌ IoT Hub error: {e}")

def main():
    if len(sys.argv) > 1:
        barcode = sys.argv[1]
        simulate_barcode_to_iot(barcode)
    else:
        print("Usage: python3 simulate_scan_to_iot.py <barcode>")
        print("Example: python3 simulate_scan_to_iot.py 1234567890123")

if __name__ == "__main__":
    main()
