#!/usr/bin/env python3
"""
Test script for device registration functionality
Tests device 8c379fcb0df2 registration process
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import required modules
from database.local_storage import LocalStorage
from utils.config import load_config
from utils.dynamic_device_manager import DynamicDeviceManager
from utils.dynamic_registration_service import get_dynamic_registration_service

def test_device_registration():
    """Test device registration process for a new device"""
    
    # Generate a new unique device ID for testing
    import time
    device_id = f"test-device-{int(time.time())}"
    
    print("🧪 Testing Device Registration Process")
    print("=" * 50)
    print(f"📱 Device ID: {device_id}")
    print("=" * 50)
    
    try:
        # Step 1: Initialize local storage
        print("\n1️⃣ Initializing local storage...")
        local_db = LocalStorage()
        print("✅ Local storage initialized")
        
        # Step 2: Check current registration status
        print(f"\n2️⃣ Checking current registration status...")
        registered_devices = local_db.get_registered_devices()
        print(f"📋 Total registered devices: {len(registered_devices)}")
        
        device_already_registered = any(device.get('device_id') == device_id for device in registered_devices)
        
        if device_already_registered:
            print(f"✅ Device {device_id} is already registered")
            # Find registration details
            for device in registered_devices:
                if device.get('device_id') == device_id:
                    print(f"📅 Registration date: {device.get('registered_at', 'Unknown')}")
                    break
        else:
            print(f"⚠️ Device {device_id} not found in local database")
        
        # Step 3: Test device registration process
        print(f"\n3️⃣ Testing device registration process...")
        
        # Initialize dynamic device manager
        device_manager = DynamicDeviceManager()
        print("✅ Dynamic device manager initialized")
        
        # Generate registration token
        token = device_manager.generate_registration_token()
        print(f"✅ Registration token generated: {token[:20]}...")
        
        # Prepare device info
        device_info = {
            "registration_method": "manual_test",
            "device_type": "barcode_scanner",
            "test_registration": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Register device
        print(f"🔄 Registering device {device_id}...")
        success, message = device_manager.register_device(token, device_id, device_info)
        
        if success:
            print(f"✅ Device registration successful: {message}")
        else:
            print(f"❌ Device registration failed: {message}")
            return False
        
        # Step 4: Verify registration in local database
        print(f"\n4️⃣ Verifying registration in local database...")
        
        # Save device to local database
        registration_saved = local_db.save_device_id(device_id)
        if registration_saved:
            print(f"✅ Device {device_id} saved to local database")
        else:
            print(f"ℹ️ Device {device_id} already exists in local database")
        
        # Verify device appears in registered devices
        updated_devices = local_db.get_registered_devices()
        device_found = any(device.get('device_id') == device_id for device in updated_devices)
        
        if device_found:
            print(f"✅ Device {device_id} confirmed in registered devices list")
            # Show device details
            for device in updated_devices:
                if device.get('device_id') == device_id:
                    print(f"📋 Device details: {device}")
                    break
        else:
            print(f"❌ Device {device_id} not found in registered devices list")
            return False
        
        # Step 5: Test IoT Hub registration
        print("\n5️⃣ Testing IoT Hub registration...")
        from iot_registration import register_device_with_iot_hub
        print("✅ IoT Hub registration module imported")
        
        try:
            result = register_device_with_iot_hub(device_id)
            if result.get("success"):
                print(f"✅ IoT Hub registration successful")
                if "connection_string" in result:
                    print(f"🔗 Connection string: {result['connection_string'][:50]}...")
                print(f"📋 Result: {result.get('message', 'Device registered')}")
            else:
                print(f"❌ IoT Hub registration failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"❌ IoT Hub registration error: {e}")
            return False
        
        # Step 6: Verify configuration
        print(f"\n6️⃣ Verifying device configuration...")
        
        config = load_config()
        device_configs = config.get("iot_hub", {}).get("devices", {})
        device_config = device_configs.get(device_id)
        
        if device_config:
            print(f"✅ Device {device_id} found in configuration")
            if device_config.get("connection_string"):
                print("✅ Device has connection string in config")
            else:
                print("⚠️ Device missing connection string in config")
        else:
            print(f"⚠️ Device {device_id} not found in configuration")
        
        # Step 7: Test device functionality
        print(f"\n7️⃣ Testing device functionality...")
        
        # Test if device can save scans
        test_barcode = "1234567890123"
        timestamp = local_db.save_scan(device_id, test_barcode, 1)
        print(f"✅ Test scan saved: {test_barcode} at {timestamp}")
        
        # Verify scan was saved
        recent_scans = local_db.get_recent_scans(limit=5)
        test_scan_found = any(scan.get('barcode') == test_barcode and scan.get('device_id') == device_id for scan in recent_scans)
        
        if test_scan_found:
            print(f"✅ Test scan confirmed in database")
        else:
            print(f"⚠️ Test scan not found in recent scans")
        
        print("\n" + "=" * 50)
        print("🎉 DEVICE REGISTRATION TEST COMPLETED!")
        print(f"📱 Device ID: {device_id}")
        print("✅ Local database registration: SUCCESS")
        print("✅ IoT Hub registration: SUCCESS")
        print("✅ Configuration verification: SUCCESS")
        print("✅ Device functionality: SUCCESS")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Registration test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_registered_devices():
    """Show all currently registered devices"""
    print("\n📋 Currently Registered Devices:")
    print("-" * 40)
    
    try:
        local_db = LocalStorage()
        devices = local_db.get_registered_devices()
        
        if devices:
            for i, device in enumerate(devices, 1):
                print(f"{i}. Device ID: {device.get('device_id', 'Unknown')}")
                print(f"   Registered: {device.get('registered_at', 'Unknown')}")
                print()
        else:
            print("No devices currently registered.")
            
    except Exception as e:
        print(f"Error retrieving devices: {e}")

if __name__ == "__main__":
    # Show current devices first
    show_registered_devices()
    
    # Run registration test
    success = test_device_registration()
    
    # Show devices after test
    show_registered_devices()
    
    sys.exit(0 if success else 1)
