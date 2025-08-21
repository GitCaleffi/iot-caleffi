import logging
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from threading import RLock
from database.local_storage import LocalStorage
from iot.hub_client import HubClient
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.config import load_config
from utils.network_discovery import NetworkDiscovery

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Enhanced connection manager for handling offline/online state detection
    and automatic message queuing/retry for IoT Hub communications.
    """
    
    def __init__(self):
        self.local_db = LocalStorage()
        self.last_connection_check = 0
        # Connection status (cached for performance) - faster intervals for auto-refresh
        self.is_connected_to_internet = False
        self.is_connected_to_iot_hub = False
        self.raspberry_pi_devices_available = False
        self.last_connectivity_check = 0
        self.last_pi_check = 0
        self.connectivity_check_interval = 15  # seconds (faster for real-time updates)
        self.connection_check_interval = 15  # Alias for backward compatibility
        self.pi_check_interval = 20  # seconds (faster Pi discovery for auto-refresh)
        
        # Auto-refresh settings
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 10  # seconds
        self.auto_refresh_thread = None
        self.retry_thread = None
        self.retry_running = False
        self.lock = RLock()
        self.network_discovery = NetworkDiscovery()
        
        # Start background retry worker
        self._start_retry_thread()
        
        # Start auto-refresh worker for real-time status updates
        self._start_auto_refresh_worker()
        
    def check_internet_connectivity(self) -> bool:
        """
        Check if device has internet connectivity using multiple methods.
        
        Returns:
            bool: True if online, False otherwise
        """
        current_time = time.time()
        
        # Use cached result if recent check
        if current_time - self.last_connection_check < self.connection_check_interval:
            return self.is_connected_to_internet
            
        try:
            # Method 1: Ping Google DNS
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
                capture_output=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                return True
                
            # Method 2: Try alternative DNS server
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", "1.1.1.1"], 
                capture_output=True, 
                timeout=5
            )
            
            connected = result.returncode == 0
            self.is_connected_to_internet = connected
            self.last_connection_check = current_time
            return connected
            
        except Exception as e:
            logger.debug(f"Internet connectivity check failed: {e}")
            self.is_connected_to_internet = False
            self.last_connection_check = current_time
            return False
    
    def check_iot_hub_connectivity(self, device_id: str = None) -> bool:
        """
        Check if IoT Hub is accessible and device can connect.
        Uses multiple verification methods to ensure true connectivity.
        
        Args:
            device_id: Optional device ID to test specific device connection
            
        Returns:
            bool: True if IoT Hub is accessible, False otherwise
        """
        try:
            # First check internet connectivity
            if not self.check_internet_connectivity():
                logger.info("Internet connectivity check failed - marking IoT Hub as offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # Load configuration
            config = load_config()
            if not config:
                logger.info("Configuration not loaded - marking IoT Hub as offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # Get IoT Hub connection string
            iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
            if not iot_hub_connection_string:
                logger.info("No IoT Hub connection string - marking IoT Hub as offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # Test with dynamic registration service
            registration_service = get_dynamic_registration_service(iot_hub_connection_string)
            if not registration_service:
                logger.info("Failed to get registration service - marking IoT Hub as offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # Test connection to IoT Hub registry with timeout
            try:
                import socket
                # Extract hostname from connection string
                parts = dict(part.split('=', 1) for part in iot_hub_connection_string.split(';'))
                hostname = parts.get('HostName')
                
                if hostname:
                    # Test socket connection to IoT Hub hostname
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)  # 5 second timeout
                    result = sock.connect_ex((hostname, 443))  # HTTPS port
                    sock.close()
                    
                    if result != 0:
                        logger.info(f"Socket connection to {hostname}:443 failed - IoT Hub offline")
                        self.is_connected_to_iot_hub = False
                        return False
                        
            except Exception as socket_error:
                logger.info(f"Socket test failed: {socket_error} - marking IoT Hub as offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # Test connection to IoT Hub registry
            try:
                connected = registration_service.test_connection()
                if not connected:
                    logger.info("Registration service test_connection failed - IoT Hub offline")
                    self.is_connected_to_iot_hub = False
                    return False
            except Exception as reg_error:
                logger.info(f"Registration service test failed: {reg_error} - IoT Hub offline")
                self.is_connected_to_iot_hub = False
                return False
                
            # All tests passed
            logger.debug("All IoT Hub connectivity tests passed - IoT Hub online")
            self.is_connected_to_iot_hub = True
            return True
            
        except Exception as e:
            logger.info(f"IoT Hub connectivity check failed: {e} - marking IoT Hub as offline")
            self.is_connected_to_iot_hub = False
            return False
    
    def check_raspberry_pi_availability(self) -> bool:
        """
        Check if any Raspberry Pi devices are available on the network.
        
        Returns:
            bool: True if at least one Pi device is reachable
        """
        current_time = time.time()
        
        # Check if we need to refresh Pi availability status
        if current_time - self.last_pi_check > self.pi_check_interval:
            logger.info("Checking Raspberry Pi device availability...")
            
            try:
                # Discover Pi devices on the network
                devices = self.network_discovery.discover_raspberry_pi_devices(use_nmap=False)
                
                if devices:
                    # Check if any device has connectivity (SSH or Web)
                    reachable_devices = []
                    for device in devices:
                        ip = device['ip']
                        ssh_available = self.network_discovery.test_raspberry_pi_connection(ip, 22)
                        web_available = self.network_discovery.test_raspberry_pi_connection(ip, 5000)
                        
                        if ssh_available or web_available:
                            reachable_devices.append(device)
                            logger.info(f"✅ Raspberry Pi reachable: {ip} (SSH: {ssh_available}, Web: {web_available})")
                        else:
                            logger.info(f"❌ Raspberry Pi unreachable: {ip} (SSH: {ssh_available}, Web: {web_available})")
                    
                    self.raspberry_pi_devices_available = len(reachable_devices) > 0
                    
                    if self.raspberry_pi_devices_available:
                        logger.info(f"✅ Found {len(reachable_devices)} reachable Raspberry Pi device(s)")
                    else:
                        logger.info("❌ No reachable Raspberry Pi devices found")
                else:
                    logger.info("❌ No Raspberry Pi devices found on the network")
                    self.raspberry_pi_devices_available = False
                    
            except Exception as e:
                logger.error(f"Error checking Raspberry Pi availability: {e}")
                self.raspberry_pi_devices_available = False
            
            self.last_pi_check = current_time
        
        return self.raspberry_pi_devices_available
    
    def _start_auto_refresh_worker(self):
        """
        Start background thread for auto-refreshing connection status.
        This provides real-time updates of Pi connectivity status.
        """
        if not self.auto_refresh_enabled:
            return
            
        def auto_refresh_loop():
            """Background loop to continuously refresh connection status"""
            logger.info(f"🔄 Auto-refresh worker started (checking every {self.auto_refresh_interval} seconds)")
            
            while self.auto_refresh_enabled:
                try:
                    with self.lock:
                        # Force refresh of all connection statuses
                        old_internet = self.is_connected_to_internet
                        old_iot_hub = self.is_connected_to_iot_hub
                        old_pi = self.raspberry_pi_devices_available
                        
                        # Check all connectivity components
                        self.check_internet_connectivity()
                        self.check_iot_hub_connectivity()
                        self.check_raspberry_pi_availability()
                        
                        # Log status changes for real-time monitoring
                        if (old_internet != self.is_connected_to_internet or 
                            old_iot_hub != self.is_connected_to_iot_hub or 
                            old_pi != self.raspberry_pi_devices_available):
                            
                            internet_status = "✅" if self.is_connected_to_internet else "❌"
                            iot_hub_status = "✅" if self.is_connected_to_iot_hub else "❌"
                            pi_status = "✅" if self.raspberry_pi_devices_available else "❌"
                            
                            logger.info(f"🔄 Connection status changed - Internet: {internet_status}, IoT Hub: {iot_hub_status}, Pi: {pi_status}")
                            
                            # Special logging for Pi status changes
                            if old_pi != self.raspberry_pi_devices_available:
                                if self.raspberry_pi_devices_available:
                                    logger.info("🍓 ✅ Raspberry Pi came ONLINE - Messages will now be sent immediately")
                                else:
                                    logger.info("🍓 ❌ Raspberry Pi went OFFLINE - Messages will be saved locally")
                    
                    # Wait before next refresh
                    time.sleep(self.auto_refresh_interval)
                    
                except Exception as e:
                    logger.error(f"Error in auto-refresh worker: {e}")
                    time.sleep(30)  # Wait longer on error
        
        # Start background thread
        self.auto_refresh_thread = threading.Thread(target=auto_refresh_loop, daemon=True)
        self.auto_refresh_thread.start()
        logger.info("🔄 Auto-refresh connection monitoring started")
    
    def stop_auto_refresh(self):
        """Stop the auto-refresh worker"""
        self.auto_refresh_enabled = False
        if self.auto_refresh_thread:
            logger.info("🔄 Auto-refresh worker stopped")
    
    def send_message_with_retry(self, device_id: str, barcode: str, quantity: int = 1, 
                           message_type: str = "barcode_scan") -> Tuple[bool, str]:
        """
        Send message to IoT Hub with automatic offline queuing.
        Includes Raspberry Pi network detection to prevent sending when Pi is offline.
        
        Args:
            device_id: Device ID
            barcode: Scanned barcode
            quantity: Quantity (default 1)
            message_type: Type of message (barcode_scan, device_registration, etc.)
            
        Returns:
            Tuple[bool, str]: (success, status_message)
        """
        with self.lock:
            # First check if Raspberry Pi is reachable
            if not self.raspberry_pi_devices_available:
                # Save message for later retry
                timestamp = datetime.now()
                # Create a message dictionary with all the details
                message_data = {
                    "barcode": barcode,
                    "quantity": quantity,
                    "message_type": message_type,
                    "timestamp": timestamp.isoformat()
                }
                self.local_db.save_unsent_message(device_id, json.dumps(message_data), timestamp)
                return False, "⚠️ Raspberry Pi is offline. Message saved for retry when back online."
            try:
                # COMPREHENSIVE OFFLINE CHECK - Internet, IoT Hub, AND Raspberry Pi availability
                is_internet_online = self.is_connected_to_internet
                is_iot_hub_online = self.is_connected_to_iot_hub
                is_pi_available = self.check_raspberry_pi_availability()
                
                # If any component is offline, save message locally
                if not is_internet_online:
                    logger.info(f"Internet offline - saving message locally")
                    timestamp = datetime.now()
                    self.local_db.save_unsent_message(device_id, barcode, timestamp)
                    status_msg = "📱 Internet offline - Message saved locally for retry when connected"
                    return False, status_msg
                
                if not is_iot_hub_online:
                    logger.info(f"IoT Hub offline - saving message locally")
                    timestamp = datetime.now()
                    self.local_db.save_unsent_message(device_id, barcode, timestamp)
                    status_msg = "📱 IoT Hub offline - Message saved locally for retry when connected"
                    return False, status_msg
                
                if not is_pi_available:
                    logger.info(f"No Raspberry Pi devices reachable - saving message locally")
                    timestamp = datetime.now()
                    self.local_db.save_unsent_message(device_id, barcode, timestamp)
                    status_msg = "📱 Raspberry Pi offline - Message saved locally for retry when Pi is reachable"
                    return False, status_msg
                
                # Perform fresh connectivity check to be absolutely sure
                if not self.check_iot_hub_connectivity(device_id):
                    timestamp = datetime.now()
                    self.local_db.save_unsent_message(device_id, barcode, timestamp)
                    status_msg = "📱 IoT Hub unreachable - Message saved locally for retry when connected"
                    logger.info(f"IoT Hub connectivity check failed: Saved message for device {device_id}, barcode {barcode}")
                    return False, status_msg
                
                # All checks passed - attempt to send message
                logger.info(f"All connectivity checks passed (Internet: ✅, IoT Hub: ✅, Pi: ✅) - attempting to send message for device {device_id}")
                success, status_msg = self._send_message_now(device_id, barcode, quantity, message_type)
                
                if success:
                    logger.info(f"Message sent successfully for device {device_id}, barcode {barcode}")
                    return True, status_msg
                else:
                    # Save for retry even if we're "online" but send failed
                    timestamp = datetime.now()
                    self.local_db.save_unsent_message(device_id, barcode, timestamp)
                    retry_msg = "⚠️ Send failed - Message saved for retry"
                    logger.warning(f"Send failed: Saved message for device {device_id}, barcode {barcode}")
                    return False, f"{status_msg}. {retry_msg}"
                    
            except Exception as e:
                # Save message for retry on any error
                timestamp = datetime.now()
                self.local_db.save_unsent_message(device_id, barcode, timestamp)
                error_msg = f"❌ Error sending message: {str(e)} - Message saved for retry"
                logger.error(f"Error sending message for device {device_id}: {e}")
                return False, error_msg
    
    def _send_message_now(self, device_id: str, barcode: str, quantity: int, 
                         message_type: str) -> Tuple[bool, str]:
        """
        Internal method to send message immediately to IoT Hub.
        
        Returns:
            Tuple[bool, str]: (success, status_message)
        """
        try:
            # Load configuration
            config = load_config()
            if not config:
                return False, "Configuration not loaded"
                
            # Get IoT Hub connection string
            iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
            if not iot_hub_connection_string:
                return False, "No IoT Hub connection string configured"
                
            # Get device-specific connection string
            registration_service = get_dynamic_registration_service(iot_hub_connection_string)
            if not registration_service:
                return False, "Failed to initialize registration service"
                
            device_connection_string = registration_service.register_device_with_azure(device_id)
            if not device_connection_string:
                return False, f"Failed to get connection string for device {device_id}"
                
            # Create Hub client and send message
            hub_client = HubClient(device_connection_string)
            
            # Prepare message payload
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": quantity,
                "messageType": message_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send message
            success = hub_client.send_message(barcode, device_id)
            
            if success:
                return True, "✅ Message sent to IoT Hub successfully"
            else:
                return False, "⚠️ Failed to send message to IoT Hub"
                
        except Exception as e:
            logger.error(f"Error in _send_message_now: {e}")
            return False, f"Error sending message: {str(e)}"
    
    def _start_retry_thread(self):
        """
        Start background thread for automatic retry of unsent messages.
        """
        if self.retry_thread and self.retry_thread.is_alive():
            return
            
        self.retry_running = True
        self.retry_thread = threading.Thread(target=self._retry_worker, daemon=True)
        self.retry_thread.start()
        logger.info("Started automatic message retry thread")
    
    def _retry_worker(self):
        """
        Background worker that periodically tries to send unsent messages.
        """
        while self.retry_running:
            try:
                time.sleep(60)  # Check every minute
                
                # Only try if we have internet connectivity
                if self.check_internet_connectivity():
                    self._process_unsent_messages_background()
                    
            except Exception as e:
                logger.error(f"Error in retry worker: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _process_unsent_messages_background(self) -> int:
        """
        Process unsent messages in background mode.
        
        Returns:
            int: Number of messages successfully sent
        """
        try:
            with self.lock:
                # Get unsent messages
                unsent_messages = self.local_db.get_unsent_scans()
                if not unsent_messages:
                    return 0
                    
                success_count = 0
                
                # Process each message
                for message in unsent_messages[:10]:  # Process max 10 at a time
                    device_id = message.get("device_id")
                    barcode = message.get("barcode")
                    quantity = message.get("quantity", 1)
                    message_id = message.get("id")
                    
                    if not device_id or not barcode:
                        continue
                        
                    # Try to send message
                    success, _ = self._send_message_now(device_id, barcode, quantity, "barcode_scan")
                    
                    if success:
                        # Mark as sent in database
                        self.local_db.mark_sent_by_id(message_id)
                        success_count += 1
                        logger.info(f"Retry success: Sent message for device {device_id}, barcode {barcode}")
                    else:
                        # Stop processing if we can't send (likely offline again)
                        break
                        
                if success_count > 0:
                    logger.info(f"Background retry: Successfully sent {success_count} unsent messages")
                    
                return success_count
                
        except Exception as e:
            logger.error(f"Error processing unsent messages in background: {e}")
            return 0
    
    def get_connection_status(self) -> Dict:
        """
        Get current connection status information.
        
        Returns:
            Dict: Connection status details
        """
        # Get unsent message count
        unsent_messages = self.local_db.get_unsent_scans()
        unsent_count = len(unsent_messages) if unsent_messages else 0
        
        return {
            "internet_connected": self.is_connected_to_internet,
            "iot_hub_connected": self.is_connected_to_iot_hub,
            "last_check": datetime.fromtimestamp(self.last_connection_check).isoformat() if self.last_connection_check > 0 else None,
            "unsent_messages_count": unsent_count,
            "retry_thread_running": self.retry_running and self.retry_thread and self.retry_thread.is_alive()
        }
    
    def force_retry_unsent_messages(self) -> str:
        """
        Manually trigger retry of all unsent messages.
        
        Returns:
            str: Status message
        """
        try:
            if not self.check_internet_connectivity():
                return "❌ Device is offline. Cannot retry unsent messages."
                
            unsent_messages = self.local_db.get_unsent_scans()
            if not unsent_messages:
                return "✅ No unsent messages to retry."
                
            success_count = 0
            total_count = len(unsent_messages)
            
            for message in unsent_messages:
                device_id = message.get("device_id")
                barcode = message.get("barcode")
                quantity = message.get("quantity", 1)
                message_id = message.get("id")
                
                if not device_id or not barcode:
                    continue
                    
                success, _ = self._send_message_now(device_id, barcode, quantity, "barcode_scan")
                
                if success:
                    self.local_db.mark_sent_by_id(message_id)
                    success_count += 1
                    
            return f"📊 Processed {total_count} unsent messages. Success: {success_count}, Failed: {total_count - success_count}"
            
        except Exception as e:
            logger.error(f"Error in force retry: {e}")
            return f"❌ Error retrying messages: {str(e)}"
    
    def stop_retry_thread(self):
        """
        Stop the background retry thread.
        """
        self.retry_running = False
        if self.retry_thread and self.retry_thread.is_alive():
            self.retry_thread.join(timeout=5)
        logger.info("Stopped automatic message retry thread")

# Global connection manager instance
_connection_manager = None

def get_connection_manager() -> ConnectionManager:
    """
    Get the global connection manager instance.
    
    Returns:
        ConnectionManager: Global connection manager
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager
