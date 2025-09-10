#!/usr/bin/env python3
"""
Send quantity update to IoT Hub with valid connection string
"""
import json
from datetime import datetime, timezone

def send_quantity_update():
    """Send quantity update to IoT Hub"""
    
    # Device-specific connection string for cfabc4830309
    device_connection_string = "HostName=CaleffiIoT.azure-devices.net;DeviceId=cfabc4830309;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="
    
    message = {
        "deviceId": "cfabc4830309",
        "barcode": "5901234123457",
        "quantity": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messageType": "barcode_scan"
    }
    
    print("📤 Sending quantity update to IoT Hub...")
    print(f"Device: cfabc4830309")
    print(f"Barcode: 5901234123457")
    print(f"Quantity: +1")
    
    try:
        from iot.hub_client import HubClient
        
        hub_client = HubClient(device_connection_string)
        success = hub_client.send_message(json.dumps(message), "cfabc4830309")
        
        if success:
            print("✅ Quantity update sent to IoT Hub successfully!")
            return True
        else:
            print("❌ Failed to send quantity update")
            return False
            
    except Exception as e:
        print(f"❌ IoT Hub error: {e}")
        return False

if __name__ == "__main__":
    send_quantity_update()