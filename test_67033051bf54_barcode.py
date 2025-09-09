#!/usr/bin/env python3
"""Test barcode scanning with device 67033051bf54"""

import sys
import os
import json
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def test_barcode_with_device():
    """Test barcode scanning with device 67033051bf54"""
    
    DEVICE_ID = "67033051bf54"
    BARCODE = "5449000000996"  # Valid EAN-13
    
    print("🧪 TESTING BARCODE SCAN WITH REGISTERED DEVICE")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {BARCODE}")
    print()
    
    try:
        from barcode_scanner_app import process_barcode_scan
        
        print("📱 Processing barcode scan...")
        result = process_barcode_scan(BARCODE, DEVICE_ID)
        
        print("📋 Result:")
        print(result)
        
        # Also test API directly
        print("\n📡 Testing API directly...")
        from api.api_client import ApiClient
        
        api_client = ApiClient()
        api_result = api_client.send_barcode_scan(DEVICE_ID, BARCODE, 1)
        
        print(f"API Result: {api_result}")
        
        # Test IoT Hub directly
        print("\n📡 Testing IoT Hub directly...")
        test_iot_hub_direct(DEVICE_ID, BARCODE)
        
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_iot_hub_direct(device_id, barcode):
    """Test IoT Hub with correct message format"""
    try:
        from iot.hub_client import HubClient
        from utils.config import load_config
        from azure.iot.hub import IoTHubRegistryManager
        
        # Get device connection string
        config = load_config()
        connection_string = config.get("iot_hub", {}).get("connection_string")
        
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        hostname = parts.get('HostName')
        
        registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
        device = registry_manager.get_device(device_id)
        primary_key = device.authentication.symmetric_key.primary_key
        device_conn_str = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
        
        # Send correct message format
        message_data = {
            "scannedBarcode": barcode,
            "deviceId": device_id,
            "quantity": 1,
            "timestamp": datetime.now().isoformat(),
            "messageType": "barcode_scan"
        }
        
        hub_client = HubClient(device_conn_str)
        if hub_client.connect():
            success = hub_client.send_message(message_data, device_id)
            hub_client.disconnect()
            
            if success:
                print("✅ IoT Hub message sent successfully")
            else:
                print("❌ IoT Hub message failed")
        else:
            print("❌ IoT Hub connection failed")
            
    except Exception as e:
        print(f"❌ IoT Hub test error: {e}")

if __name__ == "__main__":
    print("🚀 Starting barcode test with registered device...")
    success = test_barcode_with_device()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 TEST COMPLETED! ✅")
        print("📱 Check frontend for updates")
    else:
        print("❌ TEST FAILED")
    print("=" * 50)