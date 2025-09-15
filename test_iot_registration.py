#!/usr/bin/env python3
"""
Test IoT Hub device registration
"""

import json
import os
import sys
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

def save_config(config):
    """Save configuration to config.json"""
    config_path = current_dir / 'config.json'
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print("Config saved successfully")
    except Exception as e:
        print(f"Error saving config: {e}")

def register_device_with_iot_hub(device_id):
    """Register device with Azure IoT Hub"""
    try:
        from azure.iot.hub import IoTHubRegistryManager
        from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
        import base64
        import os

        print(f"Registering device {device_id} with Azure IoT Hub...")

        # Load config
        config = load_config()
        if not config or "iot_hub" not in config or "connection_string" not in config["iot_hub"]:
            print("IoT Hub connection string not found in config")
            return {"success": False, "error": "IoT Hub connection string not found in config"}

        # Check if device already exists in config
        if config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string"):
            existing_connection_string = config["iot_hub"]["devices"][device_id]["connection_string"]
            print(f"Device {device_id} already configured")
            return {"success": True, "device_id": device_id, "connection_string": existing_connection_string}

        # Get IoT Hub owner connection string
        iothub_connection_string = config["iot_hub"]["connection_string"]
        print(f"Using IoT Hub connection string: {iothub_connection_string[:50]}...")

        # Create IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(iothub_connection_string)

        # Check if device exists
        try:
            device = registry_manager.get_device(device_id)
            print(f"Device {device_id} already exists in IoT Hub")
        except Exception:
            print(f"Creating new device {device_id} in IoT Hub...")
            # Generate secure keys
            primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            status = "enabled"

            # Create device
            device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, status)
            print(f"Device {device_id} created successfully in IoT Hub")

        # Verify device
        if not device or not device.authentication or not device.authentication.symmetric_key:
            print(f"Device {device_id} creation failed or missing authentication")
            return {"success": False, "error": f"Device {device_id} creation failed or missing authentication"}

        # Get primary key
        primary_key = device.authentication.symmetric_key.primary_key
        if not primary_key:
            print(f"No primary key generated for device {device_id}")
            return {"success": False, "error": f"No primary key generated for device {device_id}"}

        # Create connection string
        import re
        hostname_match = re.search(r'HostName=([^;]+)', iothub_connection_string)
        if not hostname_match:
            print("Could not extract hostname from IoT Hub connection string")
            return {"success": False, "error": "Could not extract hostname from IoT Hub connection string"}

        hostname = hostname_match.group(1)
        connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"

        # Update config
        if "devices" not in config["iot_hub"]:
            config["iot_hub"]["devices"] = {}

        config["iot_hub"]["devices"][device_id] = {
            "connection_string": connection_string,
            "deviceId": device_id
        }

        # Save config
        save_config(config)
        print(f"Config file updated with device {device_id} connection string")

        return {"success": True, "device_id": device_id, "connection_string": connection_string}

    except Exception as e:
        print(f"Error in register_device_with_iot_hub: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("Testing IoT Hub device registration...")
    result = register_device_with_iot_hub('pi-c1323007')
    print("Registration result:", result)