#!/usr/bin/env python3
"""
Check IoT Hub message delivery and provide specific guidance for finding messages
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from database.local_storage import LocalStorage

def check_iot_messages():
    """Check recent IoT Hub messages and provide guidance"""
    print("🔍 IoT Hub Message Debugging")
    print("=" * 50)
    
    local_db = LocalStorage()
    
    print("STEP 1: Check Recent Device Messages")
    print("-" * 40)
    
    try:
        # Get all recent messages
        unsent_messages = local_db.get_unsent_messages() or []
        
        print(f"📊 Total unsent messages in database: {len(unsent_messages)}")
        
        # Show recent messages
        recent_devices = set()
        for msg in unsent_messages[-10:]:  # Last 10 messages
            try:
                msg_data = json.loads(msg.get('message_data', '{}'))
                device_id = msg_data.get('deviceId', 'unknown')
                msg_type = msg_data.get('messageType', 'unknown')
                timestamp = msg_data.get('timestamp', 'unknown')
                
                recent_devices.add(device_id)
                
                print(f"📱 Device: {device_id}")
                print(f"   Type: {msg_type}")
                print(f"   Time: {timestamp}")
                print(f"   Status: {'Unsent' if msg.get('sent', False) == False else 'Sent'}")
                print()
                
            except json.JSONDecodeError:
                pass
        
        if recent_devices:
            print("🎯 DEVICES TO CHECK IN IOT HUB:")
            for device in sorted(recent_devices):
                print(f"   • {device}")
        
    except Exception as e:
        print(f"❌ Error checking messages: {e}")
    
    print()
    print("STEP 2: Check Sent Messages (if any)")
    print("-" * 40)
    
    try:
        # Check if there are any sent messages
        sent_messages = [msg for msg in unsent_messages if msg.get('sent', False)]
        
        if sent_messages:
            print(f"✅ Found {len(sent_messages)} sent messages")
            for msg in sent_messages[-5:]:  # Last 5 sent
                try:
                    msg_data = json.loads(msg.get('message_data', '{}'))
                    device_id = msg_data.get('deviceId', 'unknown')
                    timestamp = msg_data.get('timestamp', 'unknown')
                    print(f"   ✅ {device_id} at {timestamp}")
                except:
                    pass
        else:
            print("⚠️  No sent messages found - messages may still be in queue")
    
    except Exception as e:
        print(f"❌ Error checking sent messages: {e}")
    
    print()
    print("STEP 3: IoT Hub Portal Guidance")
    print("-" * 40)
    
    print("🔍 WHERE TO LOOK IN AZURE IOT HUB:")
    print()
    print("1. Go to Azure Portal → IoT Hub")
    print("2. Select your IoT Hub instance")
    print("3. Go to 'Monitoring' → 'Metrics' or 'Device-to-cloud messages'")
    print("4. OR go to 'Devices' → Select specific device → 'Device-to-cloud messages'")
    print()
    
    print("🕐 TIME ZONE ISSUES:")
    print("   • Your local time: 15:15 IST (UTC+5:30)")
    print("   • Azure shows UTC time")
    print("   • Look for messages around 09:45 UTC (15:15 IST)")
    print()
    
    print("📱 SPECIFIC DEVICES TO CHECK:")
    if recent_devices:
        for device in sorted(recent_devices):
            print(f"   • Device ID: {device}")
    else:
        print("   • 1b058165dd09 (from recent test)")
        print("   • 448c5444b686 (from previous tests)")
    
    print()
    print("🔧 TROUBLESHOOTING STEPS:")
    print("1. Check if you're looking at the correct IoT Hub instance")
    print("2. Verify time range (last 1-2 hours)")
    print("3. Check 'Device telemetry' or 'D2C messages' section")
    print("4. Try refreshing the portal page")
    print("5. Check if messages are in 'Event Hub' compatible endpoint")

if __name__ == "__main__":
    check_iot_messages()
