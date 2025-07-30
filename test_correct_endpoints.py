#!/usr/bin/env python3
"""
Test script to verify the correct API endpoints for device registration
"""

import requests
import json
from datetime import datetime, timezone

def test_correct_endpoints():
    """Test the correct API endpoints provided"""
    
    # API details
    api_base_url = "https://api2.caleffionline.it/api/v1"
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NiwiZW1haWwiOiJhcnBpNUB5b3BtYWlsLmNvbSIsImN1c3RvbWVySWQiOiI4MjAwNDciLCJpYXQiOjE3NDIxODYzODF9.cijDSnyQhpjMC89oOmSQ10oCBJHT6nHjqADzGwhrxpM"
    
    # Test device data
    device_id = "7356a1840b0e"
    
    print("Testing correct API endpoints...")
    print("=" * 60)
    
    # Test 1: saveDeviceId endpoint
    print("Test 1: Testing saveDeviceId endpoint")
    save_endpoint = f"{api_base_url}/raspberry/saveDeviceId"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_token
    }
    
    save_payload = {
        "scannedBarcode": device_id
    }
    
    print(f"Endpoint: {save_endpoint}")
    print(f"Payload: {json.dumps(save_payload, indent=2)}")
    
    try:
        response = requests.post(save_endpoint, headers=headers, json=save_payload, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {str(e)}")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 2: confirmRegistration endpoint
    print("Test 2: Testing confirmRegistration endpoint")
    confirm_endpoint = f"{api_base_url}/raspberry/confirmRegistration"
    
    confirm_payload = {
        "deviceId": device_id
    }
    
    print(f"Endpoint: {confirm_endpoint}")
    print(f"Payload: {json.dumps(confirm_payload, indent=2)}")
    
    try:
        response = requests.post(confirm_endpoint, headers=headers, json=confirm_payload, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {str(e)}")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 3: Test notification to iot.caleffionline.it
    print("Test 3: Testing notification to iot.caleffionline.it")
    notification_url = "https://iot.caleffionline.it/"
    
    # Try different notification approaches
    notification_endpoints = [
        "https://iot.caleffionline.it/api/notifications",
        "https://iot.caleffionline.it/notifications",
        "https://iot.caleffionline.it/api/device/registered",
        "https://iot.caleffionline.it/webhook"
    ]
    
    notification_payload = {
        "deviceId": device_id,
        "message": "Registration successful! You're all set to get started.",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "device_registration",
        "status": "success"
    }
    
    for endpoint in notification_endpoints:
        print(f"\nTesting: {endpoint}")
        try:
            response = requests.post(endpoint, headers=headers, json=notification_payload, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code != 404:
                print(f"Response: {response.text[:200]}...")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("1. Use /raspberry/saveDeviceId for initial device registration")
    print("2. Use /raspberry/confirmRegistration for confirming registration")
    print("3. Send notifications to iot.caleffionline.it (need to find correct endpoint)")

if __name__ == "__main__":
    test_correct_endpoints()