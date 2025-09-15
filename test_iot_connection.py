#!/usr/bin/env python3
"""
Test IoT Hub connection for the registered device
"""

import json
import sys
import os
from pathlib import Path

# Add src to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))

# Add utils to path
utils_dir = current_dir / 'src' / 'utils'
sys.path.insert(0, str(utils_dir))

def load_config():
    """Load configuration from config.json"""
    config_path = current_dir / 'config.json'
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def test_iot_hub_connection():
    """Test IoT Hub connection for pi-c1323007"""
    print("🔗 Testing IoT Hub Connection")
    print("=" * 40)

    # Load config
    config = load_config()
    if not config:
        print("❌ Failed to load config")
        return False

    # Get device connection string
    devices = config.get("iot_hub", {}).get("devices", {})
    device_id = "pi-c1323007"

    if device_id not in devices:
        print(f"❌ Device {device_id} not found in config")
        print(f"Available devices: {list(devices.keys())}")
        return False

    connection_string = devices[device_id].get("connection_string")
    if not connection_string:
        print(f"❌ No connection string for device {device_id}")
        return False

    print(f"✅ Found connection string for device: {device_id}")
    print(f"🔗 Connection string: {connection_string[:50]}...")

    # Test IoT Hub connection
    try:
        from iot.hub_client import HubClient

        print("📡 Creating IoT Hub client...")
        hub_client = HubClient(connection_string, device_id)

        print("🔌 Connecting to IoT Hub...")
        if hub_client.connect():
            print("✅ Successfully connected to IoT Hub")

            # Test sending a message (must be 6-20 characters for barcode validation)
            test_message = "TEST12345"
            print(f"📤 Sending test message: {test_message}")

            success = hub_client.send_message(test_message, device_id)
            if success:
                print("✅ Test message sent successfully!")
                print("🎉 IoT Hub connection is working properly")
                return True
            else:
                print("❌ Failed to send test message")
                return False
        else:
            print("❌ Failed to connect to IoT Hub")
            return False

    except Exception as e:
        print(f"❌ IoT Hub connection error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_iot_hub_connection()
    sys.exit(0 if success else 1)