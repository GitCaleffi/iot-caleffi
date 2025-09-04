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
from utils.led_status_manager import LEDStatusManager

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
        self.connectivity_check_interval = 10  # seconds (faster for real-time updates)
        self.connection_check_interval = 10  # Alias for backward compatibility
        self.pi_check_interval = 15  # seconds (faster Pi discovery for auto-refresh)
        
        # Auto-refresh settings - optimized for performance
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 30  # seconds (balanced for performance)
        self.auto_refresh_thread = None
        self.retry_thread = None
        self.retry_running = False
        self.lock = RLock()
        self.network_discovery = NetworkDiscovery()
        
        # Fast local cache for immediate responses
        self.fast_pi_cache = {'available': False, 'last_check': 0, 'cache_duration': 5}
        
        # Initialize dynamic registration service for IoT Hub Pi detection
        self.dynamic_registration_service = None
        
        # Initialize LED status manager
        try:
            # Check if we're on a Raspberry Pi first
            import platform
            import os
            
            # Check multiple indicators for Raspberry Pi
            is_pi = (
                os.path.exists('/proc/device-tree/model') and 
                'raspberry pi' in open('/proc/device-tree/model', 'r').read().lower()
            ) or (
                'arm' in platform.machine().lower() and 
                os.path.exists('/sys/class/gpio')
            )
            
            if is_pi:
                # Only try to import GPIO on actual Raspberry Pi
                import RPi.GPIO as GPIO
                self.led_manager = LEDStatusManager(gpio_available=True)
                logger.info("✅ LED status manager initialized with GPIO support")
            else:
                self.led_manager = LEDStatusManager(gpio_available=False)
                logger.info("ℹ️ LED status manager initialized in simulation mode (no GPIO)")
        except Exception as e:
            self.led_manager = LEDStatusManager(gpio_available=False)
            logger.info(f"ℹ️ LED status manager initialized in simulation mode: {e}")
        
        # Start continuous internet monitoring
        self.internet_monitor_running = True
        self.internet_monitor_thread = threading.Thread(target=self._continuous_internet_monitor, daemon=True)
        self.internet_monitor_thread.start()
        logger.info("🔄 Continuous internet monitoring started")
        self._initialize_registration_service()
        
        # Start background retry worker
        self._start_retry_thread()
        
        # Start auto-refresh worker for connection monitoring (reduced frequency for plug-and-play)
        self._start_auto_refresh_worker()
        
    def check_internet_connectivity(self) -> bool:
        """
        Check if device has internet connectivity using multiple methods.
        Enhanced to detect network interface status first.
        
        Returns:
            bool: True if online, False otherwise
        """
        current_time = time.time()
        
        # Store previous state to detect changes
        previous_internet_state = self.is_connected_to_internet
        
        try:
            # Method 0: Check network interface status first
            logger.debug("Checking network interface status...")
            if not self._check_network_interface():
                logger.debug("Network interface is down - no internet connectivity")
                self.is_connected_to_internet = False
                self.last_connection_check = current_time
                # Set LED to red blinking for no network
                if hasattr(self, 'led_manager'):
                    self.led_manager.set_status(self.led_manager.STATUS_ERROR)
                
                # Check if internet just went down
                if previous_internet_state and not self.is_connected_to_internet:
                    self.handle_internet_disconnection()
                
                return False
            
            # Method 1: Python socket connection (works on live servers)
            import socket
            logger.debug("Trying Method 1: Python socket connection to Google DNS")
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(3)  # Shorter timeout for faster detection
                result = sock.connect_ex(("8.8.8.8", 53))  # DNS port
                
            if result == 0:
                logger.debug("Method 1 SUCCESS - Basic internet connected")
                
                # Method 1.5: Test IoT Hub connectivity specifically
                logger.debug("Testing IoT Hub connectivity...")
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as iot_sock:
                        iot_sock.settimeout(3)
                        iot_result = iot_sock.connect_ex(("CaleffiIoT.azure-devices.net", 443))
                    
                    if iot_result == 0:
                        logger.debug("IoT Hub connectivity SUCCESS")
                        self.is_connected_to_internet = True
                        self.last_connection_check = current_time
                        # Set LED to green for internet connected
                        if hasattr(self, 'led_manager'):
                            self.led_manager.set_status(self.led_manager.STATUS_ONLINE)
                        return True
                    else:
                        logger.warning(f"⚠️ IoT Hub unreachable - connection error {iot_result}")
                        # Continue to other methods
                        
                except Exception as iot_e:
                    logger.warning(f"⚠️ IoT Hub test failed: {iot_e}")
                    # Continue to other methods
                
            logger.debug("Method 1 FAILED or IoT Hub unreachable - Trying Method 2")
            
            # Method 2: HTTP request to reliable endpoint
            logger.debug("Trying Method 2: HTTP request to Google")
            try:
                import urllib.request
                urllib.request.urlopen('http://www.google.com', timeout=3)
                logger.debug("Method 2 SUCCESS - Internet connected via HTTP")
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                # Set LED to green for internet connected
                if hasattr(self, 'led_manager'):
                    self.led_manager.set_status(self.led_manager.STATUS_ONLINE)
                return True
            except Exception as http_e:
                logger.debug(f"Method 2 FAILED: {http_e}")
            
            # Method 3: Fallback to ping (if available)
            logger.debug("Trying Method 3: ping 8.8.8.8")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"], 
                capture_output=True, 
                timeout=3
            )
            
            if result.returncode == 0:
                logger.debug("Method 3 SUCCESS - Internet connected via ping")
                self.is_connected_to_internet = True
                self.last_connection_check = current_time
                # Set LED to green for internet connected
                if hasattr(self, 'led_manager'):
                    self.led_manager.set_status(self.led_manager.STATUS_ONLINE)
                return True
            
            logger.debug("All methods FAILED - No internet connectivity")
            self.is_connected_to_internet = False
            self.last_connection_check = current_time
            # Set LED to red blinking for no internet
            if hasattr(self, 'led_manager'):
                self.led_manager.set_status(self.led_manager.STATUS_ERROR)
            
            # Check if internet just went down (state change from connected to disconnected)
            if previous_internet_state and not self.is_connected_to_internet:
                self.handle_internet_disconnection()
            
            return False
            
        except Exception as e:
            logger.debug(f"Internet connectivity check failed with exception: {e}")
            import traceback
            logger.debug(f"Exception traceback: {traceback.format_exc()}")
            self.is_connected_to_internet = False
            self.last_connection_check = current_time
            # Set LED to red blinking for connection error
            if hasattr(self, 'led_manager'):
                self.led_manager.set_status(self.led_manager.STATUS_ERROR)
            
            # Check if internet just went down (state change from connected to disconnected)
            if previous_internet_state and not self.is_connected_to_internet:
                self.handle_internet_disconnection()
            
            return False
    
    def _check_network_interface(self) -> bool:
        """
        Check if network interfaces are up and have IP addresses
        Returns True if at least one interface is up with an IP
        """
        try:
            import netifaces
            
            # Get all network interfaces
            interfaces = netifaces.interfaces()
            
            for interface in interfaces:
                # Skip loopback interface
                if interface == 'lo':
                    continue
                    
                try:
                    # Get interface addresses
                    addrs = netifaces.ifaddresses(interface)
                    
                    # Check if interface has IPv4 address
                    if netifaces.AF_INET in addrs:
                        ipv4_addrs = addrs[netifaces.AF_INET]
                        for addr_info in ipv4_addrs:
                            ip = addr_info.get('addr')
                            if ip and not ip.startswith('127.'):  # Not localhost
                                logger.debug(f"Active interface found: {interface} - {ip}")
                                return True
                                
                except Exception as e:
                    logger.debug(f"Error checking interface {interface}: {e}")
                    continue
            
            logger.debug("No active network interfaces found")
            return False
            
        except ImportError:
            # Fallback method using ip command if netifaces not available
            try:
                result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    # Look for UP interfaces with inet addresses (not 127.x.x.x)
                    lines = result.stdout.split('\n')
                    current_interface = None
                    interface_up = False
                    
                    for line in lines:
                        if ': ' in line and 'UP' in line:
                            interface_up = True
                            current_interface = line.split(':')[1].strip()
                        elif 'inet ' in line and interface_up and current_interface != 'lo':
                            ip = line.strip().split()[1].split('/')[0]
                            if not ip.startswith('127.'):
                                logger.debug(f"Active interface found: {current_interface} - {ip}")
                                return True
                        elif line.strip() == '':
                            interface_up = False
                            current_interface = None
                
                logger.debug("No active network interfaces found via ip command")
                return False
                
            except Exception as e:
                logger.debug(f"Network interface check failed: {e}")
                # If we can't check interfaces, assume they're up
                return True
    
    def _continuous_internet_monitor(self) -> None:
        """
        Continuously monitor internet connectivity in background thread
        Updates LED status and triggers disconnection handler when needed
        """
        logger.info("🔄 Starting continuous internet connectivity monitoring...")
        
        while self.internet_monitor_running:
            try:
                # Force fresh check by resetting cache
                self.last_connection_check = 0
                
                # Check internet connectivity (this will trigger LED updates)
                current_status = self.check_internet_connectivity()
                
                logger.debug(f"🔍 Internet monitor check: {current_status} | LED: {self.led_manager.current_status}")
                
                # Sleep for 3 seconds before next check (faster for testing)
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"Error in internet monitoring thread: {e}")
                time.sleep(5)  # Wait shorter on error
    
    def stop_monitoring(self) -> None:
        """Stop the continuous internet monitoring"""
        self.internet_monitor_running = False
        if hasattr(self, 'internet_monitor_thread'):
            self.internet_monitor_thread.join(timeout=2)
        logger.info("🛑 Internet monitoring stopped")
    
    def handle_internet_disconnection(self, device_id: str = None) -> None:
        """
        Handle internet disconnection events:
        1. Send alert message to queue for later delivery
        2. Blink red LED to indicate no internet
        3. Log the disconnection event
        """
        try:
            # Generate device ID if not provided
            if not device_id:
                from utils.dynamic_device_id import generate_dynamic_device_id
                device_id = generate_dynamic_device_id()
            
            # Create alert message for internet disconnection
            alert_message = {
                'device_id': device_id,
                'alert_type': 'internet_disconnected',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'message': 'Internet connection lost - device offline'
            }
            
            # Queue the alert message for later delivery
            logger.warning("🔴 Internet disconnected - queuing alert message")
            self.local_db.store_unsent_message(
                device_id=device_id,
                barcode="INTERNET_ALERT",
                quantity=1,
                additional_data=alert_message
            )
            
            # Set LED to red blinking
            if hasattr(self, 'led_manager'):
                self.led_manager.set_status(self.led_manager.STATUS_ERROR)
                logger.info("🔴 Red LED blinking - Internet connection lost")
            
        except Exception as e:
            logger.error(f"Error handling internet disconnection: {e}")
    
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
        Fast Pi availability check with optimized caching for performance.
        Uses fast local cache first, then falls back to comprehensive check.
        """
        current_time = time.time()
        
        # Fast cache check - immediate response for UI operations
        if current_time - self.fast_pi_cache['last_check'] < self.fast_pi_cache['cache_duration']:
            logger.debug(f"Using fast Pi cache: {self.fast_pi_cache['available']}")
            return self.fast_pi_cache['available']
        
        # Medium cache check - avoid expensive operations
        cache_interval = 15  # Balanced for server deployment with device twins
        if current_time - self.last_pi_check < cache_interval:
            logger.debug(f"Using cached Pi availability result: {self.raspberry_pi_devices_available}")
            # Update fast cache
            self.fast_pi_cache['available'] = self.raspberry_pi_devices_available
            self.fast_pi_cache['last_check'] = current_time
            return self.raspberry_pi_devices_available
        
        try:
            # Try LAN check first as it's more reliable for local network
            lan_pi_devices = self._fallback_lan_pi_check_list()
            if lan_pi_devices:
                logger.info(f"✅ LAN check found {len(lan_pi_devices)} responsive Pi device(s): {lan_pi_devices}")
                self.raspberry_pi_devices_available = True
                self.last_pi_check = current_time
                self.fast_pi_cache['available'] = True
                self.fast_pi_cache['last_check'] = current_time
                return True
                
            # Fall back to IoT Hub check if LAN check fails
            logger.debug("❌ No Pi devices found via LAN, checking IoT Hub...")
            connected_pi_devices = self._check_iot_hub_pi_devices()
            
            if connected_pi_devices:
                logger.info(f"✅ Found {len(connected_pi_devices)} CONNECTED Pi device(s) in IoT Hub: {connected_pi_devices}")
                self.raspberry_pi_devices_available = True
            else:
                logger.debug("❌ No CONNECTED Pi devices found in IoT Hub")
                self.raspberry_pi_devices_available = False
            
            self.last_pi_check = current_time
            # Update fast cache with result
            self.fast_pi_cache['available'] = self.raspberry_pi_devices_available
            self.fast_pi_cache['last_check'] = current_time
            return self.raspberry_pi_devices_available
            
        except Exception as e:
            logger.error(f"Error checking Pi availability: {e}", exc_info=True)
            # Fallback to direct LAN check
            return self._fallback_lan_pi_check()
            
    def _check_iot_hub_pi_devices(self) -> list:
        """Check IoT Hub for connected Raspberry Pi devices using device twins"""
        try:
            if not self.dynamic_registration_service:
                logger.debug("⚠️ Dynamic registration service not initialized")
                return []
                
            registry_manager = self.dynamic_registration_service.registry_manager
            if not registry_manager:
                logger.debug("⚠️ Registry manager not available")
                return []
                
            connected_pi_devices = []
            pi_device_patterns = [
                "pi-",           # Device IDs starting with pi-
                "raspberry",     # Device IDs containing raspberry
                "rpi-",          # Device IDs starting with rpi-
            ]
            
            try:
                logger.debug("🔍 Scanning IoT Hub for Pi devices...")
                
                # Get device list
                devices = registry_manager.get_devices()
                logger.debug(f"📡 Found {len(devices)} total devices in IoT Hub")
                
                pi_candidates = []
                # Limit processing to first 50 devices to avoid timeout
                for device in devices[:50]:
                    device_id_lower = device.device_id.lower()
                    
                    # Check if device ID matches Pi patterns
                    if any(pattern in device_id_lower for pattern in pi_device_patterns):
                        pi_candidates.append(device.device_id)
                        logger.debug(f"🔍 Found Pi candidate device: {device.device_id}")
                        if self._check_device_connection_state(registry_manager, device.device_id):
                            logger.info(f"✅ Pi candidate {device.device_id} is CONNECTED")
                            connected_pi_devices.append(device.device_id)
                        else:
                            logger.debug(f"❌ Pi candidate {device.device_id} is not connected")
                
                if not pi_candidates:
                    logger.debug("❌ No devices found matching Pi patterns in IoT Hub")
                    # Log first few device IDs for debugging
                    sample_devices = [d.device_id for d in devices[:5]]
                    logger.debug(f"📋 Sample device IDs in IoT Hub: {sample_devices}")
                
                return connected_pi_devices
                
            except Exception as e:
                logger.debug(f"Error scanning IoT Hub devices: {e}")
                logger.debug("🔄 Falling back to LAN-based Pi detection...")
                # Fallback to LAN detection if IoT Hub scan fails
                return self._fallback_lan_pi_check_list()
                
        except Exception as e:
            logger.debug(f"Error in _check_iot_hub_pi_devices: {e}")
            return []

    def _fallback_lan_pi_check_list(self) -> list:
        """
        Fast fallback LAN check that returns list of connected Pi devices.
        Enhanced with better error handling and logging.
        """
        try:
            # Check IoT connection status first - if connected, skip network discovery
            if self.is_connected_to_iot_hub:
                logger.info("✅ IoT Hub connected - starting registration instead of device discovery")
                # Start registration process instead of network discovery
                try:
                    from utils.dynamic_registration_service import get_dynamic_registration_service
                    registration_service = get_dynamic_registration_service()
                    if registration_service:
                        registration_service.start_registration_process()
                except Exception as e:
                    logger.debug(f"Registration service not available: {e}")
                
                # Return a mock connected device to indicate system is ready
                return [{
                    'ip': 'localhost',
                    'mac': 'local-device',
                    'hostname': 'iot-hub-connected'
                }]
            
            logger.info("🔍 Starting LAN-based Pi device discovery...")
            
            # Get list of Pi devices on the LAN
            pi_devices = self.network_discovery.discover_raspberry_pi_devices()
            
            if not pi_devices:
                logger.info("❌ No Pi devices found on LAN during initial scan")
                return []
                
            logger.info(f"📡 Found {len(pi_devices)} potential Pi devices on LAN")
            responsive_pis = []
            
            # Test connectivity to each Pi device
            for device in pi_devices:
                try:
                    ip = device.get('ip')
                    if not ip:
                        continue
                    
                    # Bypass connectivity test for forced detection
                    if device.get('discovery_method') == 'config_forced':
                        device_data = {
                            'ip': ip,
                            'mac': device.get('mac', 'unknown'),
                            'hostname': device.get('hostname', 'unknown')
                        }
                        logger.info(f"✅ Found responsive Pi (forced): {device_data}")
                        responsive_pis.append(device_data)
                        continue
                        
                    logger.debug(f"🔌 Testing connectivity to Pi at {ip}...")
                    if self._test_real_pi_connectivity(ip):
                        device_data = {
                            'ip': ip,
                            'mac': device.get('mac', 'unknown'),
                            'hostname': device.get('hostname', 'unknown')
                        }
                        logger.info(f"✅ Found responsive Pi: {device_data}")
                        responsive_pis.append(device_data)
                    else:
                        logger.debug(f"❌ Pi at {ip} did not respond to connectivity test")
                except Exception as e:
                    logger.warning(f"⚠️ Error testing Pi at {ip}: {e}")
            
            logger.info(f"🏁 LAN scan complete. Found {len(responsive_pis)} responsive Pi devices")
            return responsive_pis
                
        except Exception as e:
            logger.error(f"❌ Error in LAN Pi detection: {e}", exc_info=True)
            return []

    def _test_real_pi_connectivity(self, ip: str) -> bool:
        """
        Fast connectivity test to Pi device with multiple fallback methods.
        Returns True if the device responds to any of the tests.
        """
        import socket
        import subprocess
        
        # List of ports to check (SSH, HTTP, and common Pi services)
        ports_to_check = [22, 80, 5000, 8080]
        
        # Test 1: Check common open ports
        for port in ports_to_check:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)  # 1 second timeout
                result = sock.connect_ex((ip, port))
                sock.close()
                
                if result == 0:
                    logger.debug(f"✅ Port {port} is open on {ip}")
                    return True
                
                # Try next port if this one failed
                continue
                
            except Exception as e:
                logger.debug(f"⚠️ Port {port} check failed: {e}")
                continue
        
        # Test 2: Try ping if no ports responded
        try:
            # Use system ping with count=1 and timeout=1 second
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', ip],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                logger.debug(f"✅ Ping successful to {ip}")
                return True
                
        except Exception as e:
            logger.debug(f"⚠️ Ping test failed: {e}")
        
        # If we get here, all tests failed
        logger.debug(f"❌ All connectivity tests failed for {ip}")
        return False

    def _start_auto_refresh_worker(self):
        """
        Start background thread for auto-refreshing connection status.
        This provides real-time updates of Pi connectivity status.
        """
        def auto_refresh_loop():
            """Background loop to continuously refresh connection status"""
            logger.info(f"🔄 Auto-refresh worker started (checking every {self.auto_refresh_interval} seconds)")
            
            while self.auto_refresh_enabled:
                try:
                    with self.lock:
                        # Save old states to detect changes
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
                            old_iot_hub != self.is_connected_to_iot_hub):
                            status = self.get_connection_status()
                            logger.info(f"🔄 Connection status changed - Internet: {'✅' if status['internet_connected'] else '❌'}, IoT Hub: {'✅' if status['iot_hub_connected'] else '❌'}")
                        
                    time.sleep(self.auto_refresh_interval)
                    
                except Exception as e:
                    logger.error(f"Auto-refresh worker error: {e}")
                    time.sleep(120)  # Wait longer on error
        
        # Start worker thread
        refresh_thread = threading.Thread(target=auto_refresh_loop, daemon=True)
        refresh_thread.start()
        logger.info("🔄 Connection monitoring active (plug-and-play mode)")
    
    def stop_auto_refresh(self):
        """Stop the auto-refresh worker"""
        self.auto_refresh_enabled = False
        if hasattr(self, 'auto_refresh_thread') and self.auto_refresh_thread:
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

def get_connection_manager():
    """Get connection manager with proper Pi checking."""
    from utils.connection_manager import ConnectionManager
    
    # Initialize with actual Pi IP detection
    pi_ip = get_primary_raspberry_pi_ip()
    
    # Create connection manager with real Pi IP
    manager = ConnectionManager(pi_ip=pi_ip)
    return manager