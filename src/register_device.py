#!/usr/bin/env python3
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
import json
from pathlib import Path

# IoT Hub owner connection string
IOTHUB_CONNECTION_STRING = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="

# Device IDs to register
DEVICE_IDS = [
    "694833b1b872",
    "c798aec00f22",
    "423399a34af8"
]

def register_single_device(registry_manager, device_id):
    """Register a single device and return its connection string"""
    try:
        # Validate device ID format
        if not device_id or not isinstance(device_id, str):
            raise ValueError(f"Invalid device ID format: {device_id}")

        # Check if device exists with better error handling
        try:
            device = registry_manager.get_device(device_id)
            print(f"Device {device_id} already exists")
        except Exception as e:
            print(f"Creating new device {device_id}...")
            # Create device with SAS authentication
            try:
                # Generate a secure primary key (base64 encoded)
                import base64
                import os
                # Generate a random 32-byte key and encode it as base64
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')  # Also generate secondary key
                status = "enabled"
                
                # Use create_device_with_sas method
                device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, status)
                print(f"Device {device_id} created successfully")
            except Exception as create_error:
                print(f"Detailed error creating device: {str(create_error)}")
                raise

        # Verify device was created/exists and has authentication
        if not device or not device.authentication or not device.authentication.symmetric_key:
            raise ValueError(f"Device {device_id} creation failed or missing authentication")

        # Get the primary key with verification
        primary_key = device.authentication.symmetric_key.primary_key
        if not primary_key:
            raise ValueError(f"No primary key generated for device {device_id}")
        
        # Create and verify connection string
        connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={primary_key}"
        return connection_string

    except Exception as ex:
        print(f"Detailed error registering device {device_id}: {str(ex)}")
        print(f"Error type: {type(ex).__name__}")
        return None

def update_config_file(devices_info):
    """Update config.json with device information"""
    config_path = Path(__file__).parent.parent / 'config.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Update or create devices section
        if 'iot_hub' not in config:
            config['iot_hub'] = {}
        if 'devices' not in config['iot_hub']:
            config['iot_hub']['devices'] = {}

        # Update each device
        for device_id, conn_string in devices_info.items():
            if conn_string:  # Only update if registration was successful
                config['iot_hub']['devices'][device_id] = {
                    "connection_string": conn_string,
                    "deviceId": device_id
                }

        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"\nConfig file updated successfully: {config_path}")

    except Exception as e:
        print(f"Error updating config file: {e}")

def main():
    print("Registering devices with Azure IoT Hub...")
    try:
        # Create IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(IOTHUB_CONNECTION_STRING)
        
        # Store device info
        devices_info = {}

        # Register each device
        for device_id in DEVICE_IDS:
            print(f"\nProcessing device: {device_id}")
            conn_string = register_single_device(registry_manager, device_id)
            devices_info[device_id] = conn_string

        # Update config file
        update_config_file(devices_info)

        # Summary
        print("\nRegistration Summary:")
        for device_id, conn_string in devices_info.items():
            status = "SUCCESS" if conn_string else "FAILED"
            print(f"Device {device_id}: {status}")

    except Exception as ex:
        print(f"Error in device registration: {ex}")

if __name__ == "__main__":
    main()
