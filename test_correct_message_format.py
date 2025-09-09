#!/usr/bin/env python3
"""Test correct message format for frontend API and IoT Hub"""

import sys
import os
import json
import requests
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def test_correct_message_format():
    """Test sending barcode with correct format to both API and IoT Hub"""
    
    DEVICE_ID = "149f33d4a830"
    BARCODE = "4545452521452"
    
    print("🧪 TESTING CORRECT MESSAGE FORMAT")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {BARCODE}")
    print()
    
    # Test 1: Send to Frontend API with correct format
    print("📡 STEP 1: Testing Frontend API...")
    print("-" * 30)
    
    api_success = test_frontend_api(DEVICE_ID, BARCODE)
    
    # Test 2: Send to IoT Hub with correct format
    print("\n📡 STEP 2: Testing IoT Hub...")
    print("-" * 30)
    
    iot_success = test_iot_hub(DEVICE_ID, BARCODE)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {BARCODE}")
    print(f"🌐 Frontend API: {'✅ Success' if api_success else '❌ Failed'}")
    print(f"📡 IoT Hub: {'✅ Success' if iot_success else '❌ Failed'}")
    
    if api_success and iot_success:
        print("\n🎉 BOTH SYSTEMS WORKING!")
        print("✅ Messages should appear on frontend")
        print("✅ Quantities should be updated")
    else:
        print("\n⚠️ ISSUES DETECTED")
        print("🔧 Check the errors above")
    
    return api_success and iot_success

def test_frontend_api(device_id, barcode):
    """Test sending to frontend API with correct format"""
    try:
        # Try the correct API endpoint for inventory updates
        api_urls = [
            "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId",
            "https://api2.caleffionline.it/api/v1/raspberry/barcodeScan",
            "https://iot.caleffionline.it/api/barcode-scan"
        ]
        
        # Correct payload format for inventory update
        payload = {
            "scannedBarcode": barcode,
            "deviceId": device_id,
            "quantity": 1,
            "timestamp": datetime.now().isoformat(),
            "messageType": "barcode_scan"
        }
        
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        for url in api_urls:
            try:
                print(f"🌐 Trying: {url}")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=15
                )
                
                print(f"📊 Response: {response.status_code}")
                print(f"📋 Body: {response.text[:200]}")
                
                if response.status_code == 200:
                    print(f"✅ SUCCESS with {url}")
                    return True
                else:
                    print(f"⚠️ Failed with {url}: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error with {url}: {e}")
                continue
        
        print("❌ All API endpoints failed")
        return False
        
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def test_iot_hub(device_id, barcode):
    """Test sending to IoT Hub with correct format"""
    try:
        from iot.hub_client import HubClient
        from utils.config import load_config
        
        # Load config to get connection string
        config = load_config()
        iot_hub_config = config.get("iot_hub", {})
        connection_string = iot_hub_config.get("connection_string")
        
        if not connection_string:
            print("❌ No IoT Hub connection string")
            return False
        
        # Parse hostname and create device connection string
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        hostname = parts.get('HostName')
        
        # Get device key from Azure IoT Hub Registry
        from azure.iot.hub import IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
        device = registry_manager.get_device(device_id)
        
        if not device:
            print(f"❌ Device {device_id} not found in IoT Hub")
            return False
        
        primary_key = device.authentication.symmetric_key.primary_key
        device_conn_str = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
        
        print(f"🔗 Device connection: {device_conn_str[:50]}...")
        
        # Create correct message format for IoT Hub
        message_data = {
            "scannedBarcode": barcode,
            "deviceId": device_id,
            "quantity": 1,
            "timestamp": datetime.now().isoformat(),
            "messageType": "barcode_scan",
            "action": "inventory_update"
        }
        
        print(f"📤 IoT Message: {json.dumps(message_data, indent=2)}")
        
        # Send to IoT Hub
        hub_client = HubClient(device_conn_str)
        
        if hub_client.connect():
            print("✅ IoT Hub connected")
            
            # Send the message directly without double-wrapping
            success = hub_client.send_message(message_data, device_id)
            
            if success:
                print("✅ Message sent to IoT Hub")
                hub_client.disconnect()
                return True
            else:
                print("❌ Failed to send message")
                hub_client.disconnect()
                return False
        else:
            print("❌ Failed to connect to IoT Hub")
            return False
            
    except Exception as e:
        print(f"❌ IoT Hub test error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting correct message format test...")
    success = test_correct_message_format()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 TEST PASSED - CORRECT FORMAT WORKING! ✅")
        print("📱 Check frontend for barcode scan updates")
        print("📊 Quantities should be updated")
    else:
        print("❌ TEST FAILED - FORMAT ISSUES DETECTED")
        print("🔧 Check the errors above")
    print("=" * 50)
    
    sys.exit(0 if success else 1)