"""
Dynamic device registration service for IoT Hub
Handles device provisioning and registration with Azure IoT Hub
"""
import logging
import json
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DynamicRegistrationService:
    """Service for dynamic device registration with IoT Hub"""
    
    def __init__(self, config_path=None):
        """Initialize with optional config path"""
        self.config_path = config_path or os.path.expanduser('~/.iot/device_registration.json')
        self.registered_devices = {}
        self._load_registered_devices()
    
    def _load_registered_devices(self):
        """Load registered devices from config file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.registered_devices = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load registered devices: {e}")
            self.registered_devices = {}
    
    def _save_registered_devices(self):
        """Save registered devices to config file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.registered_devices, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registered devices: {e}")
    
    def register_device(self, device_id, device_info=None):
        """
        Register a new device
        
        Args:
            device_id: Unique device identifier
            device_info: Optional device metadata
            
        Returns:
            tuple: (success, message)
        """
        try:
            if device_id in self.registered_devices:
                return True, "Device already registered"
                
            self.registered_devices[device_id] = {
                "id": device_id,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "info": device_info or {}
            }
            
            self._save_registered_devices()
            logger.info(f"Registered new device: {device_id}")
            return True, "Device registered successfully"
            
        except Exception as e:
            logger.error(f"Device registration failed: {e}")
            return False, str(e)
    
    def get_device_info(self, device_id):
        """Get registration info for a device"""
        return self.registered_devices.get(device_id)
    
    def list_devices(self):
        """List all registered devices"""
        return list(self.registered_devices.keys())

# Singleton instance
_registration_service = None

def get_dynamic_registration_service(config_path=None):
    """Get or create the singleton registration service instance"""
    global _registration_service
    if _registration_service is None:
        _registration_service = DynamicRegistrationService(config_path)
    return _registration_service
