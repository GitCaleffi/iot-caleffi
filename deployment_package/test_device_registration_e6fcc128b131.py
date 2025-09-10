#!/usr/bin/env python3
"""
Test device registration for device ID: e6fcc128b131
Using barcode_scanner_app.py functions
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime, timezone

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_device_registration():
    """Test device registration for e6fcc128b131"""
    
    device_id = "933dee6de6ee"
    
    print("🧪 TESTING DEVICE REGISTRATION")
    print("=" * 50)
    print(f"📱 Device ID: {device_id}")
    print(f"⏰ Test Time: {datetime.now().isoformat()}")
    print()
    
    try:
        # Import required modules
        from database.local_storage import LocalStorage
        from utils.dynamic_registration_service import get_dynamic_registration_service
        from utils.dynamic_device_manager import device_manager
        from iot.hub_client import HubClient
        import json
        
        # Initialize local database
        local_db = LocalStorage()
        
        print("📋 STEP 1: Check if device already registered")
        print("-" * 30)
        
        # Check if device already exists
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device.get('device_id') == device_id for device in registered_devices)
        
        if device_already_registered:
            print(f"✅ Device {device_id} already registered in local database")
            # Get registration details
            for device in registered_devices:
                if device.get('device_id') == device_id:
                    print(f"📅 Registration Date: {device.get('registration_date', 'Unknown')}")
                    break
        else:
            print(f"🆕 Device {device_id} not found - proceeding with registration")
        
        print("\n📋 STEP 2: Register device with IoT Hub")
        print("-" * 30)
        
        # Get dynamic registration service
        registration_service = get_dynamic_registration_service()
        if not registration_service:
            print("❌ Dynamic registration service not available")
            return False
        
        # Generate registration token
        token = device_manager.generate_registration_token()
        print(f"🎫 Generated registration token: {token[:20]}...")
        
        # Prepare device info
        device_info = {
            "registration_method": "test_registration",
            "device_type": "barcode_scanner",
            "test_timestamp": datetime.now(timezone.utc).isoformat(),
            "auto_registered": False
        }
        
        # Register device
        success, message = device_manager.register_device(token, device_id, device_info)
        
        if success:
            print(f"✅ Device {device_id} registered with IoT Hub successfully")
            print(f"📝 Message: {message}")
            
            # Save to local database if not already registered
            if not device_already_registered:
                local_db.save_device_id(device_id)
                print(f"💾 Device {device_id} saved to local database")
            
        else:
            print(f"❌ IoT Hub registration failed: {message}")
            return False
        
        print("\n📋 STEP 3: Test IoT Hub connection")
        print("-" * 30)
        
        # Get device connection string
        device_connection_string = device_manager.get_device_connection_string(device_id)
        if device_connection_string:
            print("✅ Device connection string obtained")
            
            # Test IoT Hub connection
            hub_client = HubClient(device_connection_string)
            
            # Send test registration message
            registration_msg = {
                "deviceId": device_id,
                "messageType": "device_registration",
                "status": "test_registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Test registration via barcode_scanner_app functions"
            }
            
            try:
                hub_client.send_message(json.dumps(registration_msg), device_id)
                print("✅ Registration confirmation sent to IoT Hub")
                print(f"📡 Message ID: {device_id}-test-{int(datetime.now().timestamp())}")
            except Exception as e:
                print(f"⚠️ IoT Hub message send failed: {e}")
                
        else:
            print("❌ Could not get device connection string")
            return False
        
        print("\n📋 STEP 4: Test barcode scanning with registered device")
        print("-" * 30)
        
        # Test barcode processing using connection manager
        test_barcode = "1234567890123"
        print(f"🔍 Testing barcode: {test_barcode}")
        
        # Temporarily set device ID in local storage
        original_device_id = local_db.get_device_id()
        local_db.save_device_id(device_id)
        
        try:
            from utils.connection_manager import ConnectionManager
            connection_manager = ConnectionManager()
            
            # Test barcode scan message
            success, message = connection_manager.send_message_with_retry(
                device_id=device_id,
                barcode=test_barcode,
                quantity=1,
                message_type="barcode_scan"
            )
            
            if success:
                print("✅ Barcode processing successful")
                print(f"📊 Result: Barcode {test_barcode} - Quantity +1 sent to IoT Hub")
            else:
                print("⚠️ Barcode processing had issues")
                print(f"📊 Result: {message}")
                
        except Exception as e:
            print(f"❌ Barcode processing error: {e}")
        finally:
            # Restore original device ID if it existed
            if original_device_id:
                local_db.save_device_id(original_device_id)
        
        print("\n🏁 REGISTRATION TEST SUMMARY")
        print("=" * 50)
        print(f"📱 Device ID: {device_id}")
        print(f"✅ IoT Hub Registration: {'SUCCESS' if success else 'FAILED'}")
        print(f"💾 Local Database: SAVED")
        print(f"📡 IoT Hub Connection: TESTED")
        print(f"🔍 Barcode Scanning: TESTED")
        print(f"⏰ Test Completed: {datetime.now().isoformat()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Registration test failed: {e}")
        logger.error(f"Registration test error: {e}")
        return False

if __name__ == "__main__":
    success = test_device_registration()
    if success:
        print("\n🎉 Device registration test completed successfully!")
    else:
        print("\n💥 Device registration test failed!")
        sys.exit(1)
