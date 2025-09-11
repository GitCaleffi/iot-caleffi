#!/usr/bin/env python3
"""
IoT Hub Registration Helper
"""

import json
import logging
from pathlib import Path
import sys

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from utils.config import load_config, save_config

logger = logging.getLogger(__name__)

# Import IoT Hub registry manager
try:
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import Device, AuthenticationMechanism, SymmetricKey
    IOT_HUB_AVAILABLE = True
except ImportError:
    IOT_HUB_AVAILABLE = False
    logger.warning("Azure IoT Hub Registry Manager not available")

def register_device_with_iot_hub(device_id):
    """Register device with Azure IoT Hub"""
    if not IOT_HUB_AVAILABLE:
        return {"success": False, "error": "Azure IoT Hub Registry Manager not available"}
    
    try:
        config = load_config()
        if not config or "iot_hub" not in config:
            return {"success": False, "error": "IoT Hub configuration not found"}
        
        connection_string = config["iot_hub"].get("connection_string")
        if not connection_string:
            return {"success": False, "error": "IoT Hub connection string not found"}
        
        # Check if device already exists in config
        existing_devices = config.get("iot_hub", {}).get("devices", {})
        if device_id in existing_devices:
            return {"success": True, "device_id": device_id, "message": "Device already registered"}
        
        # Create registry manager
        registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
        
        # Try to get existing device or create new one
        try:
            device = registry_manager.get_device(device_id)
            logger.info(f"Device {device_id} already exists in IoT Hub")
        except Exception:
            # Create new device
            import base64
            import os
            primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            
            device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, "enabled")
            logger.info(f"Created new device {device_id} in IoT Hub")
        
        # Get device connection string
        primary_key = device.authentication.symmetric_key.primary_key
        
        # Extract hostname from IoT Hub connection string
        import re
        hostname_match = re.search(r'HostName=([^;]+)', connection_string)
        if not hostname_match:
            return {"success": False, "error": "Could not extract hostname from IoT Hub connection string"}
        
        hostname = hostname_match.group(1)
        device_connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
        
        # Update config
        if "devices" not in config["iot_hub"]:
            config["iot_hub"]["devices"] = {}
        
        config["iot_hub"]["devices"][device_id] = {
            "connection_string": device_connection_string,
            "deviceId": device_id
        }
        
        # Save config
        save_config(config)
        
        return {
            "success": True,
            "device_id": device_id,
            "connection_string": device_connection_string
        }
        
    except Exception as e:
        logger.error(f"Error registering device with IoT Hub: {e}")
        return {"success": False, "error": str(e)}