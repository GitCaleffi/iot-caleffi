#!/usr/bin/env python3
"""
Pi Device Reporter - Automatically registers Pi device with live server
Runs on the Raspberry Pi to report its status to the live server
"""

import requests
import time
import json
import subprocess
import socket
import logging
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PiDeviceReporter:
    def __init__(self, live_server_url="https://iot.caleffionline.it", report_interval=30):
        self.live_server_url = live_server_url.rstrip('/')
        self.report_interval = report_interval
        self.device_info = self._get_device_info()
        self.is_running = False
        
    def _get_device_info(self):
        """Get Pi device information"""
        try:
            # Get MAC address
            mac_address = self._get_mac_address()
            
            # Get IP address
            ip_address = self._get_ip_address()
            
            # Get hostname
            hostname = socket.gethostname()
            
            # Generate device ID from MAC
            device_id = mac_address.replace(':', '').lower()
            
            return {
                "device_id": device_id,
                "mac_address": mac_address,
                "ip_address": ip_address,
                "hostname": hostname,
                "device_type": "raspberry_pi",
                "status": "online",
                "last_seen": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            return None
    
    def _get_mac_address(self):
        """Get the MAC address of the Pi"""
        try:
            result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Fallback to wlan0
            result = subprocess.run(['cat', '/sys/class/net/wlan0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
                
        except Exception as e:
            logger.error(f"Error getting MAC address: {e}")
        
        return "unknown"
    
    def _get_ip_address(self):
        """Get the IP address of the Pi"""
        try:
            # Connect to a remote server to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unknown"
    
    def register_device(self):
        """Register this Pi device with the live server"""
        try:
            if not self.device_info:
                logger.error("No device info available for registration")
                return False
                
            registration_data = {
                **self.device_info,
                "action": "register",
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.live_server_url}/api/pi-device-register",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Device registered successfully: {self.device_info['device_id']}")
                return True
            else:
                logger.error(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to live server"""
        try:
            if not self.device_info:
                return False
                
            heartbeat_data = {
                "device_id": self.device_info['device_id'],
                "mac_address": self.device_info['mac_address'],
                "ip_address": self._get_ip_address(),  # Get current IP
                "status": "online",
                "action": "heartbeat",
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(
                f"{self.live_server_url}/api/pi-device-heartbeat",
                json=heartbeat_data,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"💓 Heartbeat sent: {self.device_info['device_id']}")
                return True
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
            return False
    
    def start_reporting(self):
        """Start the reporting service"""
        self.is_running = True
        
        # Initial registration
        logger.info("🚀 Starting Pi Device Reporter...")
        logger.info(f"📍 Device Info: {json.dumps(self.device_info, indent=2)}")
        
        if self.register_device():
            logger.info("✅ Initial registration successful")
        else:
            logger.error("❌ Initial registration failed")
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        logger.info(f"💓 Heartbeat service started (interval: {self.report_interval}s)")
        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Stopping Pi Device Reporter...")
            self.is_running = False
    
    def _heartbeat_loop(self):
        """Heartbeat loop running in separate thread"""
        while self.is_running:
            self.send_heartbeat()
            time.sleep(self.report_interval)
    
    def stop_reporting(self):
        """Stop the reporting service"""
        self.is_running = False

if __name__ == "__main__":
    # Configuration
    LIVE_SERVER_URL = "https://iot.caleffionline.it"  # Your live server URL
    REPORT_INTERVAL = 30  # Send heartbeat every 30 seconds
    
    reporter = PiDeviceReporter(LIVE_SERVER_URL, REPORT_INTERVAL)
    reporter.start_reporting()
