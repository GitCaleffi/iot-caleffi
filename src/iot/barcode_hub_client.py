#!/usr/bin/env python3
"""
Barcode Hub Client - Azure IoT Hub client that works with barcodes only
Supports plug-and-play commercial deployment without manual device ID input
"""

from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionDroppedError, ConnectionFailedError
import json
import logging
from datetime import datetime, timezone
import time
import traceback
import threading
from typing import Optional
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.barcode_device_mapper import barcode_mapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class BarcodeHubClient:
    """
    Azure IoT Hub client that works with barcodes only.
    Automatically handles device registration and connection management.
    Designed for commercial scale plug-and-play deployment.
    """
    
    def __init__(self, iot_hub_owner_connection_string: str):
        """
        Initialize Barcode Hub Client
        
        Args:
            iot_hub_owner_connection_string: IoT Hub owner connection string for device registration
        """
        logger.info("Initializing Barcode Hub Client for commercial deployment...")
        
        self.iot_hub_owner_connection_string = iot_hub_owner_connection_string
        self.client = None
        self.current_device_id = None
        self.current_barcode = None
        self.current_connection_string = None
        
        # Connection state
        self.connected = False
        self.messages_sent = 0
        self.last_message_time = None
        
        # Connection settings
        self.connection_lock = threading.Lock()
        self.connection_timeout = 30  # seconds
        self.operation_timeout = 10   # seconds
        
        # Initialize dynamic registration service
        self.registration_service = get_dynamic_registration_service(iot_hub_owner_connection_string)
        if not self.registration_service:
            raise Exception("Failed to initialize dynamic registration service")
        
        logger.info("Barcode Hub Client initialized successfully")
    
    def connect_with_barcode(self, barcode: str) -> bool:
        """
        Connect to Azure IoT Hub using only a barcode.
        This is the main plug-and-play method for commercial deployment.
        
        Args:
            barcode: The barcode to use for device identification
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to Azure IoT Hub with barcode: {barcode}")
            
            # Validate barcode format
            if not barcode or not barcode.strip():
                logger.error("Invalid barcode: empty or None")
                return False
            
            barcode = barcode.strip()
            
            # Strict EAN validation
            try:
                from barcode_validator import validate_ean, BarcodeValidationError
                validate_ean(barcode)
                logger.info(f"Barcode {barcode} passed EAN validation")
            except BarcodeValidationError as e:
                logger.error(f"Invalid EAN barcode format: {e}")
                return False
            except ImportError:
                logger.warning("barcode_validator module not found, skipping EAN validation")
            
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
        with self.connection_lock:
            try:
                # Disconnect existing client if any
                self._safe_disconnect()
                
                # Create new client with operation timeout
                self.client = IoTHubDeviceClient.create_from_connection_string(
                    connection_string,
                    connection_timeout=self.connection_timeout,
                    operation_timeout=self.operation_timeout
                )
                
                # Set up event handlers
                self.client.on_connection_state_change = self._on_connection_state_change
                self.client.on_message_sent = self._on_message_sent
                
                # Connect to IoT Hub with timeout
                logger.info(f"Connecting to Azure IoT Hub with device ID: {self.current_device_id}")
                self.client.connect()
                
                # Wait for connection with timeout
                start_time = time.time()
                while time.time() - start_time < self.connection_timeout:
                    if hasattr(self.client, 'connected') and self.client.connected:
                        self.connected = True
                        logger.info(f"✓ Successfully connected to Azure IoT Hub with barcode {self.current_barcode}")
                        return True
                    time.sleep(0.1)
                
                logger.error("Connection to Azure IoT Hub timed out")
                self._safe_disconnect()
                return False
                
            except Exception as e:
                logger.error(f"Failed to connect to Azure IoT Hub: {e}")
                self._safe_disconnect()
                return False
    
    def send_inventory_update(self, barcode: str, device_id: str, quantity: int) -> bool:
        """
        Send inventory update message for existing product.
        Used for subsequent scans of the same barcode.
        
        Args:
            barcode: The barcode being scanned
            device_id: The device ID (already registered)
            quantity: Current total quantity for this barcode
            
        Returns:
            bool: True if inventory update sent successfully
        """
        try:
            logger.info(f"Sending inventory update: {barcode} -> Qty: {quantity}")
            
            # Ensure we're connected (reuse existing connection if possible)
            if not self.connected or self.current_barcode != barcode:
                if not self.connect_with_barcode(barcode):
                    logger.error(f"Failed to connect for inventory update: {barcode}")
                    return False
            
            # Send inventory update message
            message_data = {
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'inventory_update',
                'action': 'quantity_updated',
                'quantity': quantity
            }
            
            return self._send_message(message_data)
            
        except Exception as e:
            logger.error(f"Error sending inventory update: {e}")
            return False

    def send_barcode_message(self, barcode: str, metadata: dict = None) -> bool:
        """
        Send a barcode message to Azure IoT Hub and then disconnect.
        
        Args:
            barcode: The barcode to send
            metadata: Optional metadata to include with the message
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Connect if not already connected
            if not self.connected or not self.client or self.current_barcode != barcode:
                logger.info(f"Establishing connection for barcode: {barcode}")
                if not self.connect_with_barcode(barcode):
                    logger.error("Failed to connect to Azure IoT Hub")
                    return False
            
            # Prepare message payload
            message_data = {
                'barcode': barcode,
                'device_id': self.current_device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'barcode_scan'
            }
            
            # Add metadata if provided
            if metadata:
                message_data.update(metadata)
            
            # Send message and ensure we disconnect after
            try:
                return self._send_message(message_data)
            finally:
                self.disconnect()
            
        except Exception as e:
            logger.error(f"Error in send_barcode_message: {e}")
            self.disconnect()  # Ensure we clean up on error
            return False
    
    def _send_message(self, message_data: dict) -> bool:
        """
        Internal method to send message to Azure IoT Hub and ensure cleanup
        """
        try:
            if not self.connected or not self.client:
                logger.error("Not connected to IoT Hub when sending message")
                return False
                
            # Create and send message
            message_json = json.dumps(message_data)
            message = Message(message_json)
            message.content_encoding = "utf-8"
            message.content_type = "application/json"
            
            logger.info(f"Sending message to Azure IoT Hub: {message_data.get('message_type', 'unknown')}")
            
            # Send with timeout
            self.client.send_message(message, timeout=self.operation_timeout)
            
            # Update statistics
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            logger.info(f"✓ Message sent successfully: {message_data.get('barcode', 'unknown')}")
            return True

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def _on_connection_state_change(self, *args):
        """Handle connection state changes"""
        try:
            # Get connection status
            if self.client and hasattr(self.client, 'connected'):
                new_status = self.client.connected
                
                # Only log state changes
                if new_status != self.connected:
                    if new_status:
                        logger.info("Successfully connected to Azure IoT Hub")
                    else:
                        logger.info("Disconnected from Azure IoT Hub")
                    
                    self.connected = new_status
            
        except Exception as e:
            logger.error(f"Error in connection state change handler: {e}")
            self.connected = False
    
    def _on_message_sent(self, message_id):
        """Handle message sent confirmation"""
        logger.info(f"Message {message_id} confirmed by Azure IoT Hub")
    
    def _schedule_reconnect(self):
        """Reconnection is handled at the application level"""
        logger.debug("Automatic reconnection is disabled - handled at application level")
        return None
    
    def _reconnect(self):
        """Reconnection is handled at the application level"""
        logger.debug("Automatic reconnection is disabled - handled at application level")
        return False

    
    def get_status(self) -> dict:
        """Get current client status"""
        return {
            "connected": self.connected,
            "current_barcode": self.current_barcode,
            "current_device_id": self.current_device_id,
            "messages_sent": self.messages_sent,
            "last_message_time": self.last_message_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z' if self.last_message_time else None
        }
    
    def test_connection(self) -> bool:
        """Test connection to Azure IoT Hub"""
        try:
            if not self.connected or not self.client:
                return False
            
            # Try to send a test message (we'll use a dummy barcode for testing)
            test_data = {
                "test": True,
                "message": "Connection test"
            }
            
            # Don't actually send, just check if we can create the message
            test_message = Message(json.dumps(test_data))
            logger.info("Connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def _safe_disconnect(self):
        """Safely disconnect and clean up resources"""
        if self.client:
            try:
                if hasattr(self.client, 'shutdown'):
                    self.client.shutdown()
                elif hasattr(self.client, 'disconnect'):
                    self.client.disconnect()
            except Exception as e:
                logger.warning(f"Error during client shutdown: {e}")
            finally:
                self.client = None
                self.connected = False
    
    def disconnect(self):
        """Disconnect from Azure IoT Hub completely"""
        with self.connection_lock:
            logger.info("Disconnecting from Azure IoT Hub...")
            self._safe_disconnect()
            logger.info("Successfully disconnected from Azure IoT Hub")
    
    def get_registration_stats(self) -> dict:
        """Get registration statistics for monitoring"""
        try:
            return self.registration_service.get_registration_statistics()
        except Exception as e:
            logger.error(f"Error getting registration stats: {e}")
            return {}
    
    def list_registered_devices(self, limit: int = 50) -> list:
        """List registered devices for admin purposes"""
        try:
            return self.registration_service.list_registered_devices(limit)
        except Exception as e:
            logger.error(f"Error listing registered devices: {e}")
            return []


# Convenience functions for easy integration
def create_barcode_hub_client(iot_hub_owner_connection_string: str) -> BarcodeHubClient:
    """Create a new barcode hub client"""
    return BarcodeHubClient(iot_hub_owner_connection_string)

def send_barcode_to_hub(barcode: str, iot_hub_owner_connection_string: str, additional_data: dict = None) -> bool:
    """Convenience function to send a barcode to Azure IoT Hub"""
    try:
        client = BarcodeHubClient(iot_hub_owner_connection_string)
        return client.send_barcode_message(barcode, additional_data)
    except Exception as e:
        logger.error(f"Error sending barcode to hub: {e}")
        return False
