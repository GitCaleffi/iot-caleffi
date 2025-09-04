"""
Device Registry - Handles device registration and status with IoT Hub
"""
import requests
import json
import logging
import time
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class DeviceRegistry:
    """Handles device registration and heartbeat with IoT Hub"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration"""
        self.config = config.get('iot_hub', {})
        self.connection_string = self.config.get('connection_string')
        self.device_id = None
        self.registered = False
        self.last_heartbeat = None
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 10  # seconds
        
        # Parse connection string
        self.host_name = None
        self.shared_access_key = None
        self.shared_access_key_name = None
        self._parse_connection_string()
        
        # IoT Hub settings
        self.registry_url = f"https://{self.host_name}/devices"
        self.api_version = "2020-03-13"
    
    def _parse_connection_string(self):
        """Parse the IoT Hub connection string"""
        if not self.connection_string:
            logger.warning("No connection string provided")
            return
            
        parts = dict(part.split('=', 1) for part in self.connection_string.split(';'))
        self.host_name = parts.get('HostName')
        self.shared_access_key = parts.get('SharedAccessKey')
        self.shared_access_key_name = parts.get('SharedAccessKeyName')
        
        if not all([self.host_name, self.shared_access_key, self.shared_access_key_name]):
            logger.warning("Invalid connection string format")
    
    def _generate_sas_token(self, resource_uri: str, key: str, expiry: int = 3600) -> str:
        """Generate a SAS token for authentication"""
        ttl = int(time.time()) + expiry
        sign_key = f"{urllib.parse.quote_plus(resource_uri)}\n{ttl}"
        signature = base64.b64encode(hmac.new(
            base64.b64decode(key), 
            sign_key.encode('utf-8'), 
            hashlib.sha256
        ).digest())
        
        return f"SharedAccessSignature sr={urllib.parse.quote_plus(resource_uri)}&sig={urllib.parse.quote(signature)}&se={ttl}&skn={self.shared_access_key_name}"
        
    def _register_with_iothub(self, device_id: str, device_info: Dict[str, Any]) -> Tuple[bool, str]:
        """Register device directly with IoT Hub"""
        if not self.host_name or not self.shared_access_key:
            logger.warning("Missing required connection parameters for IoT Hub registration")
            return False, "Missing connection parameters"
        
        # Generate SAS token for authentication
        resource_uri = f"{self.host_name}/devices"
        sas_token = self._generate_sas_token(resource_uri, self.shared_access_key)
        
        # Prepare device registration payload
        device_payload = {
            "deviceId": device_id,
            "status": "enabled",
            "capabilities": {
                "iotEdge": False
            },
            "properties": {
                "desired": {
                    "deviceInfo": device_info
                }
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': sas_token
        }
        
        try:
            # Check if device already exists
            check_url = f"{self.registry_url}/{device_id}?api-version={self.api_version}"
            response = requests.get(check_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Device {device_id} already exists, updating properties")
                # Update existing device
                response = requests.put(
                    f"{self.registry_url}/{device_id}?api-version={self.api_version}",
                    headers=headers,
                    json=device_payload,
                    timeout=30
                )
            elif response.status_code == 404:
                # Create new device
                response = requests.put(
                    f"{self.registry_url}/{device_id}?api-version={self.api_version}",
                    headers=headers,
                    json=device_payload,
                    timeout=30
                )
            
            if response.status_code in (200, 201):
                self.registered = True
                self.last_heartbeat = datetime.utcnow()
                logger.info(f"✅ Device {device_id} registered successfully with IoT Hub")
                return True, "Registration successful"
            else:
                error_msg = response.text
                logger.error(f"IoT Hub registration failed: {response.status_code} - {error_msg}")
                return False, f"Registration failed: {error_msg}"
                
        except Exception as e:
            logger.error(f"Error during IoT Hub registration: {e}", exc_info=True)
            return False, f"Registration error: {str(e)}"
    
    def register_device(self, device_id: str, device_info: Dict[str, Any]) -> bool:
        """Register the device with IoT Hub"""
        if not self.host_name or not self.shared_access_key:
            logger.warning("No connection string configured, skipping registration")
            return False
            
        self.device_id = device_id
        self.retry_count = 0
        
        while self.retry_count < self.max_retries:
            try:
                self.retry_count += 1
                logger.info(f"Registering device (attempt {self.retry_count}/{self.max_retries})")
                
                success, message = self._register_with_iothub(device_id, device_info)
                if success:
                    return True
                
                logger.warning(f"Registration attempt {self.retry_count} failed: {message}")
                
                if self.retry_count >= self.max_retries:
                    logger.error("Max retries reached, giving up")
                    return False
                
                # Exponential backoff
                retry_time = self.retry_delay * (2 ** (self.retry_count - 1))
                logger.info(f"Retrying in {retry_time} seconds...")
                time.sleep(retry_time)
                
            except Exception as e:
                logger.error(f"Error during device registration: {e}", exc_info=True)
                if self.retry_count >= self.max_retries:
                    logger.error("Max retries reached after exception")
                    return False
                
                retry_time = self.retry_delay * (2 ** (self.retry_count - 1))
                logger.info(f"Retrying in {retry_time} seconds after error...")
                time.sleep(retry_time)
        
        return False
        
    def update_heartbeat(self) -> bool:
        """Update the device heartbeat"""
        if not self.registered or not self.device_id:
            logger.warning("Device not registered, cannot update heartbeat")
            return False
            
        # For DPS, we'll just update the last_heartbeat timestamp
        # since DPS doesn't have a direct heartbeat endpoint
        try:
            self.last_heartbeat = datetime.utcnow()
            logger.debug(f"Heartbeat updated at {self.last_heartbeat}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating heartbeat: {e}")
            return False
        
    def get_device_status(self) -> Dict[str, Any]:
        """
        Get the current device status
            Dict with device status information
        """
        return {
            "device_id": self.device_id,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "registration_attempts": self.registration_attempts
        }
