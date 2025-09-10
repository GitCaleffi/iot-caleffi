#!/usr/bin/env python3
"""
Send final quantity update to IoT Hub
"""
import json
from datetime import datetime, timezone

def send_quantity():
    """Send quantity update to IoT Hub"""
    
    try:
        from azure.iot.hub import IoTHubRegistryManager
        
        # Service connection string
        service_connection_string = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="
        device_id = "cfabc4830309"
        
        # Get device key
        registry_manager = IoTHubRegistryManager(service_connection_string)
        device = registry_manager.get_device(device_id)
        device_key = device.authentication.symmetric_key.primary_key
        
        # Create device connection string
        device_connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={device_key}"
        
        # Create quantity update message
        message = {
            "deviceId": device_id,
            "barcode": "5901234123457",
            "quantity": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messageType": "barcode_scan",
            "operation": "quantity_update"
        }
        
        print("📤 Sending quantity update to IoT Hub...")
        print(f"📱 Device: {device_id}")
        print(f"📊 Barcode: 5901234123457")
        print(f"🔢 Quantity: +1")
        
        # Send message using Azure IoT Device SDK directly
        from azure.iot.device import IoTHubDeviceClient, Message
        
        client = IoTHubDeviceClient.create_from_connection_string(device_connection_string)
        client.connect()
        
        msg = Message(json.dumps(message))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"
        
        client.send_message(msg)
        client.disconnect()
        
        print("✅ Quantity update sent to IoT Hub successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    send_quantity()