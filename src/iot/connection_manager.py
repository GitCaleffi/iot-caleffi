"""
IoT Hub Connection Manager - Maintains persistent connections
"""
import logging
import threading
import time
from typing import Dict, Optional
from .hub_client import HubClient

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages persistent IoT Hub connections for multiple devices"""
    
    def __init__(self):
        self.connections: Dict[str, HubClient] = {}
        self.connection_lock = threading.Lock()
        self.keep_alive_thread = None
        self.keep_alive_running = False
        self.keep_alive_interval = 30  # seconds
        
    def get_connection(self, device_id: str, connection_string: str) -> Optional[HubClient]:
        """Get or create a persistent connection for a device"""
        with self.connection_lock:
            if device_id not in self.connections:
                logger.info(f"Creating new persistent connection for device: {device_id}")
                client = HubClient(connection_string, device_id)
                if client.connect():
                    self.connections[device_id] = client
                    self._start_keep_alive()
                    logger.info(f"✅ Persistent connection established for device: {device_id}")
                else:
                    logger.error(f"❌ Failed to establish connection for device: {device_id}")
                    return None
            else:
                client = self.connections[device_id]
                # Check if connection is still active
                if not client.connected:
                    logger.info(f"Reconnecting device: {device_id}")
                    if not client.connect():
                        logger.error(f"❌ Failed to reconnect device: {device_id}")
                        return None
                        
            return self.connections[device_id]
    
    def send_message(self, device_id: str, connection_string: str, barcode: str) -> bool:
        """Send message using persistent connection"""
        client = self.get_connection(device_id, connection_string)
        if client:
            return client.send_message(barcode, device_id)
        return False
    
    def _start_keep_alive(self):
        """Start keep-alive thread if not already running"""
        if not self.keep_alive_running:
            self.keep_alive_running = True
            self.keep_alive_thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
            self.keep_alive_thread.start()
            logger.info("🔄 Keep-alive thread started for persistent connections")
    
    def _keep_alive_loop(self):
        """Keep-alive loop to maintain connections"""
        while self.keep_alive_running:
            try:
                time.sleep(self.keep_alive_interval)
                
                with self.connection_lock:
                    disconnected_devices = []
                    
                    for device_id, client in self.connections.items():
                        if not client.connected:
                            logger.warning(f"⚠️ Device {device_id} disconnected, attempting reconnection...")
                            if not client.connect():
                                disconnected_devices.append(device_id)
                                logger.error(f"❌ Failed to reconnect device: {device_id}")
                            else:
                                logger.info(f"✅ Reconnected device: {device_id}")
                    
                    # Remove persistently disconnected devices
                    for device_id in disconnected_devices:
                        del self.connections[device_id]
                        logger.info(f"🗑️ Removed disconnected device: {device_id}")
                        
            except Exception as e:
                logger.error(f"❌ Keep-alive error: {e}")
    
    def disconnect_all(self):
        """Disconnect all devices"""
        with self.connection_lock:
            self.keep_alive_running = False
            
            for device_id, client in self.connections.items():
                try:
                    client.disconnect()
                    logger.info(f"🔌 Disconnected device: {device_id}")
                except Exception as e:
                    logger.error(f"❌ Error disconnecting device {device_id}: {e}")
            
            self.connections.clear()
            logger.info("🔌 All connections closed")
    
    def get_status(self) -> Dict:
        """Get status of all connections"""
        with self.connection_lock:
            status = {
                "total_connections": len(self.connections),
                "connected_devices": [],
                "disconnected_devices": [],
                "keep_alive_running": self.keep_alive_running
            }
            
            for device_id, client in self.connections.items():
                if client.connected:
                    status["connected_devices"].append({
                        "device_id": device_id,
                        "messages_sent": client.messages_sent,
                        "last_message": client.last_message_time
                    })
                else:
                    status["disconnected_devices"].append(device_id)
            
            return status

# Global connection manager instance
connection_manager = ConnectionManager()