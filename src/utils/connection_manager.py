#!/usr/bin/env python3
"""
Enhanced Connection Manager for IoT Caleffi
Handles device connectivity checking in both server and local modes
"""

import os
import time
import logging
from typing import Dict, List, Optional
from pathlib import Path

from azure.iot.hub import IoTHubRegistryManager
from utils.config import load_config
from utils.network_discovery import NetworkDiscovery

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        """Initialize the connection manager with appropriate settings"""
        # Initialize basic attributes
        self.network_discovery = NetworkDiscovery()
        self.last_pi_check = 0
        self.pi_check_interval = 30
        self.raspberry_pi_devices_available = False
        
        # Load configuration
        self._load_configuration()
        
    def _load_configuration(self):
        """Load configuration settings"""
        try:
            self.config = load_config()
            # Check environment variables for mode settings
            self.server_mode = os.environ.get('SERVER_MODE', '').lower() == 'live'
            self.bypass_local = os.environ.get('BYPASS_LOCAL_CHECK', '').lower() == 'true'
            self.iot_hub_enabled = os.environ.get('IOT_HUB_ENABLED', '').lower() == 'true'
            
            logger.info(f"Connection Manager initialized in {'server' if self.server_mode else 'local'} mode")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = {}
            self.server_mode = False
            self.bypass_local = False
            self.iot_hub_enabled = False

    def check_raspberry_pi_connection(self) -> bool:
        """Check if Raspberry Pi is connected using appropriate method for environment"""
        if self.server_mode:
            return self._check_server_mode_connection()
        return self._check_local_mode_connection()
        
    def _check_server_mode_connection(self) -> bool:
        """Check connection in server mode - prioritize IoT Hub"""
        try:
            # First check IoT Hub connection
            if self.check_iot_hub_connection():
                logger.info("Raspberry Pi connection verified through IoT Hub")
                self.raspberry_pi_devices_available = True
                return True
                
            # Check registered devices in IoT Hub
            if self.config.get("iot_hub", {}).get("connection_string"):
                try:
                    registry_manager = IoTHubRegistryManager(
                        self.config["iot_hub"]["connection_string"]
                    )
                    # Query for active devices
                    query = "SELECT * FROM devices WHERE status = 'enabled'"
                    devices = registry_manager.query_iot_hub(query)
                    if devices:
                        logger.info(f"Found {len(devices)} active devices in IoT Hub")
                        self.raspberry_pi_devices_available = True
                        return True
                except Exception as e:
                    logger.error(f"IoT Hub registry query failed: {e}")
                    
            logger.warning("No active devices found in IoT Hub")
            self.raspberry_pi_devices_available = False
            return False
            
        except Exception as e:
            logger.error(f"Error checking server mode connection: {e}")
            self.raspberry_pi_devices_available = False
            return False
            
    def _check_local_mode_connection(self) -> bool:
        """Check connection in local mode - use network discovery"""
        try:
            current_time = time.time()
            if current_time - self.last_pi_check >= self.pi_check_interval:
                # Use NetworkDiscovery for local detection
                self.raspberry_pi_devices_available = self.network_discovery.find_raspberry_pi()
                self.last_pi_check = current_time
                
            return self.raspberry_pi_devices_available
            
        except Exception as e:
            logger.error(f"Error checking local mode connection: {e}")
            return False

    def check_iot_hub_connection(self) -> bool:
        """Check IoT Hub connection status"""
        try:
            if not self.iot_hub_enabled:
                return False

            if not self.config.get("iot_hub", {}).get("connection_string"):
                logger.warning("No IoT Hub connection string configured")
                return False

            registry_manager = IoTHubRegistryManager(
                self.config["iot_hub"]["connection_string"]
            )
            # Simple test query
            registry_manager.get_statistics()
            logger.debug("IoT Hub connection test successful")
            return True

        except Exception as e:
            logger.error(f"IoT Hub connection test failed: {e}")
            return False

    def get_connection_status(self) -> Dict[str, bool]:
        """Get current connection status"""
        return {
            "raspberry_pi": self.raspberry_pi_devices_available,
            "iot_hub": self.check_iot_hub_connection(),
            "server_mode": self.server_mode
        }
