"""
Device Manager - Manages device identification, connectivity, and registration
"""
import time
import threading
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..utils.device_utils import get_device_id, check_internet_connectivity, get_network_interfaces
from ..utils.led_status_manager import LEDStatusManager
from ..iot.device_registry import DeviceRegistry

logger = logging.getLogger(__name__)

class DeviceManager:
    """Manages device identification, connectivity, and registration"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the device manager"""
        self.config = config
        self.device_id = None
        self.status = "initializing"
        self.last_heartbeat = None
        self.registration_complete = False
        self.gpio_available = self._check_gpio_available()
        
        # Initialize components
        self.led_manager = LEDStatusManager(gpio_available=self.gpio_available)
        self.device_registry = DeviceRegistry(config)
        
        # Start with connecting status
        self.led_manager.set_status(LEDStatusManager.STATUS_CONNECTING)
        
        # Start monitoring in background
        self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self.monitor_active = True
        self.monitor_thread.start()
        
        logger.info("✅ Device Manager initialized")
    
    def _check_gpio_available(self) -> bool:
        """Check if GPIO is available on this device"""
        try:
            import RPi.GPIO as GPIO
            return True
        except (ImportError, RuntimeError):
            return False
    
    def initialize_device(self) -> bool:
        """Initialize the device with a unique ID"""
        try:
            self.device_id = get_device_id()
            logger.info(f"Device ID: {self.device_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize device: {e}")
            self.led_manager.set_status(LEDStatusManager.STATUS_ERROR)
            return False
    
    def register_device(self) -> bool:
        """Register the device with the IoT server"""
        if not self.device_id:
            logger.error("Cannot register device: No device ID")
            return False
            
        self.led_manager.set_status(LEDStatusManager.STATUS_CONNECTING)
        
        # Get device information
        device_info = {
            "hostname": self._get_hostname(),
            "interfaces": get_network_interfaces(),
            "gpio_available": self.gpio_available,
            "startup_time": datetime.utcnow().isoformat()
        }
        
        # Try to register
        if self.device_registry.register_device(self.device_id, device_info):
            self.registration_complete = True
            self.status = "online"
            self.last_heartbeat = datetime.utcnow()
            self.led_manager.set_status(LEDStatusManager.STATUS_ONLINE)
            logger.info("✅ Device registered successfully")
            return True
        else:
            self.status = "registration_failed"
            self.led_manager.set_status(LEDStatusManager.STATUS_ERROR)
            logger.error("❌ Failed to register device")
            return False
    
    def send_heartbeat(self) -> bool:
        """Send a heartbeat to the IoT server"""
        if not self.registration_complete or not self.device_id:
            return False
            
        if self.device_registry.update_heartbeat():
            self.last_heartbeat = datetime.utcnow()
            return True
        return False
    
    def _monitor_worker(self):
        """Background worker to monitor device status"""
        logger.info("Starting device monitoring...")
        
        # Initial delay to let system settle
        time.sleep(5)
        
        # Main monitoring loop
        while self.monitor_active:
            try:
                # Check internet connectivity
                if not check_internet_connectivity():
                    logger.warning("No internet connectivity")
                    self.led_manager.set_status(LEDStatusManager.STATUS_OFFLINE)
                    time.sleep(5)
                    continue
                
                # Initialize device if needed
                if not self.device_id:
                    if not self.initialize_device():
                        time.sleep(5)
                        continue
                
                # Register if needed
                if not self.registration_complete:
                    self.register_device()
                else:
                    # Send periodic heartbeats when registered
                    self.send_heartbeat()
                
                # Short delay between checks
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitor worker: {e}", exc_info=True)
                time.sleep(5)
    
    def _get_hostname(self) -> str:
        """Get the system hostname"""
        try:
            import socket
            return socket.gethostname()
        except:
            return "unknown"
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current device status"""
        return {
            "device_id": self.device_id,
            "status": self.status,
            "registration_complete": self.registration_complete,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "internet_connected": check_internet_connectivity(),
            "gpio_available": self.gpio_available
        }
    
    def shutdown(self):
        """Clean up resources"""
        logger.info("Shutting down Device Manager...")
        self.monitor_active = False
        self.led_manager.cleanup()
        
        if self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        
        logger.info("Device Manager shutdown complete")
