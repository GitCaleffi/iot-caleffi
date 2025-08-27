import json
import logging
import subprocess
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
        
        # Initialize dynamic registration service for IoT Hub Pi detection
        self.dynamic_registration_service = None
        self._initialize_registration_service()
        
        # Start background retry worker
        self._start_retry_thread()
        
        # Start auto-refresh worker for real-time status updates
        self._start_auto_refresh_worker()
        
    def _initialize_registration_service(self):
        """Initialize dynamic registration service for IoT Hub operations"""
        try:
            config = load_config()
            if config:
                iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
                if iot_hub_connection_string:
                    self.dynamic_registration_service = get_dynamic_registration_service(iot_hub_connection_string)
                    if self.dynamic_registration_service:
                        logger.info("✅ Dynamic registration service initialized for automatic Pi detection")
                    else:
                        logger.warning("⚠️ Failed to initialize dynamic registration service")
                else:
                    logger.warning("⚠️ No IoT Hub connection string found in config")
            else:
                logger.warning("⚠️ Config not loaded for registration service initialization")
        except Exception as e:
            logger.error(f"Error initializing registration service: {e}")
            self.dynamic_registration_service = None
        
    def check_internet_connectivity(self) -> bool:
        """
        Check if device has internet connectivity using multiple methods.
        For live server deployment, prioritize Python-based checks.
        
        Returns:
            bool: True if online, False otherwise
        """
        current_time = time.time()
        
        # Use cached result if recent check
        if current_time - self.last_connection_check < self.connection_check_interval:
            logger.debug(f"Using cached connectivity result: {self.is_connected_to_internet}")
            return self.is_connected_to_internet
            
        logger.debug("Performing fresh internet connectivity check...")
        
        try:
            # Method 1: Python socket connection (works on live servers)
            import socket
            logger.debug("Trying Method 1: Python socket connection to Google DNS")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex(("8.8.8.8", 53))  # DNS port
                
            if result == 0:
                logger.debug("Method 1 SUCCESS - Internet connected via socket")
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                return True
                
            logger.debug("Method 1 FAILED - Trying Method 2")
            
            # Method 2: HTTP request to reliable endpoint
            logger.debug("Trying Method 2: HTTP request to Google")
            try:
                import urllib.request
                urllib.request.urlopen('http://www.google.com', timeout=5)
                logger.debug("Method 2 SUCCESS - Internet connected via HTTP")
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                return True
            except Exception as http_e:
                logger.debug(f"Method 2 FAILED: {http_e}")
            
            # Method 3: Fallback to ping (if available)
            logger.debug("Trying Method 3: ping 8.8.8.8")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
                capture_output=True, 
                timeout=5
            )
            
            if result.returncode == 0:
                logger.debug("Method 3 SUCCESS - Internet connected via ping")
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                return True
            
            logger.debug("All methods FAILED - No internet connectivity")
            self.is_connected_to_internet = False
            self.last_connection_check = current_time
            return False
            
        except Exception as e:
            logger.debug(f"Internet connectivity check failed with exception: {e}")
            import traceback
            logger.debug(f"Exception traceback: {traceback.format_exc()}")
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
            # Skip Pi availability check - always assume available
                
            # Check if we have basic internet connectivity (use cached value to avoid recursion)
            if not self.is_connected_to_internet:
                logger.debug("No internet connectivity - IoT Hub marked as offline")
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
        Check if Raspberry Pi devices are available via IoT Hub connectionState.
        Uses IoT Hub device twins instead of LAN ping for reliable cloud detection.
        """
        current_time = time.time()
        
        # Use shorter cache interval for more dynamic detection
        cache_interval = 10  # Check every 10 seconds instead of 30
        if current_time - self.last_pi_check < cache_interval:
            logger.debug(f"Using cached Pi availability result: {self.raspberry_pi_devices_available}")
            return self.raspberry_pi_devices_available
        
        try:
            # Use IoT Hub device connectionState instead of LAN ping
            connected_pi_devices = self._check_iot_hub_pi_devices()
            
            if connected_pi_devices:
                logger.debug(f"✅ Found {len(connected_pi_devices)} CONNECTED Pi device(s) in IoT Hub: {connected_pi_devices}")
                self.raspberry_pi_devices_available = True
            else:
                logger.debug("❌ No CONNECTED Pi devices found in IoT Hub")
                self.raspberry_pi_devices_available = False
                
            self.last_pi_check = current_time
            return self.raspberry_pi_devices_available
            
        except Exception as e:
            logger.debug(f"Error checking Pi availability via IoT Hub: {e}")
            # Fallback to LAN check only if IoT Hub fails
            return self._fallback_lan_pi_check()
    
    def _check_iot_hub_pi_devices(self) -> list:
        """Check IoT Hub for connected Raspberry Pi devices using device twins"""
        try:
            if not self.dynamic_registration_service or not self.dynamic_registration_service.registry_manager:
                logger.info("No IoT Hub registry manager available for Pi device check")
                return []
            
            registry_manager = self.dynamic_registration_service.registry_manager
            connected_pi_devices = []
            
            # Get list of known Pi device patterns
            pi_device_patterns = [
                "pi-",           # Device IDs starting with pi-
                "raspberry",     # Device IDs containing raspberry
                "rpi-",          # Device IDs starting with rpi-
            ]
            
            # Load config to get specific Pi device IDs if configured
            from utils.config import load_config
            config = load_config()
            pi_config = config.get("raspberry_pi", {})
            specific_pi_devices = pi_config.get("device_ids", [])
            
            logger.debug(f"🔍 Checking IoT Hub for Pi devices. Configured devices: {specific_pi_devices}")
            
            # Check specific Pi devices first
            for device_id in specific_pi_devices:
                logger.info(f"🔍 Checking configured Pi device: {device_id}")
                if self._check_device_connection_state(registry_manager, device_id):
                    logger.info(f"✅ Found CONNECTED Pi device: {device_id}")
                    connected_pi_devices.append(device_id)
                else:
                    logger.info(f"❌ Pi device {device_id} not connected or not found")
            
            # If no specific devices configured or none found, scan for Pi pattern devices
            if not specific_pi_devices or not connected_pi_devices:
                logger.info("🔍 Scanning IoT Hub for Pi devices with pattern matching...")
                try:
                    # Get device list (limited to avoid timeout)
                    devices = registry_manager.get_devices(max_count=100)
                    logger.info(f"📡 Found {len(devices)} total devices in IoT Hub")
                    
                    pi_candidates = []
                    for device in devices:
                        device_id_lower = device.device_id.lower()
                        
                        # Check if device ID matches Pi patterns
                        if any(pattern in device_id_lower for pattern in pi_device_patterns):
                            pi_candidates.append(device.device_id)
                            logger.info(f"🔍 Found Pi candidate device: {device.device_id}")
                            if self._check_device_connection_state(registry_manager, device.device_id):
                                logger.info(f"✅ Pi candidate {device.device_id} is CONNECTED")
                                connected_pi_devices.append(device.device_id)
                            else:
                                logger.info(f"❌ Pi candidate {device.device_id} is not connected")
                    
                    if not pi_candidates:
                        logger.info("❌ No devices found matching Pi patterns in IoT Hub")
                        # Log first few device IDs for debugging
                        sample_devices = [d.device_id for d in devices[:10]]
                        logger.info(f"📋 Sample device IDs in IoT Hub: {sample_devices}")
                                
                except Exception as e:
                    logger.info(f"Error scanning IoT Hub devices: {e}")
            
            logger.info(f"🏁 Final result: {len(connected_pi_devices)} connected Pi devices: {connected_pi_devices}")
            return connected_pi_devices
            
        except Exception as e:
            logger.debug(f"Error checking IoT Hub Pi devices: {e}")
            return []
    
    def _check_device_connection_state(self, registry_manager, device_id: str) -> bool:
        """Check if a specific device is connected via IoT Hub device twin"""
        try:
            # Get device twin to check connection state
            twin = registry_manager.get_twin(device_id)
            
            if twin and hasattr(twin, 'connection_state'):
                is_connected = twin.connection_state == 'Connected'
                logger.debug(f"Device {device_id} connectionState: {twin.connection_state}")
                return is_connected
            else:
                # Fallback: check device status
                device = registry_manager.get_device(device_id)
                if device and hasattr(device, 'status'):
                    is_enabled = device.status == 'enabled'
                    logger.debug(f"Device {device_id} status: {device.status}")
                    return is_enabled
                    
            return False
            
        except Exception as e:
            logger.debug(f"Error checking device {device_id} connection state: {e}")
            return False
    
    def _fallback_lan_pi_check(self) -> bool:
        """Fallback LAN check if IoT Hub method fails"""
        try:
            from utils.config import load_config
            config = load_config()
            user_pi_ip = config.get("raspberry_pi", {}).get("auto_detected_ip")
            
            if user_pi_ip and self._test_real_pi_connectivity(user_pi_ip):
                logger.debug(f"✅ Fallback LAN check: Pi {user_pi_ip} is responsive")
                self.raspberry_pi_devices_available = True
                return True
            else:
                logger.debug("❌ Fallback LAN check: No responsive Pi found")
                self.raspberry_pi_devices_available = False
                return False
                
        except Exception as e:
            logger.debug(f"Fallback LAN check error: {e}")
            self.raspberry_pi_devices_available = False
            return False
    
    def _fallback_lan_pi_check_list(self) -> list:
        """Fast fallback LAN check that returns list of connected Pi devices"""
        try:
            from utils.config import load_config
            config = load_config()
            user_pi_ip = config.get("raspberry_pi", {}).get("auto_detected_ip")
            
            if user_pi_ip and self._test_real_pi_connectivity(user_pi_ip):
                logger.debug(f"✅ Fast LAN check: Pi at {user_pi_ip} is responsive")
                # Generate device ID from IP for consistency
                device_id = f"pi-lan-{user_pi_ip.replace('.', '')}"
                return [device_id]
            else:
                logger.debug("❌ Fast LAN check: Configured Pi not responsive")
                return []
                
        except Exception as e:
            logger.debug(f"Fast LAN check error: {e}")
            return []
    
    def _test_real_pi_connectivity(self, ip: str) -> bool:
        """Test real-time connectivity to a potential Pi device - SSH REQUIRED"""
        import socket
        
        # STRICT: Only consider devices with SSH as true Raspberry Pi devices
        # This prevents false positives from web servers, routers, etc.
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 2 second timeout for real-time check
            result = sock.connect_ex((ip, 22))  # SSH port only
            sock.close()
            
            if result == 0:
                logger.debug(f"✅ {ip}:22 (SSH) is responsive - confirmed Pi device")
                return True
            else:
                logger.debug(f"❌ {ip}:22 (SSH) not responsive - not a Pi device")
                return False
        except Exception as e:
            logger.debug(f"❌ {ip} SSH test failed: {e}")
            return False
    
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
                        
                        # Re-initialize registration service if needed
                        if not self.dynamic_registration_service:
                            self._initialize_registration_service()
                        
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
            try:
                # Create consistent message data for storage
                timestamp = datetime.now()
                message_data = {
                    "barcode": barcode,
                    "quantity": quantity,
                    "message_type": message_type,
                    "timestamp": timestamp.isoformat()
                }
                message_json = json.dumps(message_data)
                
                # Check Pi availability first (highest priority)
                is_pi_available = self.check_raspberry_pi_availability()
                
                if not is_pi_available:
                    logger.info(f"Raspberry Pi offline - saving message locally for device {device_id}")
                    self.local_db.save_unsent_message(device_id, message_json, timestamp)
                    status_msg = "🍓 Raspberry Pi offline - Message saved locally for retry when Pi is connected"
                    return False, status_msg
                
                # Only check other connectivity if Pi is available
                is_internet_online = self.is_connected_to_internet
                is_iot_hub_online = self.is_connected_to_iot_hub
                
                # If internet is offline, save locally
                if not is_internet_online:
                    logger.info(f"Internet offline - saving message locally for device {device_id}")
                    self.local_db.save_unsent_message(device_id, message_json, timestamp)
                    status_msg = "📱 Internet offline - Message saved locally for retry when connected"
                    return False, status_msg
                
                # If IoT Hub is offline, save locally
                if not is_iot_hub_online:
                    logger.info(f"IoT Hub offline - saving message locally for device {device_id}")
                    self.local_db.save_unsent_message(device_id, message_json, timestamp)
                    status_msg = "📱 IoT Hub offline - Message saved locally for retry when connected"
                    return False, status_msg
                
                # Perform fresh connectivity check to be absolutely sure
                if not self.check_iot_hub_connectivity(device_id):
                    logger.info(f"IoT Hub connectivity check failed - saving message locally for device {device_id}")
                    self.local_db.save_unsent_message(device_id, message_json, timestamp)
                    status_msg = "📱 IoT Hub unreachable - Message saved locally for retry when connected"
                    return False, status_msg
                
                # All checks passed - Pi is online, attempt to send message
                logger.info(f"All connectivity checks passed (Internet: ✅, IoT Hub: ✅, Pi: ✅) - attempting to send message for device {device_id}")
                success, status_msg = self._send_message_now(device_id, barcode, quantity, message_type)
                
                if success:
                    logger.info(f"Message sent successfully for device {device_id}, barcode {barcode}")
                    return True, status_msg
                else:
                    # Save for retry even if we're "online" but send failed
                    logger.warning(f"Send failed despite online status - saving message locally for device {device_id}")
                    self.local_db.save_unsent_message(device_id, message_json, timestamp)
                    retry_msg = "⚠️ Send failed - Message saved for retry"
                    return False, f"{status_msg}. {retry_msg}"
                    
            except Exception as e:
                # Save message for retry on any error
                logger.error(f"Error sending message for device {device_id}: {e} - saving message locally")
                self.local_db.save_unsent_message(device_id, message_json, timestamp)
                error_msg = f"❌ Error sending message: {str(e)} - Message saved for retry"
                return False, error_msg
    
    def _send_message_now(self, device_id: str, barcode: str, quantity: int, 
                         message_type: str) -> Tuple[bool, str]:
        """
        Internal method to send message immediately to IoT Hub.
        SAFETY CHECK: Verifies Pi is available before sending.
        
        Returns:
            Tuple[bool, str]: (success, status_message)
        """
        try:
            # Check Pi availability before sending
            if not self.check_raspberry_pi_availability():
                return False, "🍓 Raspberry Pi offline - Cannot send message"
            
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
    
    def _initialize_registration_service(self):
        """Initialize dynamic registration service for IoT Hub operations"""
        try:
            config = load_config()
            if config:
                iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
                if iot_hub_connection_string:
                    self.dynamic_registration_service = get_dynamic_registration_service(iot_hub_connection_string)
                    if self.dynamic_registration_service:
                        logger.info("✅ Dynamic registration service initialized for automatic Pi detection")
                    else:
                        logger.warning("⚠️ Failed to initialize dynamic registration service")
                else:
                    logger.warning("⚠️ No IoT Hub connection string found in config")
            else:
                logger.warning("⚠️ Config not loaded for registration service initialization")
        except Exception as e:
            logger.error(f"Error initializing registration service: {e}")
            self.dynamic_registration_service = None
    
    def _retry_worker(self):
        """
        Background worker that periodically tries to send unsent messages.
        Only attempts to send if both internet and Raspberry Pi are available.
        """
        while self.retry_running:
            try:
                time.sleep(30)  # Check every 30 seconds for faster retry
                
                # Check both internet and Pi connectivity
                is_internet_online = self.check_internet_connectivity()
                is_pi_available = self.check_raspberry_pi_availability()
                
                logger.debug(f"Retry worker check - Internet: {'✅' if is_internet_online else '❌'}, Pi: {'✅' if is_pi_available else '❌'}")
                
                if is_internet_online and is_pi_available:
                    self._process_unsent_messages_background()
                else:
                    if not is_internet_online:
                        logger.info("Skipping message retry - Internet offline")
                    if not is_pi_available:
                        logger.info("Skipping message retry - Raspberry Pi offline")
                    
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
                        
                    # Check Pi availability before sending each message
                    if not self.check_raspberry_pi_availability():
                        logger.info("Pi went offline during background processing - stopping")
                        break
                        
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
