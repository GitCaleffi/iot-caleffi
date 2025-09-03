#!/usr/bin/env python3
"""
IoT Hub-based Raspberry Pi Detection
Uses Azure IoT Hub Device Twin and connection state for reliable Pi detection
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import Twin, Device

logger = logging.getLogger(__name__)

class IoTHubPiDetection:
    """IoT Hub-based Raspberry Pi detection using Device Twin and connection state"""
    
    def __init__(self, connection_string: str):
        """
        Initialize IoT Hub Pi detection
        
        Args:
            connection_string: IoT Hub owner connection string
        """
        self.connection_string = connection_string
        self.registry_manager = None
        self._initialize_registry_manager()
    
    def _initialize_registry_manager(self):
        """Initialize IoT Hub Registry Manager"""
        try:
            self.registry_manager = IoTHubRegistryManager(self.connection_string)
            logger.info("✅ IoT Hub Registry Manager initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize IoT Hub Registry Manager: {e}")
            self.registry_manager = None
    
    def check_device_connection_state(self, device_id: str) -> Tuple[bool, str]:
        """
        Check device connection state via IoT Hub
        
        Args:
            device_id: Device ID to check
            
        Returns:
            Tuple of (is_connected, status_message)
        """
        if not self.registry_manager:
            return False, "IoT Hub Registry Manager not available"
        
        try:
            device = self.registry_manager.get_device(device_id)
            connection_state = device.connection_state
            
            if connection_state == "Connected":
                logger.info(f"✅ Device {device_id} connection state: {connection_state}")
                return True, f"Device connected to IoT Hub (state: {connection_state})"
            else:
                logger.warning(f"❌ Device {device_id} connection state: {connection_state}")
                return False, f"Device not connected to IoT Hub (state: {connection_state})"
                
        except Exception as e:
            logger.error(f"❌ Error checking device connection state for {device_id}: {e}")
            return False, f"Error checking connection state: {str(e)}"
    
    def check_device_twin_status(self, device_id: str, max_age_minutes: int = 2) -> Tuple[bool, Dict]:
        """
        Check device status via Device Twin reported properties
        
        Args:
            device_id: Device ID to check
            max_age_minutes: Maximum age of last_seen timestamp to consider device online
            
        Returns:
            Tuple of (is_online, status_info)
        """
        if not self.registry_manager:
            return False, {"error": "IoT Hub Registry Manager not available"}
        
        try:
            twin = self.registry_manager.get_twin(device_id)
            reported_props = twin.properties.reported
            
            status = reported_props.get("status", "unknown")
            last_seen_str = reported_props.get("last_seen", None)
            device_info = reported_props.get("device_info", {})
            
            status_info = {
                "status": status,
                "last_seen": last_seen_str,
                "device_info": device_info,
                "heartbeat_version": reported_props.get("heartbeat_version", "unknown")
            }
            
            # Check if status is online
            if status != "online":
                logger.warning(f"❌ Device {device_id} status: {status}")
                return False, status_info
            
            # Check last_seen timestamp
            if last_seen_str:
                try:
                    last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                    now = datetime.now(last_seen.tzinfo)
                    age_minutes = (now - last_seen).total_seconds() / 60
                    
                    if age_minutes <= max_age_minutes:
                        logger.info(f"✅ Device {device_id} online (last seen {age_minutes:.1f} minutes ago)")
                        status_info["age_minutes"] = age_minutes
                        return True, status_info
                    else:
                        logger.warning(f"❌ Device {device_id} last seen {age_minutes:.1f} minutes ago (too old)")
                        status_info["age_minutes"] = age_minutes
                        return False, status_info
                        
                except Exception as e:
                    logger.error(f"❌ Error parsing last_seen timestamp: {e}")
                    status_info["timestamp_error"] = str(e)
                    return False, status_info
            else:
                logger.warning(f"❌ Device {device_id} has no last_seen timestamp")
                return False, status_info
                
        except Exception as e:
            logger.error(f"❌ Error checking device twin for {device_id}: {e}")
            return False, {"error": str(e)}
    
    def check_pi_availability(self, device_ids: List[str]) -> Tuple[bool, Dict]:
        """
        Check availability of Raspberry Pi devices using both methods
        
        Args:
            device_ids: List of device IDs to check
            
        Returns:
            Tuple of (any_available, detailed_status)
        """
        if not self.registry_manager:
            return False, {"error": "IoT Hub Registry Manager not available"}
        
        detailed_status = {
            "method": "iot_hub_detection",
            "devices": {},
            "summary": {
                "total_devices": len(device_ids),
                "connected_devices": 0,
                "online_devices": 0,
                "available_devices": []
            }
        }
        
        any_available = False
        
        for device_id in device_ids:
            device_status = {
                "device_id": device_id,
                "connection_state": {"connected": False, "message": ""},
                "twin_status": {"online": False, "info": {}},
                "overall_available": False
            }
            
            # Check connection state
            is_connected, conn_message = self.check_device_connection_state(device_id)
            device_status["connection_state"] = {
                "connected": is_connected,
                "message": conn_message
            }
            
            if is_connected:
                detailed_status["summary"]["connected_devices"] += 1
            
            # Check Device Twin status
            is_online, twin_info = self.check_device_twin_status(device_id)
            device_status["twin_status"] = {
                "online": is_online,
                "info": twin_info
            }
            
            if is_online:
                detailed_status["summary"]["online_devices"] += 1
            
            # Device is available if either connected OR has recent online status
            device_available = is_connected or is_online
            device_status["overall_available"] = device_available
            
            if device_available:
                any_available = True
                detailed_status["summary"]["available_devices"].append(device_id)
                logger.info(f"✅ Device {device_id} is available via IoT Hub")
            else:
                logger.warning(f"❌ Device {device_id} is not available via IoT Hub")
            
            detailed_status["devices"][device_id] = device_status
        
        return any_available, detailed_status
    
    def get_device_ip_from_twin(self, device_id: str) -> Optional[str]:
        """
        Get device IP address from Device Twin reported properties
        
        Args:
            device_id: Device ID to check
            
        Returns:
            IP address if available, None otherwise
        """
        if not self.registry_manager:
            return None
        
        try:
            twin = self.registry_manager.get_twin(device_id)
            reported_props = twin.properties.reported
            device_info = reported_props.get("device_info", {})
            ip_address = device_info.get("ip_address")
            
            if ip_address and ip_address != "unknown":
                logger.info(f"📍 Device {device_id} IP from IoT Hub: {ip_address}")
                return ip_address
            else:
                logger.warning(f"📍 No IP address available for device {device_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error getting IP for device {device_id}: {e}")
            return None
