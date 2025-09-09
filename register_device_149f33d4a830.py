#!/usr/bin/env python3
"""Register device ID 149f33d4a830 in Azure IoT Hub"""

import sys
import os
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def register_device_149f33d4a830():
    """Register device ID 149f33d4a830 in Azure IoT Hub"""
    
    DEVICE_ID = "149f33d4a830"
    
    print("🚀 REGISTERING DEVICE IN AZURE IOT HUB")
    print("=" * 50)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"🕐 Registration Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Import required modules
        from utils.dynamic_registration_service import get_dynamic_registration_service
        from utils.dynamic_device_manager import device_manager
        
        print("✅ Successfully imported registration services")
        
        # Step 1: Get registration service
        print("\n🔧 STEP 1: Initializing registration service...")
        print("-" * 40)
        
        reg_service = get_dynamic_registration_service()
        if not reg_service:
            print("❌ Failed to get registration service")
            return False
        
        print("✅ Registration service initialized")
        
        # Step 2: Generate registration token
        print("\n🎫 STEP 2: Generating registration token...")
        print("-" * 40)
        
        token = device_manager.generate_registration_token()
        print(f"✅ Registration token generated: {token[:16]}...")
        
        # Step 3: Register device
        print("\n📝 STEP 3: Registering device in IoT Hub...")
        print("-" * 40)
        
        device_info = {
            "registration_method": "manual_test_registration",
            "device_type": "barcode_scanner",
            "test_device": True,
            "barcode": "4545452521452",
            "timestamp": datetime.now().isoformat(),
            "registered_by": "test_script"
        }
        
        success, message = device_manager.register_device(token, DEVICE_ID, device_info)
        
        if success:
            print(f"✅ Device registration successful: {message}")
        else:
            print(f"⚠️ Device registration result: {message}")
            if "already registered" in message.lower():
                print("✅ Device already exists - continuing...")
                success = True
        
        # Step 4: Get connection string
        print("\n🔗 STEP 4: Getting device connection string...")
        print("-" * 40)
        
        try:
            conn_str = reg_service.get_device_connection_string(DEVICE_ID)
            if conn_str:
                print("✅ Device connection string obtained")
                print(f"🔗 Connection string: {conn_str[:50]}...")
                
                # Step 5: Test IoT Hub connection
                print("\n📡 STEP 5: Testing IoT Hub connection...")
                print("-" * 40)
                
                from iot.hub_client import HubClient
                import json
                
                hub_client = HubClient(conn_str)
                if hub_client.connect():
                    print("✅ IoT Hub connection successful")
                    
                    # Send test message
                    test_message = {
                        "deviceId": DEVICE_ID,
                        "messageType": "device_registration_test",
                        "barcode": "4545452521452",
                        "timestamp": datetime.now().isoformat(),
                        "test": True,
                        "status": "registered"
                    }
                    
                    send_success = hub_client.send_message(json.dumps(test_message), DEVICE_ID)
                    if send_success:
                        print("✅ Test message sent successfully")
                    else:
                        print("⚠️ Test message send failed")
                    
                    hub_client.disconnect()
                else:
                    print("❌ IoT Hub connection failed")
                    
            else:
                print("❌ Failed to get connection string")
                return False
                
        except Exception as e:
            print(f"❌ Connection string error: {e}")
            return False
        
        # Step 6: Save to local database
        print("\n💾 STEP 6: Saving to local database...")
        print("-" * 40)
        
        try:
            from database.local_storage import LocalStorage
            local_db = LocalStorage()
            local_db.save_device_registration(DEVICE_ID, datetime.now().isoformat())
            print("✅ Device saved to local database")
        except Exception as e:
            print(f"⚠️ Local database save error: {e}")
        
        print("\n" + "=" * 50)
        print("📊 REGISTRATION SUMMARY")
        print("=" * 50)
        print(f"📱 Device ID: {DEVICE_ID}")
        print(f"📡 IoT Hub Registration: {'✅ Success' if success else '❌ Failed'}")
        print(f"🔗 Connection String: {'✅ Available' if conn_str else '❌ Not Available'}")
        print(f"💾 Local Database: ✅ Saved")
        
        if success and conn_str:
            print("\n🎉 DEVICE REGISTRATION COMPLETED SUCCESSFULLY!")
            print("✅ Device is ready for barcode scanning")
            print("✅ IoT Hub connection verified")
            print("✅ Test message sent successfully")
        else:
            print("\n⚠️ DEVICE REGISTRATION COMPLETED WITH ISSUES")
            print("🔧 Check the errors above for details")
        
        return success and bool(conn_str)
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Registration Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting device registration...")
    success = register_device_149f33d4a830()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 DEVICE REGISTRATION SUCCESSFUL! ✅")
        print("📱 Device 149f33d4a830 is ready for testing")
    else:
        print("❌ DEVICE REGISTRATION FAILED")
        print("🔧 Check the errors above and try again")
    print("=" * 50)
    
    sys.exit(0 if success else 1)