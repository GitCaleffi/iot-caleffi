#!/usr/bin/env python3
"""
Send registration notifications to frontend for both devices
"""

import requests
import json
from datetime import datetime

def send_registration_notification(device_id):
    """Send registration notification to frontend API"""
    try:
        url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        
        # Send registration notification
        payload = {
            "deviceId": device_id,
            "messageType": "device_registration",
            "action": "register",
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"📝 Sending registration notification for device: {device_id}")
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
            print(f"✅ Registration notification sent successfully for {device_id}")
            return True
        else:
            print(f"❌ Registration notification failed for {device_id}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error sending registration notification for {device_id}: {e}")
        return False

def main():
    """Send registration notifications for both devices"""
    devices = ["149f33d4a830", "67033051bf54"]
    
    print("🚀 Sending registration notifications to frontend...")
    
    for device_id in devices:
        success = send_registration_notification(device_id)
        if success:
            print(f"✅ {device_id}: Registration notification sent")
        else:
            print(f"❌ {device_id}: Registration notification failed")
        print("-" * 50)
    
    print("🏁 Registration notification process complete")

if __name__ == "__main__":
    main()