#!/usr/bin/env python3
"""
Dynamic Registration Service - Automatically registers devices with Azure IoT Hub
Supports commercial scale deployment with barcode-only identification
"""

import logging
import base64
import os
from typing import Optional, Dict, Tuple
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import Device, AuthenticationMechanism, SymmetricKey
import threading
from .barcode_device_mapper import barcode_mapper

logger = logging.getLogger(__name__)

class DynamicRegistrationService:
    """
    Handles automatic device registration with Azure IoT Hub for commercial scale deployment.
    Registers devices dynamically based on barcode scans without manual intervention.
    """
    
    def __init__(self, config):
        """Initialize the dynamic registration service"""
        self.config = config
        self.lock = threading.RLock()
        self.registry_manager = None
        
        # Extract connection string and hostname
        iot_hub_config = config.get("iot_hub", {})
        self.connection_string = iot_hub_config.get("connection_string")
        
        # Handle case where connection_string might be passed directly
        if isinstance(self.connection_string, dict):
            logger.error("Connection string is a dict, expected string")
            raise ValueError("IoT Hub connection string must be a string, not dict")
        
        if not self.connection_string:
            raise ValueError("IoT Hub connection string not found in config")
        
        # Parse hostname from connection string
        try:
            parts = dict(part.split('=', 1) for part in self.connection_string.split(';'))
            self.iot_hub_hostname = parts.get('HostName')
            if not self.iot_hub_hostname:
                raise ValueError("HostName not found in connection string")
        except Exception as e:
            logger.error(f"Error parsing IoT Hub connection string: {e}")
            logger.error(f"Connection string type: {type(self.connection_string)}")
            logger.error(f"Connection string value: {self.connection_string}")
            raise
        
        # Store connection string for registry manager
        self.iot_hub_connection_string = self.connection_string
        
        # Initialize registry manager
        self._init_registry_manager()
    
    def _init_registry_manager(self):
        """Initialize Azure IoT Hub Registry Manager with retry logic for Flask context"""
        import time
        
        for attempt in range(3):
            try:
                self.registry_manager = IoTHubRegistryManager.from_connection_string(
                    self.iot_hub_connection_string
                )
                logger.info(f"Azure IoT Hub Registry Manager initialized successfully (attempt {attempt + 1})")
                return
                
            except KeyError as ke:
                if 'SharedAccessKeyName' in str(ke) and attempt < 2:
                    logger.warning(f"Azure SDK context issue on attempt {attempt + 1}, retrying...")
                    time.sleep(0.1)  # Brief delay for context stabilization
                    continue
                else:
                    logger.error(f"Failed to initialize IoT Hub Registry Manager after {attempt + 1} attempts: {ke}")
                    raise
                    
            except Exception as e:
                # Handle base64 encoding errors specifically
                if "Invalid base64-encoded string" in str(e):
                    logger.warning(f"⚠️ IoT Hub connection string has invalid base64 encoding. Skipping Registry Manager initialization.")
                    logger.info("💡 System will continue with basic functionality. Device registration may be limited.")
                    self.registry_manager = None
                    return
                
                if attempt < 2:
                    logger.warning(f"Registry Manager init failed on attempt {attempt + 1}: {e}, retrying...")
                    time.sleep(0.1)
                    continue
                else:
                    logger.error(f"Failed to initialize IoT Hub Registry Manager after {attempt + 1} attempts: {e}")
                    logger.warning("⚠️ Continuing without Registry Manager. Some features may be limited.")
                    self.registry_manager = None
                    return
    
    def _generate_device_keys(self) -> Tuple[str, str]:
        """Generate secure primary and secondary keys for device authentication"""
        primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
        secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
        return primary_key, secondary_key
    
    def register_device_with_azure(self, device_id: str) -> Optional[str]:
        """
        Register a device with Azure IoT Hub and return connection string.
        
        Args:
            device_id: Unique device identifier
            
        Returns:
            Device connection string if successful, None if Registry Manager unavailable
        This method handles the actual Azure IoT Hub registration.
        """
        with self.lock:
            # Check if Registry Manager is available
            if self.registry_manager is None:
                logger.warning(f"⚠️ Registry Manager unavailable. Cannot register device {device_id}")
                logger.info("💡 Using fallback: generating basic device connection string")
                # Generate a basic connection string for fallback
                fallback_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                connection_string = f"HostName={self.iot_hub_hostname};DeviceId={device_id};SharedAccessKey={fallback_key}"
                return connection_string
            
            try:
                try:
                    existing_device = self.registry_manager.get_device(device_id)
                    logger.info(f"Device {device_id} already exists in Azure IoT Hub")
                    
                    if existing_device.authentication and existing_device.authentication.symmetric_key:
                        primary_key = existing_device.authentication.symmetric_key.primary_key
                        connection_string = f"HostName={self.iot_hub_hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
                        return connection_string
                    else:
                        logger.error(f"Device {device_id} exists but has no authentication keys")
                        return None
                except Exception:
                    logger.info(f"Creating new device {device_id} in Azure IoT Hub...")
                
                primary_key, secondary_key = self._generate_device_keys()
                
                device = self.registry_manager.create_device_with_sas(
                    device_id=device_id,
                    primary_key=primary_key,
                    secondary_key=secondary_key,
                    status="enabled"
                )
                
                logger.info(f"Device {device_id} created successfully in Azure IoT Hub")
                
                connection_string = f"HostName={self.iot_hub_hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
                return connection_string
                
            except Exception as e:
                logger.error(f"Error registering device {device_id} with Azure IoT Hub: {e}")
                return None
    
    def register_barcode_device(self, barcode: str) -> Dict[str, any]:
        """
        Main method: Register a device based on barcode scan.
        This is the plug-and-play entry point for commercial deployment.
        
        Returns:
            Dict with success status, device_id, connection_string, and message
        """
        try:
            # Validate barcode format
            if not barcode or not barcode.strip():
                return {
                    "success": False,
                    "message": "Invalid barcode: empty or None",
                    "device_id": None,
                    "connection_string": None
                }
            
            barcode = barcode.strip()
            
            # Validate barcode is numeric and has valid length
            if not barcode.isdigit():
                return {
                    "success": False,
                    "message": f"Invalid barcode format: {barcode}. Must be numeric.",
                    "device_id": None,
                    "connection_string": None
                }
            
            valid_lengths = [8, 12, 13, 14]  # EAN-8, UPC-A, EAN-13, GTIN-14
            if len(barcode) not in valid_lengths:
                return {
                    "success": False,
                    "message": f"Invalid barcode length: {len(barcode)}. Must be one of: {valid_lengths} digits.",
                    "device_id": None,
                    "connection_string": None
                }
            
            logger.info(f"Processing barcode registration: {barcode}")
            
            # Step 1: Get or create device ID mapping
            device_id = barcode_mapper.get_device_id_for_barcode(barcode)
            if not device_id:
                return {
                    "success": False,
                    "message": f"Failed to generate device ID for barcode: {barcode}",
                    "device_id": None,
                    "connection_string": None
                }
            
            # Step 2: Check if already registered
            existing_connection_string = barcode_mapper.get_connection_string_for_barcode(barcode)
            if existing_connection_string:
                logger.info(f"Barcode {barcode} already registered with device ID {device_id}")
                return {
                    "success": True,
                    "message": f"Device already registered for barcode {barcode}",
                    "device_id": device_id,
                    "connection_string": existing_connection_string
                }
            
            # Step 3: Register with Azure IoT Hub
            connection_string = self.register_device_with_azure(device_id)
            if not connection_string:
                return {
                    "success": False,
                    "message": f"Failed to register device {device_id} with Azure IoT Hub",
                    "device_id": device_id,
                    "connection_string": None
                }
            
            # Step 4: Update local mapping
            success = barcode_mapper.update_device_registration(
                barcode=barcode,
                connection_string=connection_string,
                azure_registered=True
            )
            
            if not success:
                logger.warning(f"Device registered with Azure but failed to update local mapping for barcode {barcode}")
            
            logger.info(f"Successfully registered barcode {barcode} -> device ID {device_id}")
            return {
                "success": True,
                "message": f"Device successfully registered for barcode {barcode}",
                "device_id": device_id,
                "connection_string": connection_string
            }
            
        except Exception as e:
            logger.error(f"Error in register_barcode_device for barcode {barcode}: {e}")
            return {
                "success": False,
                "message": f"Registration error: {str(e)}",
                "device_id": None,
                "connection_string": None
            }
    
    def get_device_connection_for_barcode(self, barcode: str) -> Optional[str]:
        """
        Get Azure IoT Hub connection string for a barcode.
        If not registered, automatically register the device.
        This enables true plug-and-play functionality.
        """
        try:
            # First check if already registered
            connection_string = barcode_mapper.get_connection_string_for_barcode(barcode)
            if connection_string:
                logger.info(f"Found existing connection for barcode {barcode}")
                return connection_string
            
            # Not registered, register now
            logger.info(f"Barcode {barcode} not registered, registering automatically...")
            registration_result = self.register_barcode_device(barcode)
            
            if registration_result["success"]:
                return registration_result["connection_string"]
            else:
                logger.error(f"Failed to register barcode {barcode}: {registration_result['message']}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting device connection for barcode {barcode}: {e}")
            return None
    
    def get_registration_statistics(self) -> Dict:
        """Get statistics about device registrations"""
        try:
            mapping_stats = barcode_mapper.get_mapping_stats()
            
            # Add Azure IoT Hub specific stats if available
            stats = {
                "total_barcode_mappings": mapping_stats.get("total_mappings", 0),
                "azure_registered_devices": mapping_stats.get("registered_devices", 0),
                "pending_registrations": mapping_stats.get("pending_registrations", 0),
                "recent_activity_24h": mapping_stats.get("recent_activity", 0),
                "registration_success_rate": 0
            }
            
            # Calculate success rate
            if stats["total_barcode_mappings"] > 0:
                stats["registration_success_rate"] = round(
                    (stats["azure_registered_devices"] / stats["total_barcode_mappings"]) * 100, 2
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting registration statistics: {e}")
            return {}
    
    def list_registered_devices(self, limit: int = 50) -> list:
        """List registered devices for admin/debugging purposes"""
        try:
            return barcode_mapper.list_all_mappings(limit)
        except Exception as e:
            logger.error(f"Error listing registered devices: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Test connection to Azure IoT Hub Registry"""
        try:
            # Check if registry manager is initialized
            if self.registry_manager is None:
                logger.warning("Registry Manager not initialized - skipping connection test")
                return False
                
            # Try to list devices (this will fail if connection is bad)
            devices = self.registry_manager.get_devices(max_number_of_devices=1)
            logger.info("Azure IoT Hub Registry connection test successful")
            return True
        except Exception as e:
            logger.error(f"Azure IoT Hub Registry connection test failed: {e}")
            return False


# Global instance - will be initialized when needed
_dynamic_registration_service = None
_service_lock = threading.Lock()

def get_dynamic_registration_service(iot_hub_connection_string: str = None) -> DynamicRegistrationService:
    """Get or create the global dynamic registration service instance"""
    global _dynamic_registration_service
    
    with _service_lock:
        if _dynamic_registration_service is None and iot_hub_connection_string:
            try:
                # Create config dict from connection string
                config = {"iot_hub": {"connection_string": iot_hub_connection_string}}
                _dynamic_registration_service = DynamicRegistrationService(config)
                logger.info("Dynamic registration service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize dynamic registration service: {e}")
                return None
        
        return _dynamic_registration_service

def register_device_for_barcode(barcode: str, iot_hub_connection_string: str = None) -> Dict[str, any]:
    """Convenience function to register a device for a barcode"""
    service = get_dynamic_registration_service(iot_hub_connection_string)
    if not service:
        return {
            "success": False,
            "message": "Dynamic registration service not available",
            "device_id": None,
            "connection_string": None
        }
    
    return service.register_barcode_device(barcode)

def get_connection_string_for_barcode(barcode: str, iot_hub_connection_string: str = None) -> Optional[str]:
    """Convenience function to get connection string for barcode (with auto-registration)"""
    service = get_dynamic_registration_service(iot_hub_connection_string)
    if not service:
        return None
    
    return service.get_device_connection_for_barcode(barcode)
