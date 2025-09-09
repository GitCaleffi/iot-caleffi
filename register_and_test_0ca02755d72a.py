#!/usr/bin/env python3
"""
Register device 0ca02755d72a in IoT Hub and test message delivery
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def register_and_test_device():
    """Register device in IoT Hub and test message delivery"""
    print("🧪 Register and Test Device: 0ca02755d72a")
    print("=" * 50)
    
    test_device_id = "0ca02755d72a"
    test_barcode = "1252417854959"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Test Barcode: {test_barcode}")
    print()
    
    print("STEP 1: Register Device in IoT Hub")
    print("-" * 40)
    
    try:
        # Load config
        config_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        from utils.dynamic_registration_service import DynamicRegistrationService
        
        reg_service = DynamicRegistrationService(config)
        
        # Register device in IoT Hub
        print(f"🔄 Registering device {test_device_id} in Azure IoT Hub...")
        
        conn_str = reg_service.register_device_with_azure(test_device_id)
        success = conn_str is not None
        
        if success:
            print("✅ Device registered successfully in IoT Hub")
        else:
            print("⚠️  Device may already exist or registration had issues")
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        # Continue anyway - device might already exist
    
    print()
    print("STEP 2: Get Device Connection String")
    print("-" * 40)
    
    try:
        conn_str = reg_service.get_device_connection_string(test_device_id)
        
        if conn_str:
            print("✅ Device connection string obtained")
            # Extract hub name
            if 'HostName=' in conn_str:
                hub_name = conn_str.split('HostName=')[1].split(';')[0]
                print(f"🏢 Hub: {hub_name}")
                print(f"📱 Device: {test_device_id}")
        else:
            print("❌ Failed to get device connection string")
            return
            
    except Exception as e:
        print(f"❌ Connection string error: {e}")
        return
    
    print()
    print("STEP 3: Test Message Sending")
    print("-" * 40)
    
    try:
        from iot.hub_client import HubClient
        
        print("🔌 Creating IoT Hub client...")
        hub_client = HubClient(conn_str)
        
        print("🔗 Connecting to IoT Hub...")
        if hub_client.connect():
            print("✅ Connected successfully")
        else:
            print("❌ Connection failed")
            return
        
        # Create test message
        current_time = datetime.now(timezone.utc)
        test_message = {
            "messageType": "device_test",
            "deviceId": test_device_id,
            "testBarcode": test_barcode,
            "timestamp": current_time.isoformat(),
            "testNote": "NEW DEVICE TEST - First message from 0ca02755d72a",
            "localTime": datetime.now().strftime("%H:%M:%S IST"),
            "utcTime": current_time.strftime("%H:%M:%S UTC")
        }
        
        print("📤 Sending test message:")
        print(json.dumps(test_message, indent=2))
        
        success = hub_client.send_message(test_message, test_device_id)
        
        if success:
            print("✅ Message sent successfully!")
            print(f"🕐 Local time: {datetime.now().strftime('%H:%M:%S')} IST")
            print(f"🕐 UTC time: {current_time.strftime('%H:%M:%S')} UTC")
        else:
            print("❌ Message sending failed")
            
    except Exception as e:
        print(f"❌ Send error: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
    
    print()
    print("STEP 4: Verify Message Queue")
    print("-" * 40)
    
    try:
        from database.local_storage import LocalStorage
        local_db = LocalStorage()
        
        unsent_messages = local_db.get_unsent_messages() or []
        device_messages = []
        
        for msg in unsent_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                if test_device_id in str(msg_data) or test_barcode in str(msg_data):
                    device_messages.append(msg_data)
            except:
                pass
        
        print(f"📊 Total unsent messages: {len(unsent_messages)}")
        print(f"📊 Messages for {test_device_id}: {len(device_messages)}")
        
        if device_messages:
            print("⚠️  Messages still in local queue:")
            for msg in device_messages[-2:]:
                msg_type = msg.get('messageType', 'unknown')
                timestamp = msg.get('timestamp', 'unknown')
                print(f"   • {msg_type} at {timestamp}")
            print("❌ Messages not delivered to IoT Hub")
        else:
            print("✅ No messages in queue - delivered successfully")
            
    except Exception as e:
        print(f"❌ Queue check error: {e}")
    
    print()
    print("=" * 50)
    print("🎯 DEVICE REGISTRATION AND TEST RESULTS")
    print("=" * 50)
    print(f"Device: {test_device_id}")
    print(f"Barcode: {test_barcode}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')} IST")
    print(f"UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
    print()
    print("🔍 CHECK AZURE IOT HUB PORTAL:")
    print(f"1. Go to IoT Hub: {hub_name if 'hub_name' in locals() else 'CaleffiIoT.azure-devices.net'}")
    print(f"2. Navigate to Devices → {test_device_id}")
    print("3. Check 'Device-to-cloud messages'")
    print("4. Look for messageType: 'device_test'")
    print(f"5. Look for testBarcode: '{test_barcode}'")
    print("6. Check around the UTC time shown above")

if __name__ == "__main__":
    register_and_test_device()
