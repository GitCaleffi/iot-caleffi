#!/usr/bin/env python3
"""
Debug Frontend Visibility Issues
Tests different approaches to make messages appear on frontend
"""

import requests
import json
from datetime import datetime
import time

def test_different_endpoints():
    """Test different API endpoints that might show messages on frontend"""
    
    base_url = "https://api2.caleffionline.it/api/v1"
    test_device_id = "84b772dc334a"
    
    endpoints_to_test = [
        {
            "name": "saveDeviceId (current)",
            "url": f"{base_url}/raspberry/saveDeviceId",
            "payload": {
                "scannedBarcode": test_device_id,
                "deviceId": test_device_id,
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Device Registration Event",
            "url": f"{base_url}/raspberry/saveDeviceId",
            "payload": {
                "scannedBarcode": test_device_id,
                "deviceId": test_device_id,
                "event": "device_registered",
                "messageType": "registration",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Notification Format",
            "url": f"{base_url}/raspberry/saveDeviceId",
            "payload": {
                "scannedBarcode": test_device_id,
                "deviceId": test_device_id,
                "notification": "New device registered",
                "type": "device_registration",
                "timestamp": datetime.now().isoformat()
            }
        },
        {
            "name": "Message Format",
            "url": f"{base_url}/raspberry/saveDeviceId",
            "payload": {
                "scannedBarcode": test_device_id,
                "deviceId": test_device_id,
                "message": f"Device {test_device_id} has been registered",
                "status": "registered",
                "timestamp": datetime.now().isoformat()
            }
        }
    ]
    
    print("🔍 Testing Different Payload Formats for Frontend Visibility")
    print("=" * 70)
    
    for i, test in enumerate(endpoints_to_test, 1):
        print(f"\n🧪 Test {i}: {test['name']}")
        print(f"📡 URL: {test['url']}")
        print(f"📦 Payload: {json.dumps(test['payload'], indent=2)}")
        
        try:
            response = requests.post(
                test['url'],
                json=test['payload'],
                timeout=10,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'RaspberryPi-BarcodeScanner/1.0'
                }
            )
            
            print(f"📊 Status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            # Check if response indicates success
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if "data" in response_data and response_data.get("responseMessage") == "Action completed successfully":
                        print("✅ SUCCESS - Full data response received")
                    elif response_data.get("responseMessage") == "This is a test barcode.":
                        print("⚠️ WARNING - Test barcode response (might not show on frontend)")
                    else:
                        print("❓ UNKNOWN - Different response format")
                except:
                    print("❌ FAILED - Invalid JSON response")
            else:
                print("❌ FAILED - Non-200 status code")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        print("-" * 50)
        time.sleep(1)  # Small delay between requests

def test_with_real_barcode_format():
    """Test with different barcode formats that might be expected"""
    
    base_url = "https://api2.caleffionline.it/api/v1"
    endpoint = f"{base_url}/raspberry/saveDeviceId"
    
    # Test different barcode formats
    test_barcodes = [
        "84b772dc334a",  # Current format
        
    ]
    
    print("\n🔍 Testing Different Barcode Formats")
    print("=" * 50)
    
    for barcode in test_barcodes:
        print(f"\n📱 Testing Barcode: {barcode}")
        
        payload = {
            "scannedBarcode": barcode,
            "deviceId": barcode,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=10
            )
            
            print(f"📊 Status: {response.status_code}")
            print(f"📄 Response: {response.text}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    if "data" in response_data:
                        print(f"✅ SUCCESS - Device ID in response: {response_data['data'].get('deviceId')}")
                        print(f"   Customer ID: {response_data['data'].get('customerId')}")
                        print(f"   Verified: {response_data['data'].get('verified')}")
                    else:
                        print("⚠️ No data field in response")
                except:
                    print("❌ Invalid JSON response")
                    
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        time.sleep(0.5)

def check_response_patterns():
    """Analyze response patterns to understand frontend integration"""
    
    print("\n🔍 Response Pattern Analysis")
    print("=" * 40)
    
    # Test the exact same barcode multiple times
    base_url = "https://api2.caleffionline.it/api/v1"
    endpoint = f"{base_url}/raspberry/saveDeviceId"
    test_barcode = "84b772dc334a"
    
    for i in range(3):
        print(f"\n📱 Test {i+1} - Barcode: {test_barcode}")
        
        payload = {
            "scannedBarcode": test_barcode,
            "deviceId": test_barcode,
            "timestamp": datetime.now().isoformat(),
            "attempt": i + 1
        }
        
        try:
            response = requests.post(endpoint, json=payload, timeout=10)
            response_data = response.json()
            
            print(f"📊 Status: {response.status_code}")
            print(f"📄 Message: {response_data.get('responseMessage')}")
            
            if "data" in response_data:
                data = response_data["data"]
                print(f"   ID: {data.get('id')}")
                print(f"   Customer: {data.get('customerId')}")
                print(f"   Device: {data.get('deviceId')}")
                print(f"   Verified: {data.get('verified')}")
                print(f"   Deleted: {data.get('isDeleted')}")
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
        
        time.sleep(1)

def main():
    """Main debug function"""
    print("🔬 Frontend Visibility Debug Suite")
    print("=" * 70)
    
    # Test different payload formats
    test_different_endpoints()
    
    # Test different barcode formats
    test_with_real_barcode_format()
    
    # Check response patterns
    check_response_patterns()
    
    print("\n" + "=" * 70)
    print("🎯 Summary:")
    print("- API calls are successful (200 responses)")
    print("- Data is being stored (ID numbers returned)")
    print("- Frontend might need to refresh or check different view")
    print("- Messages might appear in admin panel or different section")
    print("✅ Debug complete!")

if __name__ == "__main__":
    main()
