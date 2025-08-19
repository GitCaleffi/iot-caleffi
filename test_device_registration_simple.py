#!/usr/bin/env python3
"""
Simple test script to verify new device registration and IoT Hub messaging works correctly
This version doesn't use Gradio to avoid port conflicts
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

def test_device_registration_logic():
    """Test the core device registration logic without Gradio"""
    
    print("🔧 Testing Device Registration Logic")
    print("=" * 50)
    
    try:
        # Import the necessary modules
        from utils.dynamic_device_manager import device_manager
        from database.local_storage import LocalStorage
        from api.api_client import ApiClient
        from utils.config import load_config
        
        # Test with a completely new device ID
        test_device_id = "5356a1840b0e"
        test_barcode = "8968456598745"
        
        print(f"\n🧪 Testing new device registration for device: {test_device_id}")
        print(f"📊 Testing with barcode: {test_barcode}")
        
        # Initialize components
        local_db = LocalStorage()
        api_client = ApiClient()
        
        # Clear any existing registration for this test device
        if device_manager.is_device_registered(test_device_id):
            print(f"⚠️  Device {test_device_id} already exists in dynamic manager - removing for test")
            with device_manager.lock:
                if test_device_id in device_manager.device_cache:
                    del device_manager.device_cache[test_device_id]
                    device_manager.save_device_config()
        
        print(f"\n🔍 Initial device registration status:")
        print(f"   - Dynamic manager: {device_manager.is_device_registered(test_device_id)}")
        
        # Check local database
        registered_devices = local_db.get_registered_devices()
        found_in_local = False
        if registered_devices:
            for device in registered_devices:
                if device.get('device_id') == test_device_id:
                    found_in_local = True
                    break
        print(f"   - Local database: {found_in_local}")
        
        # Test device registration process
        print(f"\n🚀 Testing device registration process...")
        
        # Step 1: Generate registration token
        print("Step 1: Generating registration token...")
        token = device_manager.generate_registration_token(test_device_id)
        print(f"   ✅ Token generated: {token}")
        
        # Step 2: Register device
        print("Step 2: Registering device...")
        device_info = {
            "registration_method": "test_registration",
            "online_at_registration": api_client.is_online(),
            "user_agent": "Test Script v1.0",
            "auto_registered": True,
            "registration_time": "2025-08-19T12:37:00Z"
        }
        
        success, reg_message = device_manager.register_device(token, test_device_id, device_info)
        print(f"   Registration result: {success}")
        print(f"   Message: {reg_message}")
        
        if success:
            print("   ✅ Device registered successfully in dynamic manager")
            
            # Step 3: Save to local database
            print("Step 3: Saving to local database...")
            local_db.save_device_id(test_device_id)
            local_db.save_device_registration(test_device_id, {
                'device_id': test_device_id,
                'registered_at': '2025-08-19T12:37:00Z',
                'status': 'active'
            })
            print("   ✅ Device saved to local database")
            
            # Step 4: Test API registration (if online)
            print("Step 4: Testing API registration...")
            if api_client.is_online():
                api_result = api_client.register_device(test_device_id)
                if api_result.get("success", False):
                    print(f"   ✅ API registration successful: {api_result.get('message')}")
                else:
                    print(f"   ⚠️ API registration failed: {api_result.get('message')}")
            else:
                print("   ⚠️ System is offline - skipping API registration")
            
            # Step 5: Test IoT Hub registration message
            print("Step 5: Testing IoT Hub registration message...")
            try:
                from utils.config import load_config
                from utils.dynamic_registration_service import get_dynamic_registration_service
                from iot.hub_client import HubClient
                from datetime import datetime, timezone
                import json
                
                config = load_config()
                if config and config.get("iot_hub", {}).get("connection_string"):
                    iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                    registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                    
                    if registration_service:
                        device_connection_string = registration_service.register_device_with_azure(test_device_id)
                        if device_connection_string:
                            hub_client = HubClient(device_connection_string)
                            
                            # Create NEW DEVICE registration message
                            registration_message = {
                                "deviceId": test_device_id,
                                "status": "new_device_registered",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "message": "New device registered during test",
                                "registration_method": "test_registration",
                                "scannedBarcode": test_barcode,
                                "messageType": "device_registration"
                            }
                            
                            # Send registration message to IoT Hub
                            reg_success = hub_client.send_message(registration_message, test_device_id)
                            if reg_success:
                                print("   ✅ IoT Hub registration message sent successfully")
                            else:
                                print("   ❌ Failed to send IoT Hub registration message")
                        else:
                            print("   ❌ Failed to get device connection string")
                    else:
                        print("   ❌ Failed to get registration service")
                else:
                    print("   ⚠️ No IoT Hub configuration found")
            except Exception as iot_error:
                print(f"   ❌ IoT Hub registration error: {iot_error}")
        
        else:
            print(f"   ❌ Device registration failed: {reg_message}")
        
        # Final verification
        print(f"\n✅ Final verification:")
        print(f"   - Dynamic manager: {device_manager.is_device_registered(test_device_id)}")
        
        # Check local database again
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
        
        print(f"\n🎉 Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_device_registration_logic()
