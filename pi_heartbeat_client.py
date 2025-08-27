import time
import json
import logging
import socket
import subprocess
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

def get_system_info():
    """Get current system information"""
    try:
        # Get IP address
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        
        # Get uptime
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
        
        return {
            "hostname": hostname,
            "ip_address": ip_address,
            "uptime_seconds": uptime_seconds,
            "services": ["barcode_scanner", "iot_client"]
        }
    except Exception as e:
        logger.warning(f"Could not get system info: {e}")
        return {"services": ["barcode_scanner", "iot_client"]}

def create_reported_properties():
    """Create Device Twin reported properties"""
    system_info = get_system_info()
    
    reported_properties = {
        "status": "online",
        "last_seen": datetime.utcnow().isoformat() + "Z",
        "device_info": {
            "hostname": system_info.get("hostname", "unknown"),
            "ip_address": system_info.get("ip_address", "unknown"),
            "uptime_seconds": system_info.get("uptime_seconds", 0),
            "services": system_info.get("services", [])
        },
        "heartbeat_version": "2.0"
    }
    
    return reported_properties

def main():
    """Main heartbeat loop using Device Twin reported properties"""
    try:
        logger.info("🚀 Starting Pi IoT Hub heartbeat client with Device Twin...")
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
                # Update Device Twin reported properties
                reported_properties = create_reported_properties()
                client.patch_twin_reported_properties(reported_properties)
                heartbeat_count += 1
                
                logger.info(f"💓 Device Twin heartbeat #{heartbeat_count} updated")
                logger.info(f"📊 Status: {reported_properties['status']}, Last seen: {reported_properties['last_seen']}")
                
                # Wait 30 seconds before next heartbeat
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received, stopping...")
                break
            except Exception as e:
                logger.error(f"❌ Error updating Device Twin: {e}")
                time.sleep(10)  # Wait before retry
                
    except Exception as e:
        logger.error(f"❌ Failed to initialize IoT Hub client: {e}")
        logger.error("💡 Make sure to update CONNECTION_STRING with actual device key")
        return 1
    
    finally:
        try:
            # Set status to offline before disconnecting
            try:
                offline_properties = {
                    "status": "offline",
                    "last_seen": datetime.utcnow().isoformat() + "Z"
                }
                client.patch_twin_reported_properties(offline_properties)
                logger.info("📴 Set status to offline in Device Twin")
            except:
                pass
            
            client.disconnect()
            logger.info("🔌 Disconnected from IoT Hub")
        except:
            pass
    
    return 0

if __name__ == "__main__":
    exit(main())
