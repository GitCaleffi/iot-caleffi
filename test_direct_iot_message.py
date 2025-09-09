#!/usr/bin/env python3
"""
Test direct IoT Hub message sending to verify connectivity and message delivery
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def test_direct_iot_message():
    """Test direct IoT Hub message sending"""
    print("🧪 Testing Direct IoT Hub Message Delivery")
    print("=" * 50)
    
    test_device_id = "1b058165dd09"
    
    print(f"📱 Device ID: {test_device_id}")
    print()
    
    print("STEP 1: Load IoT Hub Configuration")
    print("-" * 40)
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        iot_config = config.get('iot_hub', {})
        owner_conn_str = iot_config.get('connection_string', '')
        
        if owner_conn_str:
            print("✅ IoT Hub configuration loaded")
            # Extract hub name for reference
            if 'HostName=' in owner_conn_str:
                hub_name = owner_conn_str.split('HostName=')[1].split(';')[0]
                print(f"🏢 Hub: {hub_name}")
        else:
            print("❌ No IoT Hub connection string found")
            return
            
    except Exception as e:
        print(f"❌ Config error: {e}")
        return
    
    print()
    print("STEP 2: Test Direct IoT Hub Connection")
    print("-" * 40)
    
    try:
        from iot.hub_client import HubClient
        
        # Create device-specific connection string
        device_conn_str = owner_conn_str.replace(
            'SharedAccessKeyName=iothubowner',
            f'DeviceId={test_device_id}'
        ).replace(
            'SharedAccessKey=',
            'SharedAccessKey='  # This will need the actual device key
        )
        
        print(f"🔌 Connecting to IoT Hub with device: {test_device_id}")
        
        hub_client = HubClient(owner_conn_str)  # Use owner connection for testing
        
        if hub_client.connect():
            print("✅ Connected to IoT Hub successfully")
        else:
            print("❌ Failed to connect to IoT Hub")
            return
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return
    
    print()
    print("STEP 3: Send Test Message")
    print("-" * 40)
    
    try:
        # Create test message
        test_message = {
            "messageType": "test_message",
            "deviceId": test_device_id,
            "testData": "Direct IoT Hub test",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": "Testing message delivery visibility"
        }
        
        print("📤 Sending test message:")
        print(json.dumps(test_message, indent=2))
        
        # Send message using the hub client
        success = hub_client.send_message(test_message, test_device_id)
        
        if success:
            print("✅ Message sent successfully!")
            print(f"🕐 Sent at: {datetime.now().strftime('%H:%M:%S')} IST")
            print(f"🕐 UTC time: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
        else:
            print("❌ Message sending failed")
            
    except Exception as e:
        print(f"❌ Send error: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
    
    print()
    print("STEP 4: Check Message Queue Status")
    print("-" * 40)
    
    try:
        from database.local_storage import LocalStorage
        local_db = LocalStorage()
        
        unsent_messages = local_db.get_unsent_messages() or []
        recent_messages = [msg for msg in unsent_messages if test_device_id in str(msg)]
        
        print(f"📊 Total unsent messages: {len(unsent_messages)}")
        print(f"📊 Messages for {test_device_id}: {len(recent_messages)}")
        
        if recent_messages:
            print("⚠️  Messages still in local queue - not delivered to IoT Hub")
        else:
            print("✅ No messages in queue - may have been delivered")
            
    except Exception as e:
        print(f"❌ Queue check error: {e}")
    
    print()
    print("=" * 50)
    print("🎯 IOT HUB MESSAGE TEST RESULTS")
    print("=" * 50)
    print(f"Device: {test_device_id}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')} IST")
    print(f"UTC: {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
    print()
    print("🔍 CHECK AZURE IOT HUB PORTAL:")
    print(f"1. Go to your IoT Hub: {hub_name if 'hub_name' in locals() else 'Your IoT Hub'}")
    print(f"2. Navigate to Devices → {test_device_id}")
    print("3. Check 'Device-to-cloud messages' or 'Telemetry'")
    print("4. Look for messages around the UTC time shown above")
    print("5. If no messages appear, there's a delivery issue")

if __name__ == "__main__":
    test_direct_iot_message()
