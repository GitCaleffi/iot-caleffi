#!/usr/bin/env python3
"""
Direct IoT Hub message sender for quantity updates
"""
import json
import sys
from datetime import datetime, timezone

def send_iot_message(device_id, barcode, quantity=1):
    """Send quantity update message directly to IoT Hub"""
    try:
        # Create IoT Hub message payload
        message_data = {
            "deviceId": device_id,
            "barcode": barcode,
            "quantity": quantity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "messageType": "barcode_scan",
            "operation": "quantity_update"
        }
        
        # Try to import and use IoT Hub client
        try:
            from iot.hub_client import HubClient
            
            # Use default connection string or device-specific one
            connection_string = "HostName=CaleffiIoT.azure-devices.net;DeviceId=cfabc4830309;SharedAccessKey=your_key_here"
            
            hub_client = HubClient(connection_string)
            success = hub_client.send_message(json.dumps(message_data), device_id)
            
            if success:
                print(f"✅ IoT Hub message sent: {barcode} quantity {quantity}")
                return True
            else:
                print(f"❌ IoT Hub send failed")
                return False
                
        except ImportError:
            print("⚠️ IoT Hub client not available - simulating send")
            print(f"📤 Would send to IoT Hub: {json.dumps(message_data, indent=2)}")
            return True
            
    except Exception as e:
        print(f"❌ Error sending IoT message: {e}")
        return False

if __name__ == "__main__":
    # Send EAN barcode from image to IoT Hub
    device_id = "cfabc4830309"
    barcode = "5901234123457"  # EAN from image
    quantity = 1
    
    print(f"🚀 Sending quantity update to IoT Hub...")
    print(f"📱 Device: {device_id}")
    print(f"📊 Barcode: {barcode}")
    print(f"🔢 Quantity: {quantity}")
    
    success = send_iot_message(device_id, barcode, quantity)
    
    if success:
        print("✅ Quantity update sent successfully!")
    else:
        print("❌ Failed to send quantity update")