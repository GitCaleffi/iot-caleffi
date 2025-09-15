"""
Dynamic device registration service for IoT Hub
Handles device provisioning and registration with Azure IoT Hub
"""
import logging
import json
import os
from datetime import datetime, timezone

# Azure IoT Hub imports
try:
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import Device, AuthenticationMechanism, SymmetricKey
    AZURE_IOT_AVAILABLE = True
except ImportError:
    AZURE_IOT_AVAILABLE = False
    print("Azure IoT Hub SDK not available - using fallback mode")

logger = logging.getLogger(__name__)

class DynamicRegistrationService:
    """Service for dynamic device registration with IoT Hub"""
    
    def __init__(self, config_path=None):
        """Initialize with optional config path"""
        self.config_path = config_path or os.path.expanduser('~/.iot/device_registration.json')
        self.registered_devices = {}
        self.iot_hub_connection_string = None
        self.registry_manager = None
        self._load_registered_devices()
        self._initialize_iot_hub()
    
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
    
    def _initialize_iot_hub(self):
        """Initialize IoT Hub connection"""
        try:
            # Load IoT Hub connection string from config
            from utils.config import load_config
            config = load_config()
            self.iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
            
            if self.iot_hub_connection_string and AZURE_IOT_AVAILABLE:
                self.registry_manager = IoTHubRegistryManager(self.iot_hub_connection_string)
                logger.info("✅ IoT Hub Registry Manager initialized")
            else:
                logger.warning("⚠️ IoT Hub connection string not available or Azure SDK missing")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize IoT Hub: {e}")
    
    def register_device_with_azure(self, device_id):
        """Register device with Azure IoT Hub and return connection string"""
        try:
            if not self.registry_manager:
                logger.error("❌ IoT Hub Registry Manager not initialized")
                return None
            
            # Check if device already exists
            try:
                existing_device = self.registry_manager.get_device(device_id)
                if existing_device:
                    logger.info(f"✅ Device {device_id} already exists in IoT Hub")
                    return self._build_device_connection_string(device_id, existing_device.authentication.symmetric_key.primary_key)
            except:
                # Device doesn't exist, create it
                pass
            
            # Create new device
            primary_key = self._generate_device_key()
            secondary_key = self._generate_device_key()
            
            # Create device directly with SAS authentication
            created_device = self.registry_manager.create_device_with_sas(
                device_id=device_id,
                primary_key=primary_key,
                secondary_key=secondary_key,
                status="enabled"
            )
            logger.info(f"✅ Device {device_id} created in Azure IoT Hub")
            
            # Build and return connection string
            connection_string = self._build_device_connection_string(device_id, primary_key)
            
            # Save device info locally
            self.registered_devices[device_id] = {
                "id": device_id,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "connection_string": connection_string,
                "azure_registered": True
            }
            self._save_registered_devices()
            
            return connection_string
            
        except Exception as e:
            logger.error(f"❌ Azure device registration failed for {device_id}: {e}")
            return None
    
    def get_device_connection_string(self, device_id):
        """Get device connection string for IoT Hub communication"""
        try:
            # Check if we have it locally first
            device_info = self.registered_devices.get(device_id)
            if device_info and device_info.get("connection_string"):
                return device_info["connection_string"]
            
            # Try to register with Azure and get connection string
            connection_string = self.register_device_with_azure(device_id)
            return connection_string
            
        except Exception as e:
            logger.error(f"❌ Failed to get connection string for {device_id}: {e}")
            return None
    
    def _generate_device_key(self):
        """Generate a device key for Azure IoT Hub"""
        import base64
        import secrets
        
        # Generate 32 random bytes and encode as base64
        key_bytes = secrets.token_bytes(32)
        return base64.b64encode(key_bytes).decode('utf-8')
    
    def _build_device_connection_string(self, device_id, primary_key):
        """Build device connection string from components"""
        if not self.iot_hub_connection_string:
            return None
            
        # Extract hostname from hub connection string
        hostname = None
        for part in self.iot_hub_connection_string.split(';'):
            if part.startswith('HostName='):
                hostname = part.split('=', 1)[1]
                break
        
        if not hostname:
            logger.error("❌ Could not extract hostname from IoT Hub connection string")
            return None
        
        return f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"

# Singleton instance
_registration_service = None

def get_dynamic_registration_service(config_path=None):
    """Get or create the singleton registration service instance"""
    global _registration_service
    if _registration_service is None:
        _registration_service = DynamicRegistrationService(config_path)
    return _registration_service
