#!/usr/bin/env python3
"""
System Status Monitor
Monitors system status and updates LED accordingly
"""

import time
import threading
import requests
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from led_controller import LEDStatusManager
from api.api_client import ApiClient
from utils.config import load_config

logger = logging.getLogger(__name__)

class SystemStatusMonitor:
    def __init__(self, use_gpio=True):
        """Initialize system status monitor"""
        self.led_manager = LEDStatusManager(use_gpio)
        self.api_client = ApiClient()
        self.config = load_config()
        
        self.monitoring = False
        self.monitor_thread = None
        self.check_interval = 30  # Check every 30 seconds
        
        # Status tracking
        self.device_registered = False
        self.verification_complete = False
        self.internet_available = True
        self.last_error = None
        
        # Initialize status from database
        self._load_initial_status()
    
    def _load_initial_status(self):
        """Load initial status from database and configuration"""
        try:
            # Check if device is registered
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            # Check for registered devices
            cursor.execute('SELECT COUNT(*) FROM device_registry WHERE status = "active"')
            device_count = cursor.fetchone()[0]
            self.device_registered = device_count > 0
            
            # Check for verification completion (look for verification barcodes)
            cursor.execute('SELECT COUNT(*) FROM device_notifications WHERE message LIKE "%Registration successful%"')
            verification_count = cursor.fetchone()[0]
            self.verification_complete = verification_count > 0
            
            conn.close()
            
            # Update LED status
            self._update_system_status()
            
            logger.info(f"Initial status - Device registered: {self.device_registered}, Verified: {self.verification_complete}")
            
        except Exception as e:
            logger.error(f"Failed to load initial status: {str(e)}")
            self.led_manager.set_error_state(True)
    
    def start_monitoring(self):
        """Start the system monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
            self.monitor_thread.start()
            logger.info("System status monitoring started")
    
    def stop_monitoring(self):
        """Stop the system monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.led_manager.cleanup()
        logger.info("System status monitoring stopped")
    
    def _monitor_worker(self):
        """Main monitoring worker thread"""
        while self.monitoring:
            try:
                # Check internet connectivity
                self._check_internet_connectivity()
                
                # Check device registration status
                self._check_device_status()
                
                # Update LED status
                self._update_system_status()
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring worker: {str(e)}")
                self.last_error = str(e)
                self._update_system_status()
                time.sleep(self.check_interval)
    
    def _check_internet_connectivity(self):
        """Check if internet is available"""
        try:
            # Try to reach the API
            response = requests.get("https://api2.caleffionline.it", timeout=5)
            self.internet_available = True
            if self.last_error and "internet" in self.last_error.lower():
                self.last_error = None  # Clear internet-related errors
        except requests.RequestException:
            self.internet_available = False
            self.last_error = "No internet connection"
        except Exception as e:
            self.internet_available = False
            self.last_error = f"Internet check failed: {str(e)}"
    
    def _check_device_status(self):
        """Check device registration and verification status"""
        try:
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            # Check device registration
            cursor.execute('SELECT COUNT(*) FROM device_registry WHERE status = "active"')
            device_count = cursor.fetchone()[0]
            self.device_registered = device_count > 0
            
            # Check verification status
            cursor.execute('SELECT COUNT(*) FROM device_notifications WHERE message LIKE "%Registration successful%"')
            verification_count = cursor.fetchone()[0]
            self.verification_complete = verification_count > 0
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to check device status: {str(e)}")
            self.last_error = f"Database error: {str(e)}"
    
    def _update_system_status(self):
        """Update LED status based on current system state"""
        try:
            # Clear error state if no current errors
            if self.last_error:
                self.led_manager.set_error_state(True)
            else:
                self.led_manager.set_error_state(False)
                
                # Update other statuses
                self.led_manager.update_internet_status(self.internet_available)
                self.led_manager.update_device_configuration(self.device_registered)
                self.led_manager.update_verification_status(self.verification_complete)
            
        except Exception as e:
            logger.error(f"Failed to update LED status: {str(e)}")
    
    def device_registration_started(self):
        """Called when device registration starts"""
        self.device_registered = True
        self.verification_complete = False
        self._update_system_status()
        logger.info("Device registration started - LED should show flashing green")
    
    def device_verification_completed(self):
        """Called when verification barcode is scanned"""
        self.verification_complete = True
        self._update_system_status()
        logger.info("Device verification completed - LED should show solid green")
    
    def report_error(self, error_message):
        """Report an error to the system"""
        self.last_error = error_message
        self._update_system_status()
        logger.error(f"System error reported: {error_message}")
    
    def clear_error(self):
        """Clear the current error state"""
        self.last_error = None
        self._update_system_status()
        logger.info("Error state cleared")
    
    def get_system_status(self):
        """Get comprehensive system status"""
        return {
            'device_registered': self.device_registered,
            'verification_complete': self.verification_complete,
            'internet_available': self.internet_available,
            'last_error': self.last_error,
            'led_status': self.led_manager.get_status_description(),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def force_status_update(self):
        """Force an immediate status update"""
        self._check_internet_connectivity()
        self._check_device_status()
        self._update_system_status()

def main():
    """Test the system status monitor"""
    print("System Status Monitor Test")
    print("=" * 50)
    
    monitor = SystemStatusMonitor(use_gpio=False)  # Use simulation mode
    
    try:
        # Start monitoring
        monitor.start_monitoring()
        
        print("Initial system status:")
        status = monitor.get_system_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        print("\nSimulating device registration workflow...")
        
        # Simulate registration process
        print("\n1. Starting device registration...")
        monitor.device_registration_started()
        time.sleep(3)
        
        print("\n2. Completing verification...")
        monitor.device_verification_completed()
        time.sleep(3)
        
        print("\n3. Simulating internet disconnection...")
        monitor.internet_available = False
        monitor._update_system_status()
        time.sleep(3)
        
        print("\n4. Restoring internet connection...")
        monitor.internet_available = True
        monitor._update_system_status()
        time.sleep(3)
        
        print("\n5. Simulating error...")
        monitor.report_error("Test error condition")
        time.sleep(3)
        
        print("\n6. Clearing error...")
        monitor.clear_error()
        time.sleep(2)
        
        print("\nFinal system status:")
        status = monitor.get_system_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        monitor.stop_monitoring()
        print("\nSystem status monitor test completed")

if __name__ == "__main__":
    main()