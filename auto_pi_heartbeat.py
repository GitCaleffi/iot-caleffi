#!/usr/bin/env python3
"""
Automatic Pi IoT Hub Heartbeat Service
Automatically maintains Pi connection to IoT Hub using dynamic device registration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import time
import json
import logging
import socket
import threading
from datetime import datetime
from azure.iot.device import IoTHubDeviceClient
from utils.config import load_config
from utils.dynamic_registration_service import get_dynamic_registration_service

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), 'logs', 'pi_heartbeat.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoPiHeartbeat:
    """Automatic Pi heartbeat service with dynamic device registration"""
    
    def __init__(self):
        self.config = load_config()
        self.client = None
        self.device_id = None
        self.connection_string = None
        self.running = False
        self.heartbeat_interval = 30  # seconds
        self.reconnect_interval = 60  # seconds
        self.max_retries = 5
        
    def get_pi_device_id(self):
        """Get Pi device ID from config or generate one"""
        pi_config = self.config.get("raspberry_pi", {})
        device_ids = pi_config.get("device_ids", [])
        
        if device_ids:
            # Use first configured device ID
            return device_ids[0]
        
        # Generate device ID from MAC address
        mac_address = pi_config.get("mac_address", "")
        if mac_address:
            # Extract last 8 characters of MAC for device ID
            mac_clean = mac_address.replace(":", "").replace("-", "").lower()
            return f"pi-{mac_clean[-8:]}"
        
        # Fallback to hostname-based ID
        hostname = socket.gethostname()
        return f"pi-{hostname}"
    
    def get_system_info(self):
        """Get current system information"""
        try:
            pi_config = self.config.get("raspberry_pi", {})
            
            # Use configured IP or detect current IP
            ip_address = pi_config.get("auto_detected_ip")
            if not ip_address:
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
            
            # Get uptime
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
        except Exception as e:
            logger.warning(f"Could not get system info: {e}")
            return {"services": ["auto_heartbeat"]}
    
    def create_reported_properties(self):
        """Create Device Twin reported properties"""
        system_info = self.get_system_info()
        
        return {
            "status": "online",
            "last_seen": datetime.utcnow().isoformat() + "Z",
            "device_info": {
                "hostname": system_info.get("hostname", "unknown"),
                "ip_address": system_info.get("ip_address", "unknown"),
                "mac_address": system_info.get("mac_address", "unknown"),
                "uptime_seconds": system_info.get("uptime_seconds", 0),
                "services": system_info.get("services", [])
            },
            "heartbeat_version": "auto-2.0",
            "auto_maintenance": True
        }
    
    def initialize_connection(self):
        """Initialize IoT Hub connection using dynamic registration"""
        try:
            self.device_id = self.get_pi_device_id()
            logger.info(f"🚀 Initializing auto heartbeat for device: {self.device_id}")
            
            # Initialize dynamic registration service with config
            try:
                from utils.dynamic_registration_service import DynamicRegistrationService
                iot_hub_config = self.config.get("iot_hub", {})
                owner_connection_string = iot_hub_config.get("connection_string")
                
                if not owner_connection_string:
                    logger.error("❌ No IoT Hub owner connection string found in config")
                    return False
                
                registration_service = DynamicRegistrationService(owner_connection_string)
                logger.info("✅ Dynamic registration service initialized")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize dynamic registration service: {e}")
                return False
            
            # Register device and get connection string
            self.connection_string = registration_service.register_device_with_azure(self.device_id)
            if not self.connection_string:
                logger.error(f"❌ Failed to get connection string for device {self.device_id}")
                return False
            
            logger.info(f"✅ Got connection string for device {self.device_id}")
            
            # Create IoT Hub client
            self.client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
            
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
        try:
            if not self.client:
                return False
            
            reported_properties = self.create_reported_properties()
            self.client.patch_twin_reported_properties(reported_properties)
            
            logger.info(f"💓 Heartbeat sent for {self.device_id}")
            logger.debug(f"📊 Status: {reported_properties['status']}, IP: {reported_properties['device_info']['ip_address']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error sending heartbeat: {e}")
            return False
    
    def disconnect(self):
        """Gracefully disconnect from IoT Hub"""
        try:
            if self.client:
                # Set status to offline before disconnecting
                offline_properties = {
                    "status": "offline",
                    "last_seen": datetime.utcnow().isoformat() + "Z"
                }
                self.client.patch_twin_reported_properties(offline_properties)
                logger.info("📴 Set status to offline in Device Twin")
                
                self.client.disconnect()
                logger.info("🔌 Disconnected from IoT Hub")
                
        except Exception as e:
            logger.warning(f"⚠️ Error during disconnect: {e}")
    
    def run(self):
        """Main heartbeat loop with automatic reconnection"""
        self.running = True
        heartbeat_count = 0
        retry_count = 0
        
        logger.info("🚀 Starting automatic Pi heartbeat service...")
        
        while self.running:
            try:
                # Initialize connection if needed
                if not self.client:
                    if not self.initialize_connection():
                        logger.error(f"❌ Connection failed, retrying in {self.reconnect_interval} seconds...")
                        time.sleep(self.reconnect_interval)
                        retry_count += 1
                        if retry_count >= self.max_retries:
                            logger.error(f"❌ Max retries ({self.max_retries}) reached, stopping service")
                            break
                        continue
                    retry_count = 0  # Reset retry count on successful connection
                
                # Send heartbeat
                if self.send_heartbeat():
                    heartbeat_count += 1
                    logger.info(f"✅ Heartbeat #{heartbeat_count} sent successfully")
                else:
                    logger.warning("⚠️ Heartbeat failed, will retry connection")
                    self.client = None  # Force reconnection
                
                # Wait for next heartbeat
                time.sleep(self.heartbeat_interval)
                
            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received, stopping service...")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in heartbeat loop: {e}")
                self.client = None  # Force reconnection
                time.sleep(self.reconnect_interval)
        
        self.running = False
        self.disconnect()
        logger.info("🏁 Automatic Pi heartbeat service stopped")

def main():
    """Main entry point"""
    heartbeat_service = AutoPiHeartbeat()
    
    try:
        heartbeat_service.run()
    except Exception as e:
        logger.error(f"❌ Service failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
