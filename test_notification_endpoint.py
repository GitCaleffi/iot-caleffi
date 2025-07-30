#!/usr/bin/env python3
"""
Test script to check the notification endpoint and find the correct way to send notifications
"""

import requests
import json
from datetime import datetime, timezone

def test_notification_endpoint():
    """Test different methods to send notifications"""
    
    # The endpoint you specified
    notification_endpoint = "https://iot.caleffionline.it/notifications"
    
    # Auth token from the API client
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NiwiZW1haWwiOiJhcnBpNUB5b3BtYWlsLmNvbSIsImN1c3RvbWVySWQiOiI4MjAwNDciLCJpYXQiOjE3NDIxODYzODF9.cijDSnyQhpjMC89oOmSQ10oCBJHT6nHjqADzGwhrxpM"
    
    # Test device
    device_id = "test_device_001"
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # Test payload
    notification_payload = {
        "deviceId": device_id,
        "message": "Registration successful! You're all set to get started.",
        "date": current_date,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "device_registration",
        "status": "success"
    }
    
    print("Testing notification endpoint...")
    print(f"Endpoint: {notification_endpoint}")
    print(f"Payload: {json.dumps(notification_payload, indent=2)}")
    print("=" * 60)
    
    # Test 1: POST with Authorization header
    print("Test 1: POST with Authorization header")
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_token
        }
        response = requests.post(notification_endpoint, headers=headers, json=notification_payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 2: POST with Bearer token
    print("Test 2: POST with Bearer token")
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}"
        }
        response = requests.post(notification_endpoint, headers=headers, json=notification_payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 3: GET request to see if endpoint exists
    print("Test 3: GET request to check endpoint")
    try:
        headers = {
            "Authorization": auth_token
        }
        response = requests.get(notification_endpoint, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 4: Try the main API base URL with notifications path
    print("Test 4: Try main API with notifications path")
    try:
        api_notification_endpoint = "https://api2.caleffionline.it/api/v1/notifications"
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_token
        }
        response = requests.post(api_notification_endpoint, headers=headers, json=notification_payload, timeout=10)
        print(f"Endpoint: {api_notification_endpoint}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "-" * 40 + "\n")
    
    # Test 5: Try raspberry notifications endpoint
    print("Test 5: Try raspberry notifications endpoint")
    try:
        raspberry_notification_endpoint = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_token
        }
        response = requests.post(raspberry_notification_endpoint, headers=headers, json=notification_payload, timeout=10)
        print(f"Endpoint: {raspberry_notification_endpoint}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("If any of the above tests returned a 200 status code,")
    print("that endpoint and method should be used for notifications.")
    print("If all failed, the notification endpoint might not be available")
    print("or might require different authentication/parameters.")

if __name__ == "__main__":
    test_notification_endpoint()