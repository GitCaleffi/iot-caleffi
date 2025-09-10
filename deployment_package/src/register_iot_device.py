#!/usr/bin/env python3
"""
Register device in Azure IoT Hub and send quantity update
"""
import json
from datetime import datetime, timezone

def register_and_send():
    """Register device and send quantity update"""
    
    # Use service connection string to register device
    service_connection_string = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="
    device_id = "cfabc4830309"
    
    print(f"📝 Registering device: {device_id}")
    
    try:
        from azure.iot.hub import IoTHubRegistryManager
        from azure.iot.hub.models import Device, AuthenticationMechanism, SymmetricKey
        
        # Create registry manager
        registry_manager = IoTHubRegistryManager(service_connection_string)
        
        # Check if device exists
        try:
            device = registry_manager.get_device(device_id)
            print(f"✅ Device {device_id} already exists")
            device_key = device.authentication.symmetric_key.primary_key
        except:
            # Create new device
            print(f"📝 Creating new device: {device_id}")
            auth = AuthenticationMechanism(type="sas", symmetric_key=SymmetricKey())
            device = Device(device_id=device_id, authentication=auth)
            device = registry_manager.create_device_with_sas(device)
            device_key = device.authentication.symmetric_key.primary_key
            print(f"✅ Device {device_id} created successfully")
        
        # Create device connection string
        device_connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={device_key}"
        
        # Send quantity update message
        message = {
            "deviceId": device_id,
            "barcode": "5901234123457",
            "quantity": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messageType": "barcode_scan"
        }
        
        print(f"📤 Sending quantity update...")
        
        from iot.hub_client import HubClient
        hub_client = HubClient(device_connection_string)
        success = hub_client.send_message(json.dumps(message), device_id)
        
        if success:
            print("✅ Quantity update sent to IoT Hub successfully!")
            print(f"📊 Barcode: 5901234123457")
            print(f"🔢 Quantity: +1")
            print(f"📱 Device: {device_id}")
        else:
            print("❌ Failed to send quantity update")
            
    except ImportError:
        print("❌ Azure IoT Hub SDK not available")
        print("Install: pip install azure-iot-hub")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    register_and_send()