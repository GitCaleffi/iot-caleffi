#!/usr/bin/env python3
"""
Test frontend API registration to see what's happening at the API endpoint
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

def test_frontend_api_registration():
    """Test what happens when we send registration to frontend API"""
    print("🧪 Testing Frontend API Registration")
    print("=" * 50)
    
    test_device_id = "0ca02755d72a"
    api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🌐 API URL: {api_url}")
    print()
    
    print("STEP 1: Test Current Registration Format")
    print("-" * 40)
    
    # Current registration format
    current_payload = {
        "deviceId": test_device_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "device_registration"
    }
    
    print("📤 Sending current registration format:")
    print(json.dumps(current_payload, indent=2))
    
    try:
        response = requests.post(api_url, json=current_payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Registration API call succeeded")
        else:
            print("❌ Registration API call failed")
            
    except Exception as e:
        print(f"❌ API Error: {e}")
    
    print()
    print("STEP 2: Test Registration-Only Format")
    print("-" * 40)
    
    # Registration-only format
    reg_only_payload = {
        "deviceId": test_device_id,
        "registrationOnly": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": "Device registration - no inventory update"
    }
    
    print("📤 Sending registration-only format:")
    print(json.dumps(reg_only_payload, indent=2))
    
    try:
        response = requests.post(api_url, json=reg_only_payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Registration-only API call succeeded")
        else:
            print("❌ Registration-only API call failed")
            
    except Exception as e:
        print(f"❌ API Error: {e}")
    
    print()
    print("STEP 3: Check What API Actually Expects")
    print("-" * 40)
    
    # Test minimal payload
    minimal_payload = {
        "deviceId": test_device_id
    }
    
    print("📤 Sending minimal payload:")
    print(json.dumps(minimal_payload, indent=2))
    
    try:
        response = requests.post(api_url, json=minimal_payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Minimal API call succeeded")
        else:
            print("❌ Minimal API call failed")
            
    except Exception as e:
        print(f"❌ API Error: {e}")
    
    print()
    print("STEP 4: Test GET Request (Check if endpoint exists)")
    print("-" * 40)
    
    try:
        response = requests.get(api_url, timeout=30)
        print(f"GET Status Code: {response.status_code}")
        print(f"GET Response: {response.text}")
        
        if response.status_code == 405:
            print("✅ Endpoint exists (Method Not Allowed for GET)")
        elif response.status_code == 404:
            print("❌ Endpoint not found")
        else:
            print(f"ℹ️  Unexpected GET response: {response.status_code}")
            
    except Exception as e:
        print(f"❌ GET Error: {e}")
    
    print()
    print("=" * 50)
    print("🎯 FRONTEND API REGISTRATION ANALYSIS")
    print("=" * 50)
    print(f"API Endpoint: {api_url}")
    print(f"Device: {test_device_id}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')} IST")
    print()
    print("🔍 ANALYSIS:")
    print("1. Check which payload format works")
    print("2. Verify if API creates inventory records")
    print("3. Determine safe registration format")
    print()
    print("💡 SOLUTION:")
    print("- If API always creates inventory, keep it disabled")
    print("- If we find safe format, we can re-enable with that format")
    print("- Registration data should appear in your frontend logs")

if __name__ == "__main__":
    test_frontend_api_registration()
