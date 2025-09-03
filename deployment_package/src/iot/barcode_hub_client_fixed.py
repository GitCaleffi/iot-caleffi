#!/usr/bin/env python3
"""
Fixed Barcode Hub Client for Inventory Tracking
Handles Azure IoT Hub communication with proper inventory tracking logic
"""

import json
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any

try:
    from azure.iot.device import IoTHubDeviceClient, Message
    from azure.iot.device.exceptions import ConnectionDroppedError, ConnectionFailedError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    logging.warning("Azure IoT SDK not available - running in offline mode")

from .dynamic_registration_service import get_dynamic_registration_service

logger = logging.getLogger(__name__)

class BarcodeHubClient:
    """
    Azure IoT Hub client for inventory tracking mode
    Implements one-device-per-barcode logic with quantity updates
    """
    
    def __init__(self, iot_hub_owner_connection_string: str):
        """Initialize the barcode hub client for inventory tracking"""
        logger.info("Initializing Barcode Hub Client for inventory tracking...")
        
        self.iot_hub_owner_connection_string = iot_hub_owner_connection_string
        self.client = None
        self.current_device_id = None
        self.current_barcode = None
        self.current_connection_string = None
        
        # Connection state
        self.connected = False
        self.messages_sent = 0
        self.last_message_time = None
        
        # Threading and retry logic
        self.connection_lock = threading.Lock()
        self.retry_count = 0
        self.max_retries = 3
        
        # Initialize dynamic registration service if Azure is available
        if AZURE_AVAILABLE:
            try:
                self.registration_service = get_dynamic_registration_service(iot_hub_owner_connection_string)
                if not self.registration_service:
                    logger.warning("Failed to initialize dynamic registration service - running in offline mode")
                    self.registration_service = None
            except Exception as e:
                logger.warning(f"Failed to initialize registration service: {e} - running in offline mode")
                self.registration_service = None
        else:
            self.registration_service = None
        
        logger.info("Barcode Hub Client initialized for inventory tracking")
    
    def register_and_send_barcode(self, barcode: str, device_id: str) -> bool:
        """
        Register new device with Azure IoT Hub and send initial barcode message.
        Used for first-time barcode scans (new products).
        
        Args:
            barcode: The barcode being scanned for the first time
            device_id: The device ID to register with Azure
            
        Returns:
            bool: True if registration and message sent successfully
        """
        try:
            logger.info(f"[INVENTORY] Registering NEW product: {barcode} -> {device_id}")
            
            if not AZURE_AVAILABLE or not self.registration_service:
                # Offline mode - just log the registration
                logger.info(f"[INVENTORY] OFFLINE MODE - New product registered: {barcode}")
                self.messages_sent += 1
                self.last_message_time = datetime.now()
                return True
            
            # Connect with barcode (this handles registration automatically)
            if not self.connect_with_barcode(barcode):
                logger.error(f"Failed to connect/register device for barcode: {barcode}")
                return False
            
            # Send initial barcode message with registration flag
            message_data = {
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'device_registration',
                'action': 'new_product_registered',
                'quantity': 1,
                'first_scan': True
            }
            
            success = self._send_message(message_data)
            if success:
                logger.info(f"[INVENTORY] ✅ NEW product registered and sent to Azure: {barcode}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error registering device and sending barcode: {e}")
            return False
    
    def send_inventory_update(self, barcode: str, device_id: str, quantity: int) -> bool:
        """
        Send inventory update message for existing product.
        Used for subsequent scans of the same barcode (quantity updates only).
        
        Args:
            barcode: The barcode being scanned (already registered)
            device_id: The device ID (already registered with Azure)
            quantity: Current total quantity for this barcode
            
        Returns:
            bool: True if inventory update sent successfully
        """
        try:
            logger.info(f"[INVENTORY] Updating EXISTING product: {barcode} -> Qty: {quantity}")
            
            if not AZURE_AVAILABLE or not self.registration_service:
                # Offline mode - just log the update
                logger.info(f"[INVENTORY] OFFLINE MODE - Inventory updated: {barcode} (Qty: {quantity})")
                self.messages_sent += 1
                self.last_message_time = datetime.now()
                return True
            
            # Ensure we're connected (reuse existing connection if possible)
            if not self.connected or self.current_barcode != barcode:
                if not self.connect_with_barcode(barcode):
                    logger.error(f"Failed to connect for inventory update: {barcode}")
                    return False
            
            # Send inventory update message (no registration needed)
            message_data = {
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'inventory_update',
                'action': 'quantity_updated',
                'quantity': quantity,
                'first_scan': False
            }
            
            success = self._send_message(message_data)
            if success:
                logger.info(f"[INVENTORY] ✅ EXISTING product inventory updated: {barcode} (Qty: {quantity})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending inventory update: {e}")
            return False

    def connect_with_barcode(self, barcode: str) -> bool:
        """
        Connect to Azure IoT Hub using only a barcode.
        This handles device registration automatically if needed.
        """
        try:
            if not AZURE_AVAILABLE or not self.registration_service:
                logger.info(f"Azure not available - simulating connection for barcode: {barcode}")
                return True
            
            logger.info(f"Connecting to Azure IoT Hub with barcode: {barcode}")
            
            # Get device connection string (with auto-registration)
            connection_string = self.registration_service.get_device_connection_for_barcode(barcode)
            if not connection_string:
                logger.error(f"Failed to get connection string for barcode: {barcode}")
                return False
            
            # Extract device ID from connection string
            try:
                parts = dict(part.split('=', 1) for part in connection_string.split(';'))
                device_id = parts.get('DeviceId')
                if not device_id:
                    logger.error("DeviceId not found in connection string")
                    return False
            except Exception as e:
                logger.error(f"Error parsing connection string: {e}")
                return False
            
            # Store current connection info
            self.current_barcode = barcode
            self.current_device_id = device_id
            self.current_connection_string = connection_string
            
            # Connect to Azure IoT Hub
            return self._connect_to_azure(connection_string)
            
        except Exception as e:
            logger.error(f"Error connecting with barcode {barcode}: {e}")
            return False
    
    def _connect_to_azure(self, connection_string: str) -> bool:
        """Connect to Azure IoT Hub with the given connection string"""
        if not AZURE_AVAILABLE:
            return True
            
        with self.connection_lock:
            try:
                # Disconnect existing client if any
                if self.client:
                    try:
                        self.client.disconnect()
                    except:
                        pass
                    self.client = None
                
                # Create new client
                self.client = IoTHubDeviceClient.create_from_connection_string(connection_string)
                
                # Connect to IoT Hub
                logger.info(f"Connecting to Azure IoT Hub with device ID: {self.current_device_id}")
                self.client.connect()
                
                # Wait a moment for connection to establish
                time.sleep(2)
                
                self.connected = True
                logger.info(f"✅ Connected to Azure IoT Hub: {self.current_device_id}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to Azure IoT Hub: {e}")
                self.connected = False
                return False
    
    def _send_message(self, message_data: dict) -> bool:
        """
        Internal method to send message to Azure IoT Hub
        
        Args:
            message_data: Dictionary containing message data
            
        Returns:
            bool: True if message sent successfully
        """
        try:
            if not AZURE_AVAILABLE or not self.client:
                # Offline mode - just log the message
                logger.info(f"[INVENTORY] OFFLINE MESSAGE: {json.dumps(message_data, indent=2)}")
                return True
            
            # Create and send message
            message_json = json.dumps(message_data)
            message = Message(message_json)
            message.content_encoding = "utf-8"
            message.content_type = "application/json"
            
            logger.info(f"Sending message to Azure IoT Hub: {message_data.get('message_type', 'unknown')}")
            self.client.send_message(message)
            
            # Update statistics
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            logger.info(f"✅ Message sent successfully to Azure: {message_data.get('barcode', 'unknown')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message to Azure: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from Azure IoT Hub"""
        try:
            if self.client:
                self.client.disconnect()
                self.client = None
            self.connected = False
            logger.info("Disconnected from Azure IoT Hub")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status information"""
        return {
            'connected': self.connected,
            'messages_sent': self.messages_sent,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'current_device_id': self.current_device_id,
            'current_barcode': self.current_barcode,
            'azure_available': AZURE_AVAILABLE
        }
