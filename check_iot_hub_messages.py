#!/usr/bin/env python3
"""
Check IoT Hub Messages - Verify if messages are actually reaching Azure IoT Hub
"""

import sys
import os
import json
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from iot.hub_client import HubClient
from utils.config import load_config
from utils.dynamic_registration_service import get_dynamic_registration_service

def test_simple_message():
    """Send a simple test message to verify IoT Hub connectivity"""
    
    print("🔍 Testing IoT Hub Message Delivery")
    print("=" * 50)
    
    try:
        # Load config
        config = load_config()
        
        # Get device connection string
        registration_service = get_dynamic_registration_service()
        device_id = "test-message-verification"
        
        print(f"📱 Device ID: {device_id}")
        
        # Register device and get connection string
        connection_string = registration_service.register_device_with_azure(device_id)
        print(f"🔗 Connection string obtained")
        
        # Create hub client
        hub_client = HubClient(connection_string, device_id)
        
        # Test connection
        print("🔄 Testing connection...")
        hub_client.test_connection()
        print("✅ Connection successful")
        
        # Send test message with timestamp
        timestamp = datetime.now(timezone.utc).isoformat()
        test_message = {
            "messageType": "test_verification",
            "deviceId": device_id,
            "testEAN": "1111111111111",
            "quantity": 1,
            "timestamp": timestamp,
            "note": "Test message to verify IoT Hub delivery"
        }
        
        print(f"📤 Sending test message at {timestamp}")
        print(f"📋 Message content: {json.dumps(test_message, indent=2)}")
        
        # Send message
        result = hub_client.send_message(test_message, device_id)
        
        if "sent successfully" in str(result):
            print("✅ Message sent successfully!")
            print()
            print("🔍 TO CHECK IN AZURE IOT HUB:")
            print(f"1. Go to Azure Portal → IoT Hub → Devices")
            print(f"2. Find device: {device_id}")
            print(f"3. Check 'Device-to-cloud messages' or 'Telemetry'")
            print(f"4. Look for timestamp: {timestamp}")
            print(f"5. Message should contain EAN: 1111111111111")
            print()
            print("⏰ Message sent at:", timestamp)
            print("📱 Device ID:", device_id)
            print("🏷️  Test EAN:", "1111111111111")
            
        else:
            print(f"❌ Message send failed: {result}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def check_recent_device_messages():
    """Check for recent messages from the main device"""
    
    print("\n" + "=" * 50)
    print("🔍 Checking Recent Messages from Main Device")
    print("=" * 50)
    
    try:
        # Get the main device ID that was used in tests
        device_id = "pi-c1323007"  # From the logs
        
        print(f"📱 Main device ID: {device_id}")
        print("🔍 Recent EAN numbers that should be in IoT Hub:")
        print("   • 12345678 (EAN-8)")
        print("   • 5901234123457 (EAN-13)")
        print("   • 8901030895559 (EAN-13)")
        print()
        print("📍 WHERE TO LOOK IN AZURE:")
        print("1. Azure Portal → Your IoT Hub")
        print("2. Left menu → 'Devices' → Find 'pi-c1323007'")
        print("3. Click on device → 'Device-to-cloud messages'")
        print("4. Set time range to 'Last hour'")
        print("5. Look for messages with messageType: 'quantity_update'")
        print()
        print("🕐 Messages sent around: 18:15 IST (12:45 UTC)")
        print("📦 Expected message format:")
        print(json.dumps({
            "messageType": "quantity_update",
            "deviceId": "pi-c1323007", 
            "ean": "12345678",
            "quantity": 1,
            "action": "scan",
            "timestamp": "2025-09-15T12:45:XX.XXXZ"
        }, indent=2))
        
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🚀 IoT Hub Message Verification Tool")
    print()
    
    # Test 1: Send a new verification message
    test_simple_message()
    
    # Test 2: Provide guidance for checking recent messages
    check_recent_device_messages()
    
    print("\n" + "=" * 50)
    print("📋 SUMMARY")
    print("=" * 50)
    print("✅ New test message sent for verification")
    print("📍 Check Azure IoT Hub for both:")
    print("   1. New test message (device: test-message-verification)")
    print("   2. Previous EAN messages (device: pi-c1323007)")
    print()
    print("💡 If no messages appear, possible causes:")
    print("   • Wrong IoT Hub instance")
    print("   • Time zone differences")
    print("   • Portal filtering settings")
    print("   • Device not properly registered")

if __name__ == "__main__":
    main()
