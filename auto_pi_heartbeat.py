#!/usr/bin/env python3
"""
Automatic Pi IoT Hub Heartbeat Service
Maintains Pi connection to IoT Hub using dynamic device registration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import time
import logging
import socket
from datetime import datetime
from azure.iot.device import IoTHubDeviceClient
from utils.config import load_config

# Optional dynamic registration import
try:
    from utils.dynamic_registration_service import get_dynamic_registration_service
except ImportError:
    get_dynamic_registration_service = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


import hashlib

def mac_to_numeric_barcode(mac: str) -> str:
    """Convert MAC to 12-digit numeric string usable as barcode"""
    h = hashlib.sha256(mac.encode()).hexdigest()
    numeric = str(int(h[:15], 16))  # Take first 15 hex digits
    return numeric[:12].rjust(12, "0")




class AutoPiHeartbeat:
    """Automatic Pi heartbeat service with dynamic registration"""

    def __init__(self):
        self.config = load_config()
        self.client = None
        self.device_id = None
        self.connection_string = None
        self.running = False
        self.heartbeat_interval = 10  # seconds
        self.reconnect_interval = 10  # seconds
        self.max_retries = 5

    def is_client_connected(self):
        """Check if the client is truly connected"""
        try:
            # Attempt a lightweight operation to verify connectivity
            return self.client.connected
        except Exception:
            return False

    def get_system_info(self):
        """Get current system information"""
        pi_config = self.config.get("raspberry_pi", {})
        ip_address = pi_config.get("auto_detected_ip") or socket.gethostbyname(socket.gethostname())
        uptime_seconds = 0
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
        except:
            uptime_seconds = time.time()
        return {
            "hostname": socket.gethostname(),
            "ip_address": ip_address,
            "uptime_seconds": uptime_seconds,
            "mac_address": pi_config.get("mac_address", "unknown"),
            "services": ["barcode_scanner", "iot_client", "auto_heartbeat"]
        }

    def create_reported_properties(self):
        """Create Device Twin reported properties"""
        system_info = self.get_system_info()
        return {
            "status": "online",
            "last_seen": datetime.utcnow().isoformat() + "Z",
            "device_info": system_info,
            "heartbeat_version": "auto-2.0",
            "auto_maintenance": True
        }

    def initialize_connection(self):
        """Initialize IoT Hub connection using dynamic registration"""
        try:
            if self.config["iot_hub"].get("use_dynamic_registration", False):
                if get_dynamic_registration_service is None:
                    logger.error("❌ Dynamic registration service not available")
                    return False

                service = get_dynamic_registration_service(
                    iot_hub_connection_string=self.config["iot_hub"]["connection_string"]
                )
                if not service:
                    logger.error("❌ Failed to initialize dynamic registration service")
                    return False

                pi_mac = self.config.get("raspberry_pi", {}).get("mac_address", "")
                if not pi_mac:
                    pi_mac = socket.gethostname()

                barcode_numeric = mac_to_numeric_barcode(pi_mac)
                self.connection_string = service.get_device_connection_for_barcode(barcode=barcode_numeric)
                self.device_id = barcode_numeric

                if not self.connection_string:
                    logger.error("❌ Failed to get dynamic device ID or connection string")
                    return False

            else:
                pi_config = self.config.get("raspberry_pi", {})
                mac = pi_config.get("mac_address", "").replace(":", "").lower()
                self.device_id = f"pi-{mac[-8:]}" if mac else f"pi-{socket.gethostname()}"
                self.connection_string = self.config["iot_hub"].get("device_connection_string")
                if not self.connection_string:
                    logger.error("❌ No device connection string provided for static mode")
                    return False

            logger.info(f"🚀 Using device ID: {self.device_id}")

            # Create IoT Hub client
            self.client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)

            # Define connection state change handler
            def connection_state_change_handler(state):
                if state:
                    logger.info("💚 Connected to IoT Hub")
                else:
                    logger.warning("💔 Disconnected from IoT Hub, forcing reconnect")
                    self.client = None  # triggers reconnection in main loop

            # Assign handler before connecting
            self.client.on_connection_state_change = connection_state_change_handler

            # Connect to IoT Hub
            logger.info("🔗 Connecting to IoT Hub...")
            self.client.connect()
            logger.info("✅ Connected to IoT Hub successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize connection: {e}")
            return False


    def send_heartbeat(self):
        """Send heartbeat via Device Twin reported properties"""
        if not self.client or not self.is_client_connected():
            return False
        try:
            reported_properties = self.create_reported_properties()
            self.client.patch_twin_reported_properties(reported_properties)
            logger.info(f"💓 Heartbeat sent for {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error sending heartbeat: {e}")
            return False

    def disconnect(self):
        """Gracefully disconnect from IoT Hub"""
        if self.client:
            try:
                offline_properties = {"status": "offline", "last_seen": datetime.utcnow().isoformat() + "Z"}
                self.client.patch_twin_reported_properties(offline_properties)
                self.client.disconnect()
                logger.info("🔌 Disconnected from IoT Hub")
            except Exception as e:
                logger.warning(f"⚠️ Error during disconnect: {e}")

    def run(self):
        self.running = True
        heartbeat_count = 0
        logger.info("🚀 Starting Pi heartbeat service...")

        while self.running:
            try:
                # Check connection
                if not self.client or not getattr(self.client, "connected", False):
                    logger.warning("⚠️ Client disconnected, reconnecting...")
                    self.client = None
                    if not self.initialize_connection():
                        logger.error(f"❌ Reconnection failed, retrying in {self.reconnect_interval}s...")
                        time.sleep(self.reconnect_interval)
                        continue

                # Send heartbeat
                if self.client and getattr(self.client, "connected", False):
                    self.send_heartbeat()
                    heartbeat_count += 1
                    logger.info(f"✅ Heartbeat #{heartbeat_count} sent successfully")
                else:
                    logger.warning("⚠️ Skipping heartbeat due to disconnected client")

                time.sleep(self.heartbeat_interval)

            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received, stopping service...")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error: {e}")
                self.client = None
                time.sleep(self.reconnect_interval)



def main():
    heartbeat_service = AutoPiHeartbeat()
    try:
        heartbeat_service.run()
    except Exception as e:
        logger.error(f"❌ Service failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit(main())
