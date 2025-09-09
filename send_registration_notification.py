#!/usr/bin/env python3
"""Send registration notification for existing devices"""

import sys
import os
import json
import requests
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def send_registration_notifications():
    """Send registration notifications for both devices"""
    
    devices = ["149f33d4a830", "67033051bf54"]
    
    print("📱 SENDING REGISTRATION NOTIFICATIONS")
    print("=" * 50)
    
    for device_id in devices:
        print(f"\n📱 Device: {device_id}")
        
        # Send registration notification
        url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {
            "deviceId": device_id,
            "registrationEvent": "device_registered",
            "timestamp": datetime.now().isoformat(),
            "messageType": "device_registration",
            "status": "registered"
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=15
            )
            
            if response.status_code == 200:
                print(f"✅ Registration notification sent for {device_id}")
            else:
                print(f"❌ Failed for {device_id}: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error for {device_id}: {e}")
    
    print(f"\n📱 Check https://iot.caleffionline.it/ for registration messages")

if __name__ == "__main__":
    send_registration_notifications()