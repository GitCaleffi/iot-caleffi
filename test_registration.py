#!/usr/bin/env python3

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment_package/src directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from utils.config import load_config
from utils.dynamic_registration_service import get_dynamic_registration_service
from database.local_storage import LocalStorage
from iot.hub_client import HubClient

def test_device_registration():
    """Test device registration functionality"""
    
    # Use a new test device ID
    device_id = f"test-{int(datetime.now().timestamp())}"
    
    print("=" * 60)
    print("🧪 DEVICE REGISTRATION TEST")
    print("=" * 60)
    print(f"Device ID: {device_id}")
    print("Testing: Complete registration workflow")
    print("=" * 60)
    
    results = {
        "device_id": device_id,
        "config_loaded": False,
        "local_storage_init": False,
        "azure_registration": False,
        "local_db_save": False,
        "iot_hub_notification": False,
        "overall_success": False
    }
    
    try:
        # Step 1: Load configuration
        print(f"\n🔧 Step 1: Loading configuration...")
        config = load_config()
        results["config_loaded"] = True
        print("✅ Configuration loaded successfully")
        
        # Step 2: Initialize local storage
        print(f"\n🔧 Step 2: Initializing local storage...")
        local_db = LocalStorage()
        results["local_storage_init"] = True
        print("✅ Local storage initialized")
        
        # Step 3: Check if device already exists
        print(f"\n🔧 Step 3: Checking existing registrations...")
        registered_devices = local_db.get_registered_devices()
        device_exists = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_exists:
            print(f"⚠️ Device {device_id} already exists - using new ID")
            device_id = f"test-{int(datetime.now().timestamp())}-new"
            results["device_id"] = device_id
        
        print(f"✅ Using device ID: {device_id}")
        
        # Step 4: Register with Azure IoT Hub
        print(f"\n🔧 Step 4: Registering with Azure IoT Hub...")
        iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
        
        if not iot_hub_connection_string:
            print("❌ No IoT Hub connection string found")
            return results
            
        reg_service = get_dynamic_registration_service(iot_hub_connection_string)
        
        if not reg_service:
            print("❌ Failed to get dynamic registration service")
            return results
            
        device_connection_string = reg_service.register_device_with_azure(device_id)
        
        if device_connection_string:
            results["azure_registration"] = True
            print("✅ Device registered with Azure IoT Hub")
        else:
            print("❌ Failed to register device with Azure IoT Hub")
            return results
        
        # Step 5: Save to local database
        print(f"\n🔧 Step 5: Saving to local database...")
        local_db.save_device_registration(device_id, datetime.now(timezone.utc).isoformat())
        results["local_db_save"] = True
        print("✅ Device saved to local database")
        
        # Step 6: Send registration notification to IoT Hub
        print(f"\n🔧 Step 6: Sending registration notification...")
        hub_client = HubClient(device_connection_string)
        
        registration_message = {
            "messageType": "device_registration",
            "action": "register",
            "deviceId": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "registration_method": "test_registration",
            "status": "registered",
            "message": "Device registration test completed successfully"
        }
        
        success = hub_client.send_message(registration_message, device_id)
        
        if success:
            results["iot_hub_notification"] = True
            print("✅ Registration notification sent to IoT Hub")
        else:
            print("⚠️ Failed to send registration notification")
        
        # Step 7: Verify registration
        print(f"\n🔧 Step 7: Verifying registration...")
        updated_devices = local_db.get_registered_devices()
        device_found = any(device['device_id'] == device_id for device in updated_devices)
        
        if device_found:
            print("✅ Device found in local database")
        else:
            print("❌ Device not found in local database")
        
        # Overall success check
        results["overall_success"] = all([
            results["config_loaded"],
            results["local_storage_init"], 
            results["azure_registration"],
            results["local_db_save"],
            results["iot_hub_notification"]
        ])
        
        return results
        
    except Exception as e:
        print(f"❌ Error during registration test: {str(e)}")
        import traceback
        traceback.print_exc()
        return results

def print_test_summary(results):
    """Print test summary"""
    print(f"\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Device ID: {results['device_id']}")
    print(f"Configuration Loading: {'✅ PASS' if results['config_loaded'] else '❌ FAIL'}")
    print(f"Local Storage Init: {'✅ PASS' if results['local_storage_init'] else '❌ FAIL'}")
    print(f"Azure Registration: {'✅ PASS' if results['azure_registration'] else '❌ FAIL'}")
    print(f"Local DB Save: {'✅ PASS' if results['local_db_save'] else '❌ FAIL'}")
    print(f"IoT Hub Notification: {'✅ PASS' if results['iot_hub_notification'] else '❌ FAIL'}")
    print("=" * 60)
    
    if results["overall_success"]:
        print("🎉 OVERALL RESULT: ✅ REGISTRATION WORKING")
        print("✅ Device registration functionality is working correctly")
    else:
        print("💥 OVERALL RESULT: ❌ REGISTRATION FAILED")
        print("❌ Device registration has issues that need fixing")
    
    print("=" * 60)

if __name__ == "__main__":
    print("🚀 Starting device registration test...")
    results = test_device_registration()
    print_test_summary(results)
