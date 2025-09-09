#!/usr/bin/env python3
"""
Send proper device registration messages to frontend
"""

import requests
import json
from datetime import datetime

def send_device_registration(device_id):
    """Send device registration using the format that shows up on frontend"""
    try:
        url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        
        # Send just the deviceId - this should register the device
        payload = {
            "deviceId": device_id
        }
        
        print(f"📝 Registering device: {device_id}")
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Response: {response.status_code}")
        print(f"Response text: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Device {device_id} registered successfully")
            return True
        else:
            print(f"❌ Device registration failed for {device_id}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error registering device {device_id}: {e}")
        return False

def main():
    """Register both devices with frontend"""
    devices = ["149f33d4a830", "67033051bf54"]
    
    print("🚀 Registering devices with frontend...")
    
    for device_id in devices:
        success = send_device_registration(device_id)
        if success:
            print(f"✅ {device_id}: Device registered")
        else:
            print(f"❌ {device_id}: Device registration failed")
        print("-" * 50)
    
    print("🏁 Device registration process complete")
    print("📊 Check https://iot.caleffionline.it/ to see registered devices")

if __name__ == "__main__":
    main()