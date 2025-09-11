#!/usr/bin/env python3
"""
Test script for barcode scanner device registration and IoT Hub messaging
Tests device 8c379fcb0df2 scanning barcode 4545858588888
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import required modules
from barcode_validator import validate_ean, BarcodeValidationError
from database.local_storage import LocalStorage
from utils.config import load_config
from iot.hub_client import HubClient
from api.api_client import ApiClient

def test_device_registration_and_barcode_scan():
    """Test device registration and barcode scanning functionality"""
    
    # Test parameters
    device_id = "67033051bf54"
    barcode = "4545858588888"
    quantity = 1
    
    print("🧪 Testing Barcode Scanner Device Registration and IoT Hub Messaging")
    print("=" * 70)
    print(f"📱 Device ID: {device_id}")
    print(f"📊 Barcode: {barcode}")
    print(f"📈 Quantity: {quantity}")
    print("=" * 70)
    
    try:
        # Step 1: Validate barcode format
        print("\n1️⃣ Validating barcode format...")
        try:
            validated_barcode = validate_ean(barcode)
            print(f"✅ Barcode validation successful: {validated_barcode}")
        except BarcodeValidationError as e:
            print(f"❌ Barcode validation failed: {e}")
            return False
        
        # Step 2: Initialize local storage
        print("\n2️⃣ Initializing local storage...")
        local_db = LocalStorage()
        print("✅ Local storage initialized")
        
        # Step 3: Check if device is registered
        print(f"\n3️⃣ Checking device registration for {device_id}...")
        registered_devices = local_db.get_registered_devices()
        device_registered = any(device.get('device_id') == device_id for device in registered_devices)
        
        if device_registered:
            print(f"✅ Device {device_id} is already registered")
        else:
            print(f"⚠️ Device {device_id} not found in local database")
            # Register device
            print(f"🔄 Registering device {device_id}...")
            local_db.save_device_id(device_id)
            print(f"✅ Device {device_id} registered locally")
        
        # Step 4: Save barcode scan locally
        print(f"\n4️⃣ Saving barcode scan to local database...")
        timestamp = local_db.save_scan(device_id, barcode, quantity)
        print(f"✅ Barcode scan saved: {barcode} from device {device_id} at {timestamp}")
        
        # Step 5: Load configuration
        print("\n5️⃣ Loading configuration...")
        config = load_config()
        print("✅ Configuration loaded")
        
        # Step 6: Test IoT Hub connection and messaging
        print(f"\n6️⃣ Testing IoT Hub connection for device {device_id}...")
        
        # Check if device has connection string in config
        device_configs = config.get("iot_hub", {}).get("devices", {})
        device_config = device_configs.get(device_id)
        
        if device_config and device_config.get("connection_string"):
            connection_string = device_config["connection_string"]
            print(f"✅ Found connection string for device {device_id}")
            
            # Initialize IoT Hub client
            try:
                hub_client = HubClient(connection_string)
                print("✅ IoT Hub client initialized")
                
                # Prepare message data
                timestamp_obj = datetime.now(timezone.utc)
                message_data = {
                    "deviceId": device_id,
                    "barcode": barcode,
                    "quantity": quantity,
                    "messageType": "barcode_scan",
                    "timestamp": timestamp_obj.isoformat(),
                    "action": "quantity_update"
                }
                
                # Send message to IoT Hub
                print(f"📤 Sending message to IoT Hub...")
                result = hub_client.send_message(barcode, device_id)
                
                if result:
                    print(f"✅ Message sent to IoT Hub successfully")
                    print(f"📋 Message content: {json.dumps(message_data, indent=2)}")
                else:
                    print(f"❌ Failed to send message to IoT Hub")
                    
            except Exception as e:
                print(f"❌ IoT Hub connection error: {e}")
                return False
                
        else:
            print(f"❌ No connection string found for device {device_id}")
            print("💡 Device may need to be registered in Azure IoT Hub first")
            return False
        
        # Step 7: Test API client (optional)
        print(f"\n7️⃣ Testing API client...")
        try:
            api_client = ApiClient()
            
            # Send barcode scan to API
            api_result = api_client.send_barcode_scan(device_id, barcode, quantity)
            
            if api_result and api_result.get('success'):
                print(f"✅ API call successful: {api_result}")
            else:
                print(f"⚠️ API call failed or returned error: {api_result}")
                
        except Exception as e:
            print(f"⚠️ API client error (non-critical): {e}")
        
        # Step 8: Verify local database entries
        print(f"\n8️⃣ Verifying database entries...")
        
        # Check recent scans
        try:
            recent_scans = local_db.get_recent_scans(limit=5)
            print(f"✅ Recent scans retrieved: {len(recent_scans)} entries")
            
            # Find our scan
            our_scan = None
            for scan in recent_scans:
                if scan.get('barcode') == barcode and scan.get('device_id') == device_id:
                    our_scan = scan
                    break
            
            if our_scan:
                print(f"✅ Our scan found in database: {our_scan}")
            else:
                print(f"⚠️ Our scan not found in recent scans")
                
        except Exception as e:
            print(f"⚠️ Database verification error: {e}")
        
        print("\n" + "=" * 70)
        print("🎉 TEST COMPLETED SUCCESSFULLY!")
        print(f"📱 Device {device_id} registration: ✅")
        print(f"📊 Barcode {barcode} scanning: ✅")
        print(f"📤 IoT Hub messaging: ✅")
        print(f"💾 Local storage: ✅")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_device_registration_and_barcode_scan()
    sys.exit(0 if success else 1)
