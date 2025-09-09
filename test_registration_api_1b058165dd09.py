#!/usr/bin/env python3
"""
Test registration API directly with device ID 1b058165dd09
This will help identify if the registration API is working correctly
"""

import sys
import os
import json
import requests
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from api.api_client import ApiClient

def test_registration_api():
    """Test the registration API directly"""
    print("🧪 Testing Registration API with Device ID: 1b058165dd09")
    print("=" * 60)
    
    test_device_id = "1b058165dd09"
    
    print(f"📱 Device ID: {test_device_id}")
    print()
    
    # Initialize API client
    api_client = ApiClient()
    
    print("STEP 1: Test Direct API Registration Call")
    print("-" * 40)
    
    try:
        # Test the confirm_registration method directly
        result = api_client.confirm_registration(test_device_id)
        
        print("API Registration Result:")
        print(f"Success: {result.get('success', False)}")
        print(f"Message: {result.get('message', 'No message')}")
        print(f"Response: {result.get('response', 'No response')}")
        
        if result.get('success'):
            print("✅ Registration API call succeeded")
        else:
            print("❌ Registration API call failed")
            
    except Exception as e:
        print(f"❌ Error calling registration API: {e}")
    
    print()
    print("STEP 2: Test Raw HTTP Request to Registration Endpoint")
    print("-" * 40)
    
    try:
        # Test the raw HTTP request
        url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        
        # Test the fixed payload format
        payload = {
            "deviceId": test_device_id,
            "timestamp": datetime.now().isoformat(),
            "action": "device_registration"
        }
        
        print(f"URL: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(
            url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("✅ Raw HTTP registration request succeeded")
        else:
            print("❌ Raw HTTP registration request failed")
            
    except Exception as e:
        print(f"❌ Error with raw HTTP request: {e}")
    
    print()
    print("STEP 3: Test Old Payload Format (with scannedBarcode)")
    print("-" * 40)
    
    try:
        # Test the old problematic payload format
        old_payload = {
            "scannedBarcode": test_device_id,
            "deviceId": test_device_id,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"Old Payload: {json.dumps(old_payload, indent=2)}")
        
        response = requests.post(
            url,
            json=old_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("⚠️  Old format still works - this might be causing inventory drops!")
        else:
            print("✅ Old format rejected - good!")
            
    except Exception as e:
        print(f"❌ Error with old format test: {e}")
    
    print()
    print("STEP 4: Test Barcode Scan API (Should NOT be used for registration)")
    print("-" * 40)
    
    try:
        # Test what happens if we send a barcode scan
        scan_payload = {
            "deviceId": test_device_id,
            "barcode": "TEST123456789"
        }
        
        print(f"Scan Payload: {json.dumps(scan_payload, indent=2)}")
        
        response = requests.post(
            url,
            json=scan_payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print("⚠️  Barcode scan format works - this could cause inventory drops!")
        else:
            print("✅ Barcode scan format rejected")
            
    except Exception as e:
        print(f"❌ Error with barcode scan test: {e}")
    
    print()
    print("=" * 60)
    print("🎯 REGISTRATION API TEST SUMMARY")
    print("=" * 60)
    print(f"Device: {test_device_id}")
    print()
    print("Key findings:")
    print("1. Check which payload formats return 200 OK")
    print("2. Identify if any format is causing inventory drops")
    print("3. Verify the registration API endpoint behavior")
    print()
    print("🔍 Compare timestamps with inventory drop notifications!")

if __name__ == "__main__":
    test_registration_api()
