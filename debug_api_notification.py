#!/usr/bin/env python3
"""
Debug script to test the API notification endpoint and identify the issue
"""

import requests
import json
from datetime import datetime, timezone

def test_api_notification():
    """Test the API notification endpoint to identify the issue"""
    
    # API details
    api_base_url = "https://api2.caleffionline.it/api/v1"
    auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NiwiZW1haWwiOiJhcnBpNUB5b3BtYWlsLmNvbSIsImN1c3RvbWVySWQiOiI4MjAwNDciLCJpYXQiOjE3NDIxODYzODF9.cijDSnyQhpjMC89oOmSQ10oCBJHT6nHjqADzGwhrxpM"
    
    # Test device data
    device_id = "7356a1840b0e"
    test_barcode = "TEST_7356a1840b0e_20250730"
    connection_string = "HostName=CaleffiIoT.azure-devices.net;DeviceId=7356a1840b0e;SharedAccessKey=test"
    
    print("Testing API notification endpoint...")
    print(f"Base URL: {api_base_url}")
    print(f"Device ID: {device_id}")
    print("=" * 60)
    
    # Test 1: Check if the endpoint exists
    endpoint = f"{api_base_url}/raspberry/deviceRegistered"
    print(f"Test 1: Testing endpoint: {endpoint}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": auth_token
    }
    
    payload = {
        "deviceId": device_id,
        "testBarcode": test_barcode,
        "connectionString": connection_string,
        "registrationTime": datetime.now(timezone.utc).isoformat(),
        "status": "successfully_registered",
        "message": f"Device {device_id} has been registered and is ready for use"
    }
    
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 40)
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Content Type: {response.headers.get('content-type', 'Not specified')}")
        print(f"Response Length: {len(response.content)} bytes")
        print(f"Raw Response: {response.text}")
        
        # Try to parse as JSON
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {str(e)}")
            print("Response is not valid JSON")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "=" * 60)
    
    # Test 2: Try alternative endpoints
    alternative_endpoints = [
        f"{api_base_url}/raspberry/notifications",
        f"{api_base_url}/notifications",
        f"{api_base_url}/device/register",
        f"{api_base_url}/raspberry/register"
    ]
    
    print("Test 2: Trying alternative endpoints...")
    
    for alt_endpoint in alternative_endpoints:
        print(f"\nTesting: {alt_endpoint}")
        try:
            response = requests.post(alt_endpoint, headers=headers, json=payload, timeout=10)
            print(f"Status: {response.status_code}")
            if response.status_code != 404:
                print(f"Response: {response.text[:200]}...")
        except Exception as e:
            print(f"Error: {str(e)}")
    
    print("\n" + "=" * 60)
    
    # Test 3: Try with minimal payload
    print("Test 3: Testing with minimal payload...")
    
    minimal_payload = {
        "deviceId": device_id,
        "message": "Registration successful! You're all set to get started.",
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    try:
        response = requests.post(endpoint, headers=headers, json=minimal_payload, timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        try:
            data = response.json()
            print(f"Parsed JSON: {json.dumps(data, indent=2)}")
        except json.JSONDecodeError:
            print("Response is not valid JSON")
            
    except Exception as e:
        print(f"Request Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("1. Check if the endpoint returns valid JSON")
    print("2. Verify the expected payload format")
    print("3. Check if authentication is working correctly")
    print("4. Look for alternative endpoints that might work")

if __name__ == "__main__":
    test_api_notification()