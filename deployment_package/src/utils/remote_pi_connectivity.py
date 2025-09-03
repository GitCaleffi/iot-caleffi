#!/usr/bin/env python3
"""
Remote Pi Connectivity Detection
Detects Pi device connectivity from live server across different networks using multiple methods.
"""

import subprocess
import threading
import time
import json
import requests
import logging
import socket
from datetime import datetime
from typing import List, Dict, Optional, Set
import asyncio
import concurrent.futures

logger = logging.getLogger(__name__)

class RemotePiConnectivity:
    """Detect Pi connectivity across different networks from live server"""
    
    def __init__(self, config: dict):
        self.config = config
        self.raspberry_pi_config = config.get("raspberry_pi", {})
        self.check_interval = 30  # Check every 30 seconds
        self.is_monitoring = False
        self.monitor_thread = None
        
        # Pi connection methods
        self.pi_devices = self._load_known_pi_devices()
        self.last_connectivity_status = {}
        
    def _load_known_pi_devices(self) -> List[Dict]:
        """Load known Pi devices from config"""
        devices = []
        
        # From manual configuration
        manual_ip = self.raspberry_pi_config.get("manual_ip")
        if manual_ip:
            devices.append({
                'ip': manual_ip,
                'type': 'manual',
                'ports': [22, 5000, 80]  # SSH, web service, HTTP
            })
            
        # From auto-detected devices
        auto_ip = self.raspberry_pi_config.get("auto_detected_ip")
        if auto_ip and auto_ip != manual_ip:
            devices.append({
                'ip': auto_ip,
                'type': 'auto_detected',
                'ports': [22, 5000, 80]
            })
            
        # From device registry (if available)
        device_registry = self.raspberry_pi_config.get("device_registry", [])
        for device in device_registry:
            if device.get('ip') not in [d['ip'] for d in devices]:
                devices.append({
                    'ip': device['ip'],
                    'type': 'registered',
                    'ports': device.get('ports', [22, 5000, 80])
                })
                
        return devices
        
    def start_monitoring(self):
        """Start continuous Pi connectivity monitoring"""
        if self.is_monitoring:
            logger.warning("Pi connectivity monitoring already running")
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("🔍 Remote Pi connectivity monitoring started")
        
    def stop_monitoring(self):
        """Stop Pi connectivity monitoring"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("🛑 Remote Pi connectivity monitoring stopped")
        
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                self._check_all_pi_devices()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(10)
                
    def _check_all_pi_devices(self):
        """Check connectivity to all known Pi devices"""
        current_status = {}
        
        for device in self.pi_devices:
            device_ip = device['ip']
            connectivity = self._check_pi_connectivity(device)
            current_status[device_ip] = connectivity
            
            # Detect status changes
            previous_status = self.last_connectivity_status.get(device_ip, {})
            if connectivity['connected'] != previous_status.get('connected', False):
                self._handle_connectivity_change(device_ip, connectivity, previous_status)
                
        self.last_connectivity_status = current_status
        
    def _check_pi_connectivity(self, device: Dict) -> Dict:
        """Check connectivity to a specific Pi device using multiple methods"""
        device_ip = device['ip']
        ports = device['ports']
        
        connectivity = {
            'ip': device_ip,
            'connected': False,
            'methods': {},
            'timestamp': datetime.now().isoformat(),
            'response_time': None
        }
        
        start_time = time.time()
        
        # Method 1: TCP port connectivity test
        tcp_results = self._test_tcp_ports(device_ip, ports)
        connectivity['methods']['tcp'] = tcp_results
        
        # Method 2: ICMP ping test
        ping_result = self._test_ping(device_ip)
        connectivity['methods']['ping'] = ping_result
        
        # Method 3: HTTP/HTTPS service test
        http_result = self._test_http_services(device_ip)
        connectivity['methods']['http'] = http_result
        
        # Method 4: SSH connectivity test
        ssh_result = self._test_ssh_connectivity(device_ip)
        connectivity['methods']['ssh'] = ssh_result
        
        # Determine overall connectivity
        connectivity['connected'] = any([
            tcp_results['any_port_open'],
            ping_result['reachable'],
            http_result['accessible'],
            ssh_result['accessible']
        ])
        
        connectivity['response_time'] = round(time.time() - start_time, 2)
        
        return connectivity
        
    def _test_tcp_ports(self, ip: str, ports: List[int]) -> Dict:
        """Test TCP port connectivity"""
        results = {'ports': {}, 'any_port_open': False}
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((ip, port))
                sock.close()
                
                port_open = result == 0
                results['ports'][port] = port_open
                if port_open:
                    results['any_port_open'] = True
                    
            except Exception as e:
                results['ports'][port] = False
                logger.debug(f"TCP test error for {ip}:{port} - {e}")
                
        return results
        
    def _test_ping(self, ip: str) -> Dict:
        """Test ICMP ping connectivity"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", ip],
                capture_output=True,
                timeout=5
            )
            
            return {
                'reachable': result.returncode == 0,
                'output': result.stdout.decode() if result.stdout else None
            }
            
        except Exception as e:
            logger.debug(f"Ping test error for {ip} - {e}")
            return {'reachable': False, 'error': str(e)}
            
    def _test_http_services(self, ip: str) -> Dict:
        """Test HTTP/HTTPS service accessibility"""
        results = {'accessible': False, 'services': {}}
        
        # Test common Pi web service ports
        test_urls = [
            f"http://{ip}:5000",
            f"http://{ip}:80",
            f"https://{ip}:443",
            f"http://{ip}:8080"
        ]
        
        for url in test_urls:
            try:
                response = requests.get(url, timeout=3, verify=False)
                service_accessible = response.status_code < 500
                results['services'][url] = {
                    'accessible': service_accessible,
                    'status_code': response.status_code
                }
                if service_accessible:
                    results['accessible'] = True
                    
            except Exception as e:
                results['services'][url] = {
                    'accessible': False,
                    'error': str(e)
                }
                
        return results
        
    def _test_ssh_connectivity(self, ip: str) -> Dict:
        """Test SSH service accessibility"""
        try:
            # Test SSH port without authentication
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, 22))
            sock.close()
            
            ssh_accessible = result == 0
            
            return {
                'accessible': ssh_accessible,
                'port': 22
            }
            
        except Exception as e:
            logger.debug(f"SSH test error for {ip} - {e}")
            return {'accessible': False, 'error': str(e)}
            
    def _handle_connectivity_change(self, device_ip: str, current: Dict, previous: Dict):
        """Handle Pi connectivity status changes"""
        if current['connected'] and not previous.get('connected', False):
            logger.info(f"🟢 Pi device CONNECTED: {device_ip}")
            self._notify_pi_connected(device_ip, current)
            
        elif not current['connected'] and previous.get('connected', False):
            logger.info(f"🔴 Pi device DISCONNECTED: {device_ip}")
            self._notify_pi_disconnected(device_ip, current)
            
    def _notify_pi_connected(self, device_ip: str, connectivity: Dict):
        """Handle Pi device connection"""
        try:
            # Update config
            self._update_config_pi_status(device_ip, "connected", connectivity)
            
            # Send webhook notification
            self._send_connectivity_webhook(device_ip, "connected", connectivity)
            
            # Refresh barcode scanner
            self._refresh_barcode_scanner()
            
        except Exception as e:
            logger.error(f"Error handling Pi connection: {e}")
            
    def _notify_pi_disconnected(self, device_ip: str, connectivity: Dict):
        """Handle Pi device disconnection"""
        try:
            # Update config
            self._update_config_pi_status(device_ip, "disconnected", connectivity)
            
            # Send webhook notification
            self._send_connectivity_webhook(device_ip, "disconnected", connectivity)
            
            # Refresh barcode scanner
            self._refresh_barcode_scanner()
            
        except Exception as e:
            logger.error(f"Error handling Pi disconnection: {e}")
            
    def _update_config_pi_status(self, device_ip: str, status: str, connectivity: Dict):
        """Update configuration with Pi connectivity status"""
        try:
            from utils.config import load_config, save_config
            
            config = load_config()
            pi_config = config.get("raspberry_pi", {})
            
            if status == "connected":
                pi_config["auto_detected_ip"] = device_ip
                pi_config["last_detection"] = connectivity['timestamp']
                pi_config["status"] = "connected"
                pi_config["connectivity_methods"] = connectivity['methods']
            else:
                if pi_config.get("auto_detected_ip") == device_ip:
                    pi_config["status"] = "disconnected"
                    pi_config["last_disconnect"] = connectivity['timestamp']
                    
            config["raspberry_pi"] = pi_config
            save_config(config)
            
            logger.info(f"✅ Config updated: Pi {status} at {device_ip}")
            
        except Exception as e:
            logger.error(f"Error updating config: {e}")
            
    def _send_connectivity_webhook(self, device_ip: str, status: str, connectivity: Dict):
        """Send webhook notification about connectivity change"""
        try:
            webhook_url = self.raspberry_pi_config.get("notification_webhook")
            if not webhook_url:
                return
                
            payload = {
                'device_ip': device_ip,
                'status': status,
                'timestamp': connectivity['timestamp'],
                'device_type': 'raspberry_pi',
                'connectivity_details': connectivity,
                'detection_method': 'remote_monitoring'
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            
            if response.status_code == 200:
                logger.info(f"✅ Connectivity webhook sent: {device_ip} {status}")
            else:
                logger.warning(f"⚠️ Webhook failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending connectivity webhook: {e}")
            
    def _refresh_barcode_scanner(self):
        """Trigger barcode scanner refresh"""
        try:
            from barcode_scanner_app import refresh_pi_connection
            refresh_pi_connection()
            logger.info("🔄 Barcode scanner refreshed")
        except Exception as e:
            logger.error(f"Error refreshing barcode scanner: {e}")
            
    def get_current_connectivity_status(self) -> Dict:
        """Get current connectivity status for all Pi devices"""
        return {
            'devices': self.last_connectivity_status,
            'monitoring': self.is_monitoring,
            'timestamp': datetime.now().isoformat()
        }
        
    def force_connectivity_check(self) -> Dict:
        """Force immediate connectivity check for all devices"""
        logger.info("🔍 Forcing immediate Pi connectivity check...")
        self._check_all_pi_devices()
        return self.get_current_connectivity_status()
