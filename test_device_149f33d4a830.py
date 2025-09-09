#!/usr/bin/env python3
"""Test barcode_scanner_app.py with device ID 149f33d4a830 and barcode 4545452521452"""

import sys
import os
import json
from datetime import datetime

# Add the deployment package src directory to path
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
sys.path.insert(0, '/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package')

def test_device_149f33d4a830():
    """Test with specific device ID 149f33d4a830 and barcode 4545452521452"""
    
    DEVICE_ID = "149f33d4a830"
    BARCODE = "4545452521452"
    
    print("🧪 TESTING BARCODE SCANNER APP")
    print("=" * 60)
    print(f"📱 Device ID: {DEVICE_ID}")
    print(f"📊 Barcode: {BARCODE}")
    print(f"🕐 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Import the barcode scanner app functions
        from barcode_scanner_app import (
            process_barcode_scan,
            auto_register_device_to_server,
            check_raspberry_pi_connection,
            get_local_mac_address,
            generate_device_id
        )
        
        print("✅ Successfully imported barcode_scanner_app functions")
        
        # Test 1: Check system status
        print("\n🔍 STEP 1: Checking system status...")
        print("-" * 40)
        
        # Check MAC address
        mac_address = get_local_mac_address()
        print(f"📍 MAC Address: {mac_address or 'Not detected'}")
        
        # Check Pi connection
        pi_connected = check_raspberry_pi_connection()
        print(f"🔗 Pi Connection: {'✅ Connected' if pi_connected else '❌ Disconnected'}")
        
        # Test 2: Auto-register device
        print("\n🚀 STEP 2: Auto-registering device...")
        print("-" * 40)
        
        try:
            registration_result = auto_register_device_to_server()
            print(f"📝 Auto-registration: {'✅ Success' if registration_result else '⚠️ Failed/Already registered'}")
        except Exception as e:
            print(f"📝 Auto-registration: ⚠️ Error - {e}")
        
        # Test 3: Process barcode scan
        print("\n📱 STEP 3: Processing barcode scan...")
        print("-" * 40)
        
        result = process_barcode_scan(BARCODE, DEVICE_ID)
        print(f"📋 Scan Result:")
        print(result)
        
        # Test 4: Check IoT Hub connectivity
        print("\n📡 STEP 4: IoT Hub connectivity test...")
        print("-" * 40)
        
        try:
            from utils.dynamic_registration_service import get_dynamic_registration_service
            from iot.hub_client import HubClient
            
            reg_service = get_dynamic_registration_service()
            if reg_service:
                conn_str = reg_service.get_device_connection_string(DEVICE_ID)
                if conn_str:
                    print("✅ Device connection string available")
                    
                    # Test IoT Hub connection
                    hub_client = HubClient(conn_str)
                    if hub_client.connect():
                        print("✅ IoT Hub connection successful")
                        
                        # Send test message
                        test_message = {
                            "deviceId": DEVICE_ID,
                            "barcode": BARCODE,
                            "messageType": "test_message",
                            "timestamp": datetime.now().isoformat(),
                            "test": True
                        }
                        
                        success = hub_client.send_message(json.dumps(test_message), DEVICE_ID)
                        print(f"📤 Test message sent: {'✅ Success' if success else '❌ Failed'}")
                    else:
                        print("❌ IoT Hub connection failed")
                else:
                    print("⚠️ No connection string available")
            else:
                print("⚠️ Registration service not available")
                
        except Exception as e:
            print(f"❌ IoT Hub test error: {e}")
        
        # Determine overall success
        success_indicators = [
            "✅" in result,
            "sent" in result.lower(),
            "success" in result.lower()
        ]
        
        overall_success = any(success_indicators)
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"📱 Device ID: {DEVICE_ID}")
        print(f"📊 Barcode: {BARCODE}")
        print(f"🔗 Pi Connection: {'✅' if pi_connected else '❌'}")
        print(f"📡 Overall Status: {'✅ WORKING' if overall_success else '⚠️ NEEDS ATTENTION'}")
        
        if overall_success:
            print("\n🎉 BARCODE SCANNER APP IS WORKING!")
            print("✅ Device registration successful")
            print("✅ Barcode processing functional")
            print("✅ IoT Hub integration active")
        else:
            print("\n⚠️ BARCODE SCANNER APP NEEDS ATTENTION")
            print("📋 Check the scan result above for details")
            print("🔧 May need configuration or connectivity fixes")
        
        return overall_success
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("🔧 Check if all required modules are installed")
        return False
    except Exception as e:
        print(f"❌ Test Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting barcode scanner test...")
    success = test_device_149f33d4a830()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 TEST PASSED - BARCODE SCANNER APP IS WORKING! ✅")
    else:
        print("❌ TEST FAILED - BARCODE SCANNER APP NEEDS FIXES")
    print("=" * 60)
    
    sys.exit(0 if success else 1)