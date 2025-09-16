#!/usr/bin/env python3
"""
Test barcode scanning with specific device ID 7079fa7ab32e
"""

import sys
import os
import json
import time
from pathlib import Path

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def test_barcode_with_device_id():
    """Test sending barcode with device ID 7079fa7ab32e"""
    
    # Convert hex device ID to numeric
    hex_device_id = "7079fa7ab32e"
    numeric_device_id = str(int(hex_device_id, 16))  # 123669195698990
    device_id = f"device-{numeric_device_id}"
    
    print("🧪 Testing Barcode with Device ID 7079fa7ab32e")
    print("=" * 50)
    print(f"Original hex device ID: {hex_device_id}")
    print(f"Numeric equivalent:     {numeric_device_id}")
    print(f"Device ID format:       {device_id}")
    print()
    
    # Test barcode to send
    test_barcode = "1234567890123"
    
    try:
        # Import required modules
        from api.api_client import ApiClient
        from datetime import datetime
        
        # Load config
        config_path = Path("/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src/device_config.json")
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        print("📡 Testing API Client...")
        # Test API client
        api_client = ApiClient()
        api_result = api_client.send_barcode_scan(device_id, test_barcode)
        print(f"API Result: {'✅ Success' if api_result.get('success') else '❌ Failed'}")
        if not api_result.get('success'):
            print(f"   Error: {api_result.get('message')}")
        
        print("\n🌐 Testing IoT Hub Message Creation...")
        # Create IoT Hub message data (without actual sending due to mock connection)
        message_data = {
            "messageType": "barcode_scan",
            "deviceId": device_id,
            "barcode": test_barcode,
            "timestamp": datetime.now().isoformat(),
            "quantity": 1
        }
        print(f"IoT Hub Message: ✅ Created successfully")
        print(f"   Message: {json.dumps(message_data, indent=2)}")
        
        print(f"\n📊 Test Summary:")
        print(f"Device ID: {device_id}")
        print(f"Test Barcode: {test_barcode}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        print(f"\n💡 To use with real USB scanner:")
        print(f"1. Create numeric barcode: {numeric_device_id}")
        print(f"2. Scan it to register device as: {device_id}")
        print(f"3. Then scan any barcodes for processing")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_barcode_with_device_id()
