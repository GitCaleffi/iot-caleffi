#!/usr/bin/env python3
"""
Test Frontend API Payload Formats
Tests different payload formats to see what the frontend expects
"""

import requests
import json
from datetime import datetime

def test_api_payload_formats():
    """Test different payload formats for the frontend API"""
    
    base_url = "https://api2.caleffionline.it/api/v1"
    endpoint = f"{base_url}/raspberry/saveDeviceId"
    test_device_id = "892d8f1d00e5"
    
    print("🧪 Testing Frontend API Payload Formats")
    print("=" * 60)
    print(f"📡 Endpoint: {endpoint}")
    print(f"🆔 Test Device ID: {test_device_id}")
    print()
    
    # Test different payload formats
    test_payloads = [
        {
            "name": "Current Format (with messageType)",
            "payload": {
                "deviceId": test_device_id,
                "messageType": "device_registration",
                "action": "register",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Simple Format (deviceId only)",
            "payload": {
                "deviceId": test_device_id
            }
        },
        {
            "name": "Barcode Format",
            "payload": {
                "scannedBarcode": test_device_id
            }
        },
        {
            "name": "Combined Format",
            "payload": {
                "deviceId": test_device_id,
                "scannedBarcode": test_device_id,
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Registration Event Format",
            "payload": {
                "deviceId": test_device_id,
                "event": "device_registered",
                "barcode": test_device_id,
                "quantity": 1,
                "timestamp": datetime.now().isoformat()
            }
        }
    ]
    
    for i, test in enumerate(test_payloads, 1):
        print(f"🔬 Test {i}: {test['name']}")
        print(f"📦 Payload: {json.dumps(test['payload'], indent=2)}")
        
        try:
            response = requests.post(
                endpoint,
                json=test['payload'],
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"📊 Response: {response.status_code}")
            print(f"📄 Body: {response.text}")
            
            if response.status_code == 200:
                print("✅ SUCCESS")
            else:
                print("❌ FAILED")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        print("-" * 40)
        print()

def test_working_endpoint():
    """Test the endpoint that we know works from previous tests"""
    
    print("🔍 Testing Known Working Configuration")
    print("=" * 50)
    
    endpoint = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
    payload = {
        "deviceId": "892d8f1d00e5",
        "messageType": "device_registration", 
        "action": "register",
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"📡 Endpoint: {endpoint}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=10
        )
        
        print(f"📊 Status: {response.status_code}")
        print(f"📄 Response: {response.text}")
        
        # Try to parse response
        try:
            response_data = response.json()
            print(f"📋 Parsed Response: {json.dumps(response_data, indent=2)}")
        except:
            print("📋 Response is not JSON")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main test function"""
    print("🔬 Frontend API Testing Suite")
    print("=" * 60)
    
    # Test the known working configuration first
    test_working_endpoint()
    print()
    
    # Test different payload formats
    test_api_payload_formats()
    
    print("=" * 60)
    print("✅ Testing complete!")

if __name__ == "__main__":
    main()
