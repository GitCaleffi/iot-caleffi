#!/usr/bin/env python3
"""
Automatic Pi IoT Hub Heartbeat Service
Automatically maintains Pi connection to IoT Hub using dynamic device registration
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import time
import json
import logging
import socket
import threading
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from azure.iot.device import IoTHubDeviceClient
from utils.config import load_config
from utils.dynamic_registration_service import get_dynamic_registration_service

# Configure logging
log_file = os.path.join(os.path.dirname(__file__), 'logs', 'pi_heartbeat.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoPiHeartbeat:
    """Automatic Pi heartbeat service with dynamic device registration"""
    
    def __init__(self):
        self.config = load_config()
        self.client = None
        self.device_id = None
        self.connection_string = None
        self.running = False
        self.heartbeat_interval = 5  # seconds - ultra fast heartbeat
        self.reconnect_interval = 5  # seconds - ultra fast reconnect
        self.max_retries = 2  # minimal retries for fastest response
        self.connection_timeout = 5  # seconds - aggressive timeout
        self.heartbeat_timeout = 3  # seconds - fast heartbeat timeout
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="heartbeat")
        
        # Caching for performance
        self._system_info_cache = None
        self._cache_timestamp = 0
        self._cache_duration = 15  # shorter cache for more responsive updates
        self._device_id_cache = None
        self._hostname_cache = None
        self._reported_props_cache = None
        self._reported_props_timestamp = 0
        
    def get_pi_device_id(self):
        """Get Pi device ID from config or generate one (cached for performance)"""
        # Return cached device ID if available
        if self._device_id_cache:
            return self._device_id_cache
        
        pi_config = self.config.get("raspberry_pi", {})
        device_ids = pi_config.get("device_ids", [])
        
        if device_ids:
            # Use first configured device ID
            self._device_id_cache = device_ids[0]
            return self._device_id_cache
        
        # Generate device ID from MAC address
        mac_address = pi_config.get("mac_address", "")
        if mac_address:
            # Extract last 8 characters of MAC for device ID
            mac_clean = mac_address.replace(":", "").replace("-", "").lower()
            self._device_id_cache = f"pi-{mac_clean[-8:]}"
            return self._device_id_cache
        
        # Fallback to hostname-based ID (cached)
        if not self._hostname_cache:
            self._hostname_cache = socket.gethostname()
        self._device_id_cache = f"pi-{self._hostname_cache}"
        return self._device_id_cache
    
    def get_system_info(self):
        """Get current system information with aggressive caching for performance"""
        current_time = time.time()
        
        # Return cached data if still valid
        if (self._system_info_cache and 
            current_time - self._cache_timestamp < self._cache_duration):
            return self._system_info_cache
        
        # Use thread pool for non-blocking system info gathering
        try:
            future = self.executor.submit(self._get_system_info_worker)
            system_info = future.result(timeout=2)  # 2 second timeout
            
            # Cache the result
            self._system_info_cache = system_info
            self._cache_timestamp = current_time
            return system_info
            
        except (TimeoutError, Exception) as e:
            logger.warning(f"System info gathering failed/timed out: {e}")
            # Return cached data if available, even if expired
            if self._system_info_cache:
                return self._system_info_cache
            
            # Ultimate fallback
            fallback = {
                "hostname": self._hostname_cache or "unknown",
                "ip_address": "unknown",
                "uptime_seconds": int(time.time()),
                "mac_address": "unknown",
                "services": ["auto_heartbeat"]
            }
            self._system_info_cache = fallback
            self._cache_timestamp = current_time
            return fallback
    
    def _get_system_info_worker(self):
        """Worker method for gathering system information"""
        pi_config = self.config.get("raspberry_pi", {})
        
        # Use cached hostname if available
        if not self._hostname_cache:
            self._hostname_cache = socket.gethostname()
        
        # Use configured IP or detect current IP with aggressive timeout
        ip_address = pi_config.get("auto_detected_ip")
        if not ip_address:
            try:
                # Ultra-fast DNS resolution with 1 second timeout
                socket.setdefaulttimeout(1)
                ip_address = socket.gethostbyname(self._hostname_cache)
                socket.setdefaulttimeout(None)
            except (socket.timeout, socket.gaierror):
                ip_address = "unknown"
                socket.setdefaulttimeout(None)
        
        # Get uptime with error handling
        uptime_seconds = 0
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
        except (IOError, ValueError, IndexError):
            uptime_seconds = int(time.time())
        
        return {
            "hostname": self._hostname_cache,
            "ip_address": ip_address,
            "uptime_seconds": uptime_seconds,
            "mac_address": pi_config.get("mac_address", "unknown"),
            "services": ["barcode_scanner", "iot_client", "auto_heartbeat"]
        }
    
    def create_reported_properties(self):
        """Create Device Twin reported properties with caching"""
        current_time = time.time()
        
        # Cache reported properties for 5 seconds to avoid repeated system info calls
        if (self._reported_props_cache and 
            current_time - self._reported_props_timestamp < 5):
            # Update only timestamp for cached properties
            self._reported_props_cache["last_seen"] = datetime.utcnow().isoformat() + "Z"
            return self._reported_props_cache
        
        system_info = self.get_system_info()
        
        properties = {
            "status": "online",
            "last_seen": datetime.utcnow().isoformat() + "Z",
            "device_info": {
                "hostname": system_info.get("hostname", "unknown"),
                "ip_address": system_info.get("ip_address", "unknown"),
                "mac_address": system_info.get("mac_address", "unknown"),
                "uptime_seconds": system_info.get("uptime_seconds", 0),
                "services": system_info.get("services", [])
            },
            "heartbeat_version": "auto-2.1",
            "auto_maintenance": True
        }
        
        # Cache the properties
        self._reported_props_cache = properties.copy()
        self._reported_props_timestamp = current_time
        
        return properties
    
    def initialize_connection(self):
        """Initialize IoT Hub connection using dynamic registration with timeout"""
        try:
            self.device_id = self.get_pi_device_id()
            logger.info(f"🚀 Initializing auto heartbeat for device: {self.device_id}")
            
            # Use thread pool for timeout-controlled operations
            future = self.executor.submit(self._initialize_connection_worker)
            
            try:
                return future.result(timeout=self.connection_timeout)
            except TimeoutError:
                logger.error(f"❌ Connection initialization timed out after {self.connection_timeout}s")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize connection: {e}")
            return False
    
    def _initialize_connection_worker(self):
        """Worker method for connection initialization"""
        try:
            # Initialize dynamic registration service with config
            from utils.dynamic_registration_service import DynamicRegistrationService
            iot_hub_config = self.config.get("iot_hub", {})
            owner_connection_string = iot_hub_config.get("connection_string")
            
            if not owner_connection_string:
                logger.error("❌ No IoT Hub owner connection string found in config")
                return False
            
            registration_service = DynamicRegistrationService(owner_connection_string)
            logger.info("✅ Dynamic registration service initialized")
            
            # Register device and get connection string
            self.connection_string = registration_service.register_device_with_azure(self.device_id)
            if not self.connection_string:
                logger.error(f"❌ Failed to get connection string for device {self.device_id}")
                return False
            
            logger.info(f"✅ Got connection string for device {self.device_id}")
            
            # Create IoT Hub client
            self.client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
            
            # Connect to IoT Hub
            logger.info("🔗 Connecting to IoT Hub...")
            self.client.connect()
            logger.info("✅ Connected to IoT Hub successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Connection worker failed: {e}")
            return False
    
    def send_heartbeat(self):
        """Send heartbeat via Device Twin reported properties with aggressive timeout"""
        try:
            if not self.client:
                return False
            
            # Use thread pool for timeout-controlled heartbeat with faster timeout
            future = self.executor.submit(self._send_heartbeat_worker)
            
            try:
                return future.result(timeout=self.heartbeat_timeout)  # 3 second timeout
            except TimeoutError:
                logger.warning(f"⚠️ Heartbeat timed out after {self.heartbeat_timeout}s")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending heartbeat: {e}")
            return False
    
    def _send_heartbeat_worker(self):
        """Worker method for sending heartbeat"""
        try:
            reported_properties = self.create_reported_properties()
            self.client.patch_twin_reported_properties(reported_properties)
            
            logger.info(f"💓 Heartbeat sent for {self.device_id}")
            logger.debug(f"📊 Status: {reported_properties['status']}, IP: {reported_properties['device_info']['ip_address']}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Heartbeat worker failed: {e}")
            return False
    
    def disconnect(self):
        """Gracefully disconnect from IoT Hub with timeout"""
        try:
            if self.client:
                # Use thread pool for timeout-controlled disconnect
                future = self.executor.submit(self._disconnect_worker)
                
                try:
                    future.result(timeout=5)  # 5 second timeout for disconnect
                except TimeoutError:
                    logger.warning(f"⚠️ Disconnect timed out after 5s")
                
            # Cleanup executor
            self.executor.shutdown(wait=False)
                
        except Exception as e:
            logger.warning(f"⚠️ Error during disconnect: {e}")
    
    def _disconnect_worker(self):
        """Worker method for disconnection"""
        try:
            # Set status to offline before disconnecting
            offline_properties = {
                "status": "offline",
                "last_seen": datetime.utcnow().isoformat() + "Z"
            }
            self.client.patch_twin_reported_properties(offline_properties)
            logger.info("📴 Set status to offline in Device Twin")
            
            self.client.disconnect()
            logger.info("🔌 Disconnected from IoT Hub")
            
        except Exception as e:
            logger.warning(f"⚠️ Disconnect worker failed: {e}")
    
    def run(self):
        """Optimized main heartbeat loop with ultra-fast reconnection"""
        self.running = True
        heartbeat_count = 0
        retry_count = 0
        consecutive_failures = 0
        last_success_time = time.time()
        
        logger.info("🚀 Starting optimized Pi heartbeat service...")
        
        while self.running:
            try:
                current_time = time.time()
                
                # Initialize connection if needed
                if not self.client:
                    if not self.initialize_connection():
                        retry_count += 1
                        consecutive_failures += 1
                        
                        # Exponential backoff for repeated failures
                        backoff_time = min(self.reconnect_interval * (2 ** min(consecutive_failures - 1, 3)), 30)
                        logger.error(f"❌ Connection failed (attempt {retry_count}), retrying in {backoff_time}s...")
                        
                        # Interruptible sleep with faster granularity
                        for i in range(int(backoff_time * 2)):  # 0.5 second intervals
                            if not self.running:
                                break
                            time.sleep(0.5)
                        
                        if retry_count >= self.max_retries:
                            logger.error(f"❌ Max retries ({self.max_retries}) reached, stopping service")
                            break
                        continue
                    
                    # Reset counters on successful connection
                    retry_count = 0
                    consecutive_failures = 0
                    last_success_time = current_time
                    logger.info("✅ Connection established successfully")
                
                # Send heartbeat
                heartbeat_start = time.time()
                if self.send_heartbeat():
                    heartbeat_count += 1
                    consecutive_failures = 0
                    last_success_time = current_time
                    heartbeat_duration = time.time() - heartbeat_start
                    
                    # Log only every 10th heartbeat to reduce log noise
                    if heartbeat_count % 10 == 0:
                        logger.info(f"✅ Heartbeat #{heartbeat_count} sent (took {heartbeat_duration:.2f}s)")
                else:
                    consecutive_failures += 1
                    logger.warning(f"⚠️ Heartbeat failed (failure #{consecutive_failures})")
                    
                    # Force reconnection after 3 consecutive failures
                    if consecutive_failures >= 3:
                        logger.warning("🔄 Forcing reconnection due to repeated failures")
                        self.client = None
                
                # Adaptive sleep interval based on recent performance
                sleep_interval = self.heartbeat_interval
                if consecutive_failures > 0:
                    sleep_interval = max(1, self.heartbeat_interval // 2)  # Faster retry on failures
                
                # Ultra-responsive interruptible sleep
                for i in range(sleep_interval * 4):  # 0.25 second intervals
                    if not self.running:
                        break
                    time.sleep(0.25)
                
            except KeyboardInterrupt:
                logger.info("🛑 Keyboard interrupt received, stopping service...")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in heartbeat loop: {e}")
                self.client = None  # Force reconnection
                consecutive_failures += 1
                
                # Brief pause before retry
                for i in range(self.reconnect_interval * 2):  # 0.5 second intervals
                    if not self.running:
                        break
                    time.sleep(0.5)
        
        self.running = False
        self.disconnect()
        logger.info(f"🏁 Optimized Pi heartbeat service stopped (sent {heartbeat_count} heartbeats)")

def main():
    """Main entry point"""
    heartbeat_service = AutoPiHeartbeat()
    
    try:
        heartbeat_service.run()
    except Exception as e:
        logger.error(f"❌ Service failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
