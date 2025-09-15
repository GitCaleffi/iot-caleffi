#!/usr/bin/env python3

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from database.local_storage import LocalStorage
from iot.hub_client import HubClient
from utils.config import load_config
import time

def simulate_barcode_scan(barcode):
    """Simulate a barcode scan and process it"""
    print(f"🔍 Simulating barcode scan: {barcode}")
    
    # Initialize local storage
    local_db = LocalStorage()
    
    # Get or create device ID
    device_id = local_db.get_device_id()
    if not device_id:
        # Auto-generate device ID from MAC address
        import subprocess
        try:
            result = subprocess.run(['cat', '/sys/class/net/*/address'], 
                                  capture_output=True, text=True, shell=True)
            if result.stdout:
                mac = result.stdout.strip().split('\n')[0].replace(':', '')[-8:]
                device_id = f"pi-{mac}"
                local_db.save_device_id(device_id)
                print(f"✅ Auto-registered device: {device_id}")
        except:
            device_id = "test-device-simulator"
            local_db.save_device_id(device_id)
            print(f"✅ Using fallback device ID: {device_id}")
    
    # Save scan locally
    timestamp = local_db.save_scan(device_id, barcode, 1)
    print(f"💾 Saved scan locally: {device_id}, {barcode}")
    
    # Try to send to IoT Hub
    try:
        config = load_config()
        devices = config.get("iot_hub", {}).get("devices", {})
        
        if device_id in devices:
            connection_string = devices[device_id].get("connection_string")
            
            if connection_string and "YOUR_DEVICE_SPECIFIC_KEY_HERE" not in connection_string:
                hub_client = HubClient(connection_string, device_id)
                if hub_client.connect():
                    success = hub_client.send_message(barcode, device_id)
                    if success:
                        print("✅ Sent to IoT Hub successfully")
                        local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                    else:
                        print("❌ Failed to send to IoT Hub")
                else:
                    print("❌ Failed to connect to IoT Hub")
            else:
                print("⚠️ Invalid or missing IoT Hub connection string")
        else:
            print(f"⚠️ Device {device_id} not found in IoT Hub config")
            
    except Exception as e:
        print(f"❌ IoT Hub error: {e}")
    
    print("=" * 50)

def main():
    """Main function to simulate barcode scans"""
    print("🔍 Barcode Scanner Simulator")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        # Use barcode from command line
        barcode = sys.argv[1]
        simulate_barcode_scan(barcode)
    else:
        # Interactive mode
        print("Enter barcodes to simulate (Ctrl+C to exit):")
        try:
            while True:
                barcode = input("📱 Barcode: ").strip()
                if barcode:
                    simulate_barcode_scan(barcode)
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Simulator stopped")

if __name__ == "__main__":
    main()
