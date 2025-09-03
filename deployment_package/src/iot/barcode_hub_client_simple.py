#!/usr/bin/env python3
"""
Simplified Barcode Hub Client for Inventory Tracking
Handles Azure IoT Hub communication with inventory tracking support
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class BarcodeHubClient:
    """
    Simplified Azure IoT Hub client for inventory tracking mode
    """
    
    def __init__(self, iot_hub_owner_connection_string: str):
        """Initialize the simplified barcode hub client"""
        logger.info("Initializing Simplified Barcode Hub Client for inventory tracking...")
        self.iot_hub_owner_connection_string = iot_hub_owner_connection_string
        self.connected = False
        self.messages_sent = 0
        self.last_message_time = None
        logger.info("Simplified Barcode Hub Client initialized (offline mode)")
    
    def register_and_send_barcode(self, barcode: str, device_id: str) -> bool:
        """
        Register new device with Azure IoT Hub and send initial barcode message.
        Used for first-time barcode scans (new products).
        """
        try:
            logger.info(f"[INVENTORY] Registering new product: {barcode} -> {device_id}")
            
            # In offline mode, just log the registration
            message_data = {
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'device_registration',
                'action': 'new_product_registered',
                'quantity': 1
            }
            
            logger.info(f"[INVENTORY] New product registered: {json.dumps(message_data, indent=2)}")
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            # Return True for offline mode (would send to Azure in production)
            return True
            
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return False
    
    def send_inventory_update(self, barcode: str, device_id: str, quantity: int) -> bool:
        """
        Send inventory update message for existing product.
        Used for subsequent scans of the same barcode.
        """
        try:
            logger.info(f"[INVENTORY] Updating inventory: {barcode} -> Qty: {quantity}")
            
            # In offline mode, just log the update
            message_data = {
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'inventory_update',
                'action': 'quantity_updated',
                'quantity': quantity
            }
            
            logger.info(f"[INVENTORY] Inventory updated: {json.dumps(message_data, indent=2)}")
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            # Return True for offline mode (would send to Azure in production)
            return True
            
        except Exception as e:
            logger.error(f"Error sending inventory update: {e}")
            return False
    
    def send_barcode_message(self, barcode: str, metadata: dict = None) -> bool:
        """
        Send barcode message to Azure IoT Hub (legacy method for compatibility)
        """
        try:
            logger.info(f"[INVENTORY] Sending barcode message: {barcode}")
            
            message_data = {
                'barcode': barcode,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message_type': 'barcode_scan'
            }
            
            if metadata:
                message_data.update(metadata)
            
            logger.info(f"[INVENTORY] Barcode message: {json.dumps(message_data, indent=2)}")
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending barcode message: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Azure IoT Hub"""
        self.connected = False
        logger.info("Disconnected from Azure IoT Hub")
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status information"""
        return {
            'connected': self.connected,
            'messages_sent': self.messages_sent,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None
        }
