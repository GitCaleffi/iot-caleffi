#!/usr/bin/env python3
"""Test sending device registration notification to frontend"""

import sys
import os
import json
import requests
from datetime import datetime

def test_registration_notification():
    """Test sending device registration notification"""
    
    DEVICE_ID = "67033051bf54"
    
    print("🧪 TESTING DEVICE REGISTRATION NOTIFICATION")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print()
    
    # Test registration notification
    url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
    payload = {
        "deviceId": DEVICE_ID,
        "registrationEvent": "device_registered",
        "timestamp": datetime.now().isoformat(),
        "messageType": "device_registration",
        "status": "registered"
    }
    
    print(f"📤 Sending registration notification...")
    print(f"🌐 URL: {url}")
    print(f"📋 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        
        print(f"📊 Response: {response.status_code}")
        print(f"📋 Body: {response.text}")
        
        if response.status_code == 200:
            print("✅ Registration notification sent successfully!")
            print("📱 Check https://iot.caleffionline.it/ for registration message")
            return True
        else:
            print("❌ Registration notification failed")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_registration_notification()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 REGISTRATION NOTIFICATION SENT! ✅")
        print("📱 Check frontend for registration message")
    else:
        print("❌ REGISTRATION NOTIFICATION FAILED")
    print("=" * 50)