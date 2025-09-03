#!/usr/bin/env python3
"""
Dynamic Raspberry Pi Discovery System
Automatically detects when Pi devices connect/disconnect from any network and notifies the server.
"""

import subprocess
import threading
import time
import json
import requests
import logging
from datetime import datetime
from typing import List, Dict, Optional, Set
import ipaddress
import socket

logger = logging.getLogger(__name__)

class DynamicPiDiscovery:
    """Dynamic discovery system that detects Pi devices across multiple networks"""
    
    def __init__(self, config: dict):
        self.config = config
        self.raspberry_pi_config = config.get("raspberry_pi", {})
        self.discovery_interval = self.raspberry_pi_config.get("discovery_interval", 30)
        self.network_ranges = self.raspberry_pi_config.get("network_scan_range", ["192.168.1.0/24"])
        self.notification_webhook = self.raspberry_pi_config.get("notification_webhook")
        
        # Track discovered devices
        self.discovered_devices: Set[str] = set()
        self.last_scan_results: List[Dict] = []
        self.is_running = False
        self.discovery_thread = None
        
        # Pi MAC prefixes for identification
        self.pi_mac_prefixes = [
            "b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1", 
            "d8:3a:dd", "2c:cf:67", "b8:27:eb", "dc:a6:32"
        ]
        
    def start_discovery(self):
        """Start the dynamic discovery background thread"""
        if self.is_running:
            logger.warning("Discovery already running")
            return
            
        self.is_running = True
        self.discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.discovery_thread.start()
        logger.info(f"🔍 Dynamic Pi discovery started (scanning every {self.discovery_interval}s)")
        
    def stop_discovery(self):
        """Stop the dynamic discovery"""
        self.is_running = False
        if self.discovery_thread:
            self.discovery_thread.join(timeout=5)
        logger.info("🛑 Dynamic Pi discovery stopped")
        
    def _discovery_loop(self):
        """Main discovery loop that runs in background"""
        while self.is_running:
            try:
                self._scan_for_pi_devices()
                time.sleep(self.discovery_interval)
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                time.sleep(10)  # Wait before retrying
                
    def _scan_for_pi_devices(self):
        """Scan all configured network ranges for Pi devices"""
        current_devices = set()
        
        for network_range in self.network_ranges:
            try:
                devices = self._scan_network_range(network_range)
                for device in devices:
                    current_devices.add(device['ip'])
                    
            except Exception as e:
                logger.error(f"Error scanning network {network_range}: {e}")
                
        # Detect new connections
        new_devices = current_devices - self.discovered_devices
        if new_devices:
            for device_ip in new_devices:
                self._handle_new_device(device_ip)
                
        # Detect disconnections
        disconnected_devices = self.discovered_devices - current_devices
        if disconnected_devices:
            for device_ip in disconnected_devices:
                self._handle_device_disconnect(device_ip)
                
        # Update tracked devices
        self.discovered_devices = current_devices
        
    def _scan_network_range(self, network_range: str) -> List[Dict]:
        """Scan a specific network range for Pi devices using fast methods"""
        devices = []
        
        try:
            # First try ARP table scan (fastest)
            devices = self._arp_scan_network(network_range)
            
            if not devices:
                # Fallback to lightweight ping scan
                devices = self._ping_scan_network(network_range)
            
        except Exception as e:
            logger.error(f"Error scanning {network_range}: {e}")
            
        return devices
        
    def _arp_scan_network(self, network_range: str) -> List[Dict]:
        """Fast ARP table-based scanning"""
        devices = []
        
        try:
            # Get ARP table
            result = subprocess.run(
                ["ip", "neighbor", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 5:
                            ip = parts[0]
                            mac = parts[4]
                            
                            # Check if IP is in our target network range
                            if self._ip_in_range(ip, network_range):
                                if self._is_raspberry_pi_mac(mac):
                                    device_info = self._get_device_details(ip, mac)
                                    if device_info:
                                        devices.append(device_info)
                                        logger.info(f"🔍 ARP scan found Pi: {ip} ({mac})")
                                        
        except Exception as e:
            logger.error(f"Error in ARP scan: {e}")
            
        return devices
        
    def _ping_scan_network(self, network_range: str) -> List[Dict]:
        """Fallback ping-based network scanning"""
        devices = []
        
        try:
            network = ipaddress.IPv4Network(network_range, strict=False)
            
            # Scan first 50 IPs to avoid long delays
            for ip in list(network.hosts())[:50]:
                if self._ping_host(str(ip)):
                    # Try to get MAC address via ARP
                    mac = self._get_mac_address(str(ip))
                    if mac and self._is_raspberry_pi_mac(mac):
                        device_info = self._get_device_details(str(ip), mac)
                        if device_info:
                            devices.append(device_info)
                            
        except Exception as e:
            logger.error(f"Error in ping scan: {e}")
            
        return devices
        
    def _ping_host(self, ip: str) -> bool:
        """Check if host responds to ping"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip],
                capture_output=True,
                timeout=3
            )
            return result.returncode == 0
        except:
            return False
            
    def _get_mac_address(self, ip: str) -> Optional[str]:
        """Get MAC address for IP via ARP table"""
        try:
            result = subprocess.run(
                ["arp", "-n", ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if ip in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            return parts[2]  # MAC address column
        except:
            pass
        return None
        
    def _is_raspberry_pi_mac(self, mac: str) -> bool:
        """Check if MAC address belongs to Raspberry Pi"""
        mac_prefix = mac.lower()[:8]
        return any(prefix in mac_prefix for prefix in self.pi_mac_prefixes)
        
    def _get_device_details(self, ip: str, mac: str) -> Optional[Dict]:
        """Get detailed information about discovered Pi device"""
        device_info = {
            'ip': ip,
            'mac': mac,
            'discovered_at': datetime.now().isoformat(),
            'services': []
        }
        
        # Test common Pi services
        if self._test_port(ip, 22):  # SSH
            device_info['services'].append('ssh')
        if self._test_port(ip, 5000):  # Common Pi web service
            device_info['services'].append('web')
        if self._test_port(ip, 80):  # HTTP
            device_info['services'].append('http')
            
        # Only return if at least one service is available
        return device_info if device_info['services'] else None
        
    def _test_port(self, ip: str, port: int, timeout: float = 2.0) -> bool:
        """Test if a port is open on the target IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
            
    def _handle_new_device(self, device_ip: str):
        """Handle when a new Pi device is discovered"""
        logger.info(f"🟢 NEW Pi device detected: {device_ip}")
        
        # Update config with discovered device
        self._update_config_with_device(device_ip)
        
        # Send notification webhook
        if self.notification_webhook:
            self._send_device_notification(device_ip, "connected")
            
        # Trigger immediate barcode scanner refresh
        self._notify_barcode_scanner(device_ip, "connected")
        
    def _handle_device_disconnect(self, device_ip: str):
        """Handle when a Pi device disconnects"""
        logger.info(f"🔴 Pi device disconnected: {device_ip}")
        
        # Send notification webhook
        if self.notification_webhook:
            self._send_device_notification(device_ip, "disconnected")
            
        # Trigger barcode scanner refresh
        self._notify_barcode_scanner(device_ip, "disconnected")
        
    def _update_config_with_device(self, device_ip: str):
        """Update configuration file with discovered device"""
        try:
            from utils.config import load_config, save_config
            
            config = load_config()
            pi_config = config.get("raspberry_pi", {})
            
            pi_config["auto_detected_ip"] = device_ip
            pi_config["last_detection"] = datetime.now().isoformat()
            pi_config["status"] = "connected"
            
            config["raspberry_pi"] = pi_config
            save_config(config)
            
            logger.info(f"✅ Config updated with Pi device: {device_ip}")
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            
    def _send_device_notification(self, device_ip: str, status: str):
        """Send webhook notification about device status change"""
        try:
            payload = {
                'device_ip': device_ip,
                'status': status,
                'timestamp': datetime.now().isoformat(),
                'device_type': 'raspberry_pi'
            }
            
            response = requests.post(
                self.notification_webhook,
                json=payload,
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Device notification sent: {device_ip} {status}")
            else:
                logger.warning(f"⚠️ Notification failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            
    def _notify_barcode_scanner(self, device_ip: str, status: str):
        """Notify the barcode scanner system about device changes"""
        try:
            # Import here to avoid circular imports
            from barcode_scanner_app import refresh_pi_connection
            
            # Trigger immediate refresh
            refresh_pi_connection()
            logger.info(f"🔄 Barcode scanner notified of Pi {status}: {device_ip}")
            
        except Exception as e:
            logger.error(f"Error notifying barcode scanner: {e}")
            
    def get_current_devices(self) -> List[Dict]:
        """Get list of currently discovered Pi devices"""
        devices = []
        for ip in self.discovered_devices:
            # Get device details from last scan
            device_info = next(
                (d for d in self.last_scan_results if d['ip'] == ip),
                {'ip': ip, 'status': 'connected'}
            )
            devices.append(device_info)
        return devices
        
    def force_scan(self) -> List[Dict]:
        """Force an immediate scan and return results"""
        logger.info("🔍 Forcing immediate Pi device scan...")
        self._scan_for_pi_devices()
        return self.get_current_devices()
        
    def _ip_in_range(self, ip: str, network_range: str) -> bool:
        """Check if IP address is in the specified network range"""
        try:
            network = ipaddress.IPv4Network(network_range, strict=False)
            ip_addr = ipaddress.IPv4Address(ip)
            return ip_addr in network
        except:
            return False
