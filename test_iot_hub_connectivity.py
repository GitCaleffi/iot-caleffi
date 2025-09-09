#!/usr/bin/env python3
"""
Test IoT Hub connectivity and message visibility using the correct approach
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def test_iot_hub_connectivity():
    """Test IoT Hub message delivery using the same method as the app"""
    print("🧪 Testing IoT Hub Message Visibility")
    print("=" * 50)
    
    test_device_id = "0ca02755d72a"
    test_barcode = "1252417854959"
    
    print(f"📱 Device ID: {test_device_id}")
    print(f"🏷️  Test Barcode: {test_barcode}")
    print()
    
    print("STEP 1: Generate Device Connection String")
    print("-" * 40)
    
    try:
        # Load config and create registration service
        config_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        from utils.dynamic_registration_service import DynamicRegistrationService
        
        reg_service = DynamicRegistrationService(config)
        conn_str = reg_service.get_device_connection_string(test_device_id)
        
        if conn_str:
            print("✅ Device connection string generated")
            # Extract hub name
            if 'HostName=' in conn_str:
                hub_name = conn_str.split('HostName=')[1].split(';')[0]
                print(f"🏢 Hub: {hub_name}")
                print(f"📱 Device: {test_device_id}")
        else:
            print("❌ Failed to generate device connection string")
            return
            
    except Exception as e:
        print(f"❌ Connection string error: {e}")
        return
    
    print()
    print("STEP 2: Test Message Sending (Same as App)")
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
        
        # Create test message with clear identifier
        current_time = datetime.now(timezone.utc)
        test_message = {
            "messageType": "visibility_test",
            "deviceId": test_device_id,
            "testBarcode": test_barcode,
            "timestamp": current_time.isoformat(),
            "testNote": "VISIBILITY TEST - Look for this message",
            "localTime": datetime.now().strftime("%H:%M:%S IST"),
            "utcTime": current_time.strftime("%H:%M:%S UTC")
        }
        
        print("📤 Sending visibility test message:")
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
    print("STEP 3: Check Local Message Queue")
    print("-" * 40)
    
    try:
        from database.local_storage import LocalStorage
        local_db = LocalStorage()
        
        # Check unsent messages
        unsent_messages = local_db.get_unsent_messages() or []
        test_messages = []
        
        for msg in unsent_messages:
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                if test_device_id in str(msg_data) or test_barcode in str(msg_data):
                    test_messages.append(msg_data)
            except:
                pass
        
        print(f"📊 Total unsent messages: {len(unsent_messages)}")
        print(f"📊 Test messages in queue: {len(test_messages)}")
        
        if test_messages:
            print("⚠️  Test messages still in local queue:")
            for msg in test_messages[-3:]:  # Show last 3
                msg_type = msg.get('messageType', 'unknown')
                timestamp = msg.get('timestamp', 'unknown')
                print(f"   • {msg_type} at {timestamp}")
            print("❌ Messages not delivered to IoT Hub")
        else:
            print("✅ No test messages in queue - likely delivered")
            
    except Exception as e:
        print(f"❌ Queue check error: {e}")
    
    print()
    print("STEP 4: Azure Portal Guidance")
    print("-" * 40)
    
    current_utc = datetime.now(timezone.utc)
    current_ist = datetime.now()
    
    print("🔍 WHERE TO LOOK IN AZURE PORTAL:")
    print()
    print("1. Go to Azure Portal → IoT Hubs")
    print(f"2. Select: {hub_name if 'hub_name' in locals() else 'CaleffiIoT'}")
    print("3. Navigate to: Overview → Monitoring")
    print("4. OR: Devices → Select device → Device-to-cloud messages")
    print()
    print("🕐 TIME RANGE TO CHECK:")
    print(f"   • Current IST: {current_ist.strftime('%H:%M:%S')} (your local time)")
    print(f"   • Current UTC: {current_utc.strftime('%H:%M:%S')} (Azure time)")
    print(f"   • Look for messages around: {current_utc.strftime('%H:%M')} UTC")
    print()
    print("📱 DEVICE TO CHECK:")
    print(f"   • Device ID: {test_device_id}")
    print(f"   • Look for messageType: 'visibility_test'")
    print(f"   • Look for testBarcode: '{test_barcode}'")
    print()
    print("🔧 IF NO MESSAGES APPEAR:")
    print("   1. Messages are stuck in local queue (not delivered)")
    print("   2. Device connection/authentication issue")
    print("   3. Wrong IoT Hub instance being checked")
    print("   4. Time zone confusion (check UTC time)")

if __name__ == "__main__":
    test_iot_hub_connectivity()
