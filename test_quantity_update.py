#!/usr/bin/env python3
"""
Test script to verify quantity update functionality for already registered devices
"""

import sys
import os
from pathlib import Path
import logging

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_quantity_update():
    """Test quantity update for an already registered device"""
    
    print("🔧 Testing Quantity Update for Already Registered Device")
    print("=" * 60)
    
    try:
        # Import the necessary modules
        from utils.dynamic_device_manager import device_manager
        from database.local_storage import LocalStorage
        from api.api_client import ApiClient
        from utils.config import load_config
        from utils.dynamic_registration_service import get_dynamic_registration_service
        from iot.hub_client import HubClient
        from datetime import datetime, timezone
        
        # Use a device that should already be registered
        test_device_id = "5356a1840b0e"  # This was registered in our previous test
        test_barcode = "1234567890123"  # Different barcode for quantity update
        
        print(f"\n🧪 Testing quantity update for device: {test_device_id}")
        print(f"📊 Testing with barcode: {test_barcode}")
        
        # Initialize components
        local_db = LocalStorage()
        api_client = ApiClient()
        
        # Check if device is registered
        print(f"\n🔍 Device registration status:")
        
        # Check dynamic device manager
        is_registered_dynamic = device_manager.is_device_registered(test_device_id)
        print(f"   - Dynamic manager: {is_registered_dynamic}")
        
        # Check local database
        registered_devices = local_db.get_registered_devices()
        found_in_local = False
        if registered_devices:
            for device in registered_devices:
                if device.get('device_id') == test_device_id:
                    found_in_local = True
                    print(f"   - Local database: {found_in_local} (registered at: {device.get('registered_at', 'Unknown')})")
                    break
        
        if not found_in_local:
            print(f"   - Local database: {found_in_local}")
        
        if not (is_registered_dynamic or found_in_local):
            print("⚠️ Device is not registered. Registering it first...")
            
            # Register the device first
            token = device_manager.generate_registration_token(test_device_id)
            device_info = {
                "registration_method": "test_registration",
                "auto_registered": True,
                "registration_time": datetime.now(timezone.utc).isoformat()
            }
            
            success, reg_message = device_manager.register_device(token, test_device_id, device_info)
            if success:
                local_db.save_device_id(test_device_id)
                local_db.save_device_registration(test_device_id, {
                    'device_id': test_device_id,
                    'registered_at': datetime.now().isoformat(),
                    'status': 'active'
                })
                print("   ✅ Device registered successfully")
            else:
                print(f"   ❌ Device registration failed: {reg_message}")
                return
        
        print(f"\n🚀 Testing quantity update process...")
        
        # Test API quantity update
        print("Step 1: Testing API quantity update...")
        api_result = api_client.send_barcode_scan(test_device_id, test_barcode, 1)
        if api_result.get("success", False):
            print("   ✅ API quantity update successful")
        else:
            print(f"   ⚠️ API quantity update failed: {api_result.get('message', 'Unknown error')}")
        
        # Test IoT Hub quantity update
        print("Step 2: Testing IoT Hub quantity update...")
        try:
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                device_connection_string = registration_service.register_device_with_azure(test_device_id)
                
                if device_connection_string:
                    hub_client = HubClient(device_connection_string)
                    
                    # Create quantity update message
                    quantity_message = {
                        "scannedBarcode": test_barcode,
                        "deviceId": test_device_id,
                        "quantity": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "messageType": "quantity_update"
                    }
                    
                    # Send message with the quantity update payload
                    success = hub_client.send_message(quantity_message, test_device_id)
                    if success:
                        print("   ✅ IoT Hub quantity update successful")
                    else:
                        print("   ❌ IoT Hub quantity update failed")
                else:
                    print("   ❌ Failed to get device connection string")
            else:
                print("   ⚠️ No IoT Hub configuration found")
        except Exception as e:
            print(f"   ❌ IoT Hub quantity update error: {str(e)}")
        
        print(f"\n🎉 Quantity update test completed!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_quantity_update()
