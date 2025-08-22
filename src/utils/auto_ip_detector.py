"""
Automatic Raspberry Pi IP Detection and Configuration Service

This module automatically detects when Raspberry Pi devices connect to the network
and updates the configuration file with their IP addresses without manual intervention.
"""

import time
import threading
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
from utils.network_discovery import NetworkDiscovery
from utils.config import load_config, save_config

logger = logging.getLogger(__name__)

class AutoIPDetector:
    """
    Automatic Raspberry Pi IP detection and configuration service.
    
    This service runs in the background and automatically:
    1. Monitors network for new Raspberry Pi devices
    2. Detects when Pi devices connect/disconnect
    3. Updates configuration file automatically
    4. Provides real-time Pi availability status
    """
    
    def __init__(self, scan_interval: int = 30):
        """
        Initialize the automatic IP detector.
        
        Args:
            scan_interval (int): How often to scan for Pi devices (seconds)
        """
        self.scan_interval = scan_interval
        self.running = False
        self.scan_thread = None
        self.discovery = NetworkDiscovery()
        self.known_devices: Set[str] = set()  # Track known Pi IPs
        self.current_primary_ip: Optional[str] = None
        self.last_scan_time = None
        
        # Load existing configuration
        self._load_existing_config()
        
    def _load_existing_config(self):
        """Load existing Pi configuration from config file."""
        try:
            config = load_config()
            pi_config = config.get('raspberry_pi', {})
            
            if pi_config.get('auto_detected_ip'):
                self.current_primary_ip = pi_config['auto_detected_ip']
                self.known_devices.add(self.current_primary_ip)
                logger.info(f"🔄 Loaded existing Pi IP from config: {self.current_primary_ip}")
                
        except Exception as e:
            logger.warning(f"Could not load existing Pi config: {e}")
    
    def start_monitoring(self):
        """Start the automatic IP detection service."""
        if self.running:
            logger.warning("Auto IP detector is already running")
            return
            
        self.running = True
        self.scan_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.scan_thread.start()
        logger.info(f"🚀 Started automatic Pi IP detection service (scan every {self.scan_interval}s)")
    
    def stop_monitoring(self):
        """Stop the automatic IP detection service."""
        self.running = False
        if self.scan_thread:
            self.scan_thread.join(timeout=5)
        logger.info("🛑 Stopped automatic Pi IP detection service")
    
    def _monitoring_loop(self):
        """Main monitoring loop that runs in background thread."""
        logger.info("🔍 Starting automatic Pi monitoring loop...")
        
        while self.running:
            try:
                self._scan_and_update()
                time.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.scan_interval)
    
    def _scan_and_update(self):
        """Scan for Pi devices and update configuration if needed."""
        try:
            logger.debug("🔍 Scanning for Raspberry Pi devices...")
            
            # Discover Pi devices on network
            pi_devices = self.discovery.discover_raspberry_pi_devices()
            current_ips = {device['ip'] for device in pi_devices}
            
            self.last_scan_time = datetime.now(timezone.utc)
            
            # Check for new devices
            new_devices = current_ips - self.known_devices
            if new_devices:
                logger.info(f"🆕 New Raspberry Pi devices detected: {list(new_devices)}")
                self._handle_new_devices([d for d in pi_devices if d['ip'] in new_devices])
            
            # Check for disconnected devices
            disconnected = self.known_devices - current_ips
            if disconnected:
                logger.info(f"📴 Raspberry Pi devices disconnected: {list(disconnected)}")
                self._handle_disconnected_devices(disconnected)
            
            # Update known devices
            self.known_devices = current_ips
            
            # Update primary IP if needed
            if pi_devices and (not self.current_primary_ip or self.current_primary_ip not in current_ips):
                self._update_primary_device(pi_devices)
                
        except Exception as e:
            logger.error(f"Error during Pi scan: {e}")
    
    def _handle_new_devices(self, new_devices: List[Dict]):
        """Handle newly detected Pi devices."""
        for device in new_devices:
            ip = device['ip']
            mac = device.get('mac', 'Unknown')
            hostname = device.get('hostname', 'Unknown')
            
            logger.info(f"🔗 New Pi connected: {ip} (MAC: {mac}, Hostname: {hostname})")
            
            # Test connectivity
            ssh_available = device.get('ssh_available', False)
            web_available = device.get('web_available', False)
            
            logger.info(f"   • SSH Available: {'✅' if ssh_available else '❌'}")
            logger.info(f"   • Web Service: {'✅' if web_available else '❌'}")
    
    def _handle_disconnected_devices(self, disconnected_ips: Set[str]):
        """Handle Pi devices that have disconnected."""
        for ip in disconnected_ips:
            logger.info(f"📴 Pi disconnected: {ip}")
            
            # If the primary Pi disconnected, we'll select a new one in the next scan
            if ip == self.current_primary_ip:
                logger.warning(f"⚠️ Primary Pi {ip} disconnected - will select new primary")
                self.current_primary_ip = None
    
    def _update_primary_device(self, pi_devices: List[Dict]):
        """Update the primary Pi device configuration."""
        if not pi_devices:
            return
            
        # Sort devices by priority (same logic as main app)
        def device_priority(device):
            score = 0
            if device.get('web_available'):
                score += 20
            if device.get('ssh_available'):
                score += 10
            mac = device.get('mac', '').lower()
            pi_mac_prefixes = ['b8:27:eb', 'dc:a6:32', 'e4:5f:01', '28:cd:c1', 'd8:3a:dd', '2c:cf:67']
            if any(mac.startswith(prefix) for prefix in pi_mac_prefixes):
                score += 15
            hostname = device.get('hostname', '').lower()
            if any(keyword in hostname for keyword in ['pi', 'raspberry', 'raspberrypi']):
                score += 5
            return score
        
        sorted_devices = sorted(pi_devices, key=device_priority, reverse=True)
        primary_device = sorted_devices[0]
        new_primary_ip = primary_device['ip']
        
        # Only update if primary changed
        if new_primary_ip != self.current_primary_ip:
            self.current_primary_ip = new_primary_ip
            self._save_primary_to_config(primary_device)
            logger.info(f"🎯 Updated primary Pi: {new_primary_ip}")
    
    def _save_primary_to_config(self, device: Dict):
        """Automatically save the primary Pi device to configuration file."""
        try:
            config = load_config()
            
            # Create raspberry_pi section if it doesn't exist
            if 'raspberry_pi' not in config:
                config['raspberry_pi'] = {}
            
            # Update Pi configuration
            config['raspberry_pi'].update({
                'auto_detected_ip': device['ip'],
                'last_detection': datetime.now(timezone.utc).isoformat(),
                'mac_address': device.get('mac'),
                'hostname': device.get('hostname'),
                'ssh_available': device.get('ssh_available', False),
                'web_available': device.get('web_available', False),
                'auto_updated': True,
                'detection_method': 'automatic_monitoring'
            })
            
            # Save configuration
            save_config(config)
            
            logger.info(f"💾 Automatically saved Pi config: {device['ip']}")
            logger.info(f"   • MAC: {device.get('mac', 'Unknown')}")
            logger.info(f"   • Hostname: {device.get('hostname', 'Unknown')}")
            logger.info(f"   • Services: SSH={'✅' if device.get('ssh_available') else '❌'}, Web={'✅' if device.get('web_available') else '❌'}")
            
        except Exception as e:
            logger.error(f"Failed to save Pi config automatically: {e}")
    
    def get_current_primary_ip(self) -> Optional[str]:
        """Get the current primary Pi IP address."""
        return self.current_primary_ip
    
    def get_status(self) -> Dict:
        """Get the current status of the auto IP detector."""
        return {
            'running': self.running,
            'current_primary_ip': self.current_primary_ip,
            'known_devices': list(self.known_devices),
            'last_scan_time': self.last_scan_time.isoformat() if self.last_scan_time else None,
            'scan_interval': self.scan_interval
        }
    
    def force_scan(self) -> Dict:
        """Force an immediate scan and return results."""
        logger.info("🔄 Forcing immediate Pi scan...")
        self._scan_and_update()
        return self.get_status()

# Global instance for the auto IP detector
_auto_detector = None

def get_auto_ip_detector() -> AutoIPDetector:
    """Get the global auto IP detector instance."""
    global _auto_detector
    if _auto_detector is None:
        _auto_detector = AutoIPDetector()
    return _auto_detector

def start_auto_ip_detection():
    """Start the automatic IP detection service."""
    detector = get_auto_ip_detector()
    detector.start_monitoring()
    return detector

def stop_auto_ip_detection():
    """Stop the automatic IP detection service."""
    global _auto_detector
    if _auto_detector:
        _auto_detector.stop_monitoring()

def get_auto_detected_ip() -> Optional[str]:
    """Get the automatically detected primary Pi IP."""
    detector = get_auto_ip_detector()
    return detector.get_current_primary_ip()
