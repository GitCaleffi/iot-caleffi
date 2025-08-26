#!/usr/bin/env python3
"""
Pi IoT Hub Heartbeat Client
Sends periodic heartbeat messages to IoT Hub to maintain "Connected" status
"""

import time
import json
import logging
from datetime import datetime
from azure.iot.device import IoTHubDeviceClient, Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Device connection string for pi-5284d8ff
# Replace with actual device connection string from IoT Hub
CONNECTION_STRING = "HostName=CaleffiIoT.azure-devices.net;DeviceId=pi-5284d8ff;SharedAccessKey=YOUR_DEVICE_KEY"

def create_heartbeat_message():
    """Create a heartbeat message with current status"""
    message_data = {
        "messageType": "heartbeat",
        "deviceId": "pi-5284d8ff",
        "status": "online",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "systemInfo": {
            "uptime": time.time(),
            "services": ["barcode_scanner", "iot_client"]
        }
    }
    return json.dumps(message_data)

def main():
    """Main heartbeat loop"""
    try:
        logger.info("🚀 Starting Pi IoT Hub heartbeat client...")
        logger.info(f"📡 Device ID: pi-5284d8ff")
        
        # Create IoT Hub client
        client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
        
        # Connect to IoT Hub
        logger.info("🔗 Connecting to IoT Hub...")
        client.connect()
        logger.info("✅ Connected to IoT Hub successfully")
        
        heartbeat_count = 0
        
        while True:
            try:
                # Create and send heartbeat message
                heartbeat_data = create_heartbeat_message()
                message = Message(heartbeat_data)
                message.content_type = "application/json"
                message.content_encoding = "utf-8"
                
                # Send message
                client.send_message(message)
                heartbeat_count += 1
                
                logger.info(f"💓 Heartbeat #{heartbeat_count} sent to IoT Hub")
                
                # Wait 30 seconds before next heartbeat
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received, stopping...")
                break
            except Exception as e:
                logger.error(f"❌ Error sending heartbeat: {e}")
                time.sleep(10)  # Wait before retry
                
    except Exception as e:
        logger.error(f"❌ Failed to initialize IoT Hub client: {e}")
        logger.error("💡 Make sure to update CONNECTION_STRING with actual device key")
        return 1
    
    finally:
        try:
            client.disconnect()
            logger.info("🔌 Disconnected from IoT Hub")
        except:
            pass
    
    return 0

if __name__ == "__main__":
    exit(main())
