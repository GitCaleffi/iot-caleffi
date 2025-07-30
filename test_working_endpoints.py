#!/usr/bin/env python3
"""
Test script to find working API endpoints for notifications
"""

import requests
import json
from datetime import datetime, timezone

def test_working_endpoints():
    """Test the working API endpoints to find the correct one for notifications"""
    
    # API details
    api_base_url = "https://api2.caleffionline.it/api/v1"
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NiwiZW1haWwiOiJhcnBpNUB5b3BtYWlsLmNvbSIsImN1c3RvbWVySWQiOiI4MjAwNDciLCJpYXQiOjE3NDIxODYzODF9.cijDSnyQhpjMC89oOmSQ10oCBJHT6nHjqADzGwhrxpM"
    
    # Test device data
    device_id = "7356a1840b0e"
    test_barcode = "TEST_7356a1840b0e_20250730"
    
    print("Testing working API endpoints...")
    print("=" * 60)
    
    # Test 1: The working saveDeviceId endpoint
    print("Test 1: Testing the working saveDeviceId endpoint")
    endpoint = f"{api_base_url}/raspberry/saveDeviceId"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_token
    }
    
    # Test with device registration notification payload
    notification_payload = {
        "scannedBarcode": device_id,
        "notificationType": "device_registration",
        "notificationMessage": "Registration successful! You're all set to get started.",
        "notificationDate": datetime.now().strftime("%Y-%m-%d"),
        "testBarcode": test_barcode,
        "registrationStatus": "success",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {json.dumps(notification_payload, indent=2)}")
    
    try:
        response = requests.post(endpoint, headers=headers, json=notification_payload, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Content Type: {response.headers.get('content-type', 'Not specified')}")
        print(f"Raw Response: {response.text}")
        
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {str(e)}")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 2: Try with just the device ID (original working format)
    print("Test 2: Testing with original working format")
    
    original_payload = {
        "scannedBarcode": device_id
    }
    
    print(f"Payload: {json.dumps(original_payload, indent=2)}")
    
    try:
        response = requests.post(endpoint, headers=headers, json=original_payload, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Raw Response: {response.text}")
        
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {str(e)}")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 3: Check if there are other raspberry endpoints
    print("Test 3: Testing other potential raspberry endpoints")
    
    potential_endpoints = [
        f"{api_base_url}/raspberry/notify",
        f"{api_base_url}/raspberry/message",
        f"{api_base_url}/raspberry/status",
        f"{api_base_url}/raspberry/update"
    ]
    
    test_payload = {
        "deviceId": device_id,
        "message": "Registration successful! You're all set to get started.",
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    for test_endpoint in potential_endpoints:
        print(f"\nTesting: {test_endpoint}")
        try:
            response = requests.post(test_endpoint, headers=headers, json=test_payload, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code != 404:
                print(f"Response: {response.text[:200]}...")
                try:
                    data = response.json()
                    print(f"JSON: {json.dumps(data, indent=2)}")
                except:
                    pass
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("1. Use the working /raspberry/saveDeviceId endpoint")
    print("2. Include notification data in the payload")
    print("3. Handle the response appropriately")
    print("4. The endpoint might not return JSON for all requests")

if __name__ == "__main__":
    test_working_endpoints()