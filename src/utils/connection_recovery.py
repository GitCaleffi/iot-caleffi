"""
Connection Recovery Manager - Handles IoT Hub connection stability and automatic recovery
Fixes frequent disconnections and ensures reliable message delivery
"""
import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Optional, Callable
from threading import Lock, Event

from azure.iot.device import IoTHubDeviceClient
from azure.iot.device.exceptions import ConnectionFailedError, ConnectionDroppedError
from utils.dynamic_registration_service import get_dynamic_registration_service

logger = logging.getLogger(__name__)

class ConnectionRecovery:
    """Manages stable IoT Hub connections with automatic recovery"""
    
    def __init__(self):
        self.clients = {}  # device_id -> client mapping
        self.connection_states = {}  # device_id -> state mapping
        self.recovery_lock = Lock()
        self.recovery_threads = {}
        
        # Connection settings
        self.max_retry_attempts = 5
        self.retry_delay = 2  # seconds
        self.connection_timeout = 30  # seconds
        self.keepalive_interval = 60  # seconds
        
        # Callbacks
        self.connection_callbacks = []
    
    def get_stable_client(self, device_id: str) -> Optional[IoTHubDeviceClient]:
        """Get a stable IoT Hub client with automatic recovery"""
        with self.recovery_lock:
            # Check if we have a healthy client
            if device_id in self.clients:
                client = self.clients[device_id]
                if self._is_client_healthy(client):
                    return client
                else:
                    # Clean up unhealthy client
                    self._cleanup_client(device_id)
            
            # Create new stable client
            return self._create_stable_client(device_id)
    
    def _create_stable_client(self, device_id: str) -> Optional[IoTHubDeviceClient]:
        """Create a new stable IoT Hub client"""
        try:
            # Get device connection string using barcode as device_id
            registration_service = get_dynamic_registration_service()
            connection_string = registration_service.get_device_connection_for_barcode(device_id)
            
            if not connection_string:
                logger.error(f"❌ No connection string for device {device_id}")
                return None
            
            # Create client with optimized settings
            client = IoTHubDeviceClient.create_from_connection_string(
                connection_string,
                websockets=False  # Use MQTT over TCP for better stability
            )
            
            # Configure client for stability
            self._configure_client_for_stability(client)
            
            # Connect with retry
            if self._connect_with_retry(client, device_id):
                self.clients[device_id] = client
                self.connection_states[device_id] = {
                    'connected': True,
                    'last_connect': datetime.now(timezone.utc),
                    'retry_count': 0
                }
                
                # Start monitoring for this client
                self._start_client_monitoring(device_id, client)
                
                logger.info(f"✅ Stable client created for {device_id}")
                return client
            else:
                logger.error(f"❌ Failed to connect stable client for {device_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error creating stable client for {device_id}: {e}")
            return None
    
    def _configure_client_for_stability(self, client: IoTHubDeviceClient):
        """Configure client settings for maximum stability"""
        try:
            # Set connection options for stability
            client._mqtt_pipeline._pipeline[0]._keep_alive = self.keepalive_interval
            client._mqtt_pipeline._pipeline[0]._connection_retry = True
            client._mqtt_pipeline._pipeline[0]._connection_retry_interval = self.retry_delay
            
            # Set timeouts
            client._mqtt_pipeline._pipeline[0]._operation_timeout = self.connection_timeout
            
        except Exception as e:
            logger.warning(f"⚠️ Could not configure client stability settings: {e}")
    
    def _connect_with_retry(self, client: IoTHubDeviceClient, device_id: str) -> bool:
        """Connect client with retry logic"""
        for attempt in range(self.max_retry_attempts):
            try:
                logger.info(f"🔄 Connecting {device_id} (attempt {attempt + 1}/{self.max_retry_attempts})")
                
                client.connect()
                
                # Wait a moment to ensure connection is stable
                time.sleep(1)
                
                if client.connected:
                    logger.info(f"✅ {device_id} connected successfully")
                    return True
                else:
                    logger.warning(f"⚠️ {device_id} connection not confirmed")
                    
            except (ConnectionFailedError, ConnectionDroppedError) as e:
                logger.warning(f"⚠️ Connection attempt {attempt + 1} failed for {device_id}: {e}")
                if attempt < self.max_retry_attempts - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error connecting {device_id}: {e}")
                break
        
        return False
    
    def _is_client_healthy(self, client: IoTHubDeviceClient) -> bool:
        """Check if client is healthy and connected"""
        try:
            return client and client.connected
        except Exception:
            return False
    
    def _cleanup_client(self, device_id: str):
        """Clean up client resources"""
        try:
            if device_id in self.clients:
                client = self.clients[device_id]
                try:
                    if client.connected:
                        client.disconnect()
                except Exception as e:
                    logger.warning(f"⚠️ Error disconnecting client {device_id}: {e}")
                
                del self.clients[device_id]
            
            if device_id in self.connection_states:
                del self.connection_states[device_id]
            
            if device_id in self.recovery_threads:
                thread = self.recovery_threads[device_id]
                if thread.is_alive():
                    thread.join(timeout=2)
                del self.recovery_threads[device_id]
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up client {device_id}: {e}")
    
    def _start_client_monitoring(self, device_id: str, client: IoTHubDeviceClient):
        """Start monitoring thread for client health"""
        if device_id in self.recovery_threads:
            return  # Already monitoring
        
        def monitor_client():
            while device_id in self.clients:
                try:
                    time.sleep(30)  # Check every 30 seconds
                    
                    if device_id not in self.clients:
                        break
                    
                    current_client = self.clients.get(device_id)
                    if not self._is_client_healthy(current_client):
                        logger.warning(f"⚠️ Client {device_id} became unhealthy, recovering...")
                        self._recover_client(device_id)
                        
                except Exception as e:
                    logger.error(f"❌ Client monitoring error for {device_id}: {e}")
                    break
        
        thread = threading.Thread(target=monitor_client, daemon=True, name=f"Monitor-{device_id}")
        self.recovery_threads[device_id] = thread
        thread.start()
    
    def _recover_client(self, device_id: str):
        """Recover a failed client connection"""
        with self.recovery_lock:
            try:
                logger.info(f"🔄 Recovering client connection for {device_id}")
                
                # Clean up old client
                self._cleanup_client(device_id)
                
                # Create new client
                new_client = self._create_stable_client(device_id)
                
                if new_client:
                    logger.info(f"✅ Client {device_id} recovered successfully")
                    
                    # Notify callbacks
                    for callback in self.connection_callbacks:
                        try:
                            callback(device_id, True)
                        except Exception as e:
                            logger.error(f"❌ Recovery callback error: {e}")
                else:
                    logger.error(f"❌ Failed to recover client {device_id}")
                    
                    # Update state
                    self.connection_states[device_id] = {
                        'connected': False,
                        'last_attempt': datetime.now(timezone.utc),
                        'retry_count': self.connection_states.get(device_id, {}).get('retry_count', 0) + 1
                    }
                    
            except Exception as e:
                logger.error(f"❌ Client recovery error for {device_id}: {e}")
    
    def send_message_stable(self, device_id: str, message: str) -> bool:
        """Send message using stable client with automatic recovery"""
        try:
            client = self.get_stable_client(device_id)
            if not client:
                logger.error(f"❌ No stable client available for {device_id}")
                return False
            
            # Send message with timeout
            client.send_message(message)
            logger.info(f"✅ Message sent successfully via stable client for {device_id}")
            return True
            
        except (ConnectionFailedError, ConnectionDroppedError) as e:
            logger.warning(f"⚠️ Connection lost during send for {device_id}, recovering...")
            self._recover_client(device_id)
            return False
            
        except Exception as e:
            logger.error(f"❌ Error sending message for {device_id}: {e}")
            return False
    
    def add_connection_callback(self, callback: Callable[[str, bool], None]):
        """Add callback for connection state changes"""
        self.connection_callbacks.append(callback)
    
    def get_connection_status(self, device_id: str) -> Dict:
        """Get connection status for device"""
        state = self.connection_states.get(device_id, {})
        client = self.clients.get(device_id)
        
        return {
            'device_id': device_id,
            'connected': self._is_client_healthy(client),
            'client_exists': client is not None,
            'last_connect': state.get('last_connect'),
            'retry_count': state.get('retry_count', 0),
            'monitoring_active': device_id in self.recovery_threads
        }
    
    def cleanup_all(self):
        """Clean up all clients and resources"""
        logger.info("🧹 Cleaning up all connection recovery resources")
        
        device_ids = list(self.clients.keys())
        for device_id in device_ids:
            self._cleanup_client(device_id)

# Global instance
_connection_recovery = None
_recovery_lock = Lock()

def get_connection_recovery() -> ConnectionRecovery:
    """Get global connection recovery instance"""
    global _connection_recovery
    
    if _connection_recovery is None:
        with _recovery_lock:
            if _connection_recovery is None:
                _connection_recovery = ConnectionRecovery()
    
    return _connection_recovery
