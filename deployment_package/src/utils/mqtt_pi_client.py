#!/usr/bin/env python3
"""
MQTT Pi Client - Raspberry Pi Device Announcement System
Automatically announces Pi presence to server regardless of network changes
"""

import json
import time
import threading
import logging
import socket
import subprocess
import netifaces
from datetime import datetime
from typing import Dict, List, Optional
import paho.mqtt.client as mqtt

class MQTTPiClient:
    """MQTT client for Raspberry Pi to announce itself to the server"""
    
    def __init__(self, server_host: str, mqtt_port: int = 1883, device_id: str = None):
        self.server_host = server_host
        self.mqtt_port = mqtt_port
        self.device_id = device_id or self._generate_device_id()
        self.client = None
        self.connected = False
        self.logger = logging.getLogger(__name__)
        
        # MQTT Topics
        self.DEVICE_ANNOUNCE_TOPIC = "devices/announce"
        self.DEVICE_HEARTBEAT_TOPIC = "devices/heartbeat"
        self.DEVICE_STATUS_TOPIC = "devices/status"
        self.SERVER_REQUESTS_TOPIC = "server/requests"
        
        # Device information
        self.device_info = self._get_device_info()
        
        # Heartbeat interval (30 seconds)
        self.heartbeat_interval = 30
        self.heartbeat_thread = None
        self.running = False
    
    def _generate_device_id(self) -> str:
        """Generate unique device ID based on hardware"""
        try:
            # Try to get CPU serial number (Raspberry Pi specific)
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()[-12:]
        except:
            pass
        
        try:
            # Fallback to MAC address
            mac = self._get_primary_mac_address()
            if mac:
                return mac.replace(':', '').lower()
        except:
            pass
        
        # Final fallback to hostname
        return socket.gethostname().lower()
    
    def _get_primary_mac_address(self) -> Optional[str]:
        """Get primary network interface MAC address"""
        try:
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                if interface.startswith(('eth', 'wlan', 'en', 'wl')):
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_LINK in addrs:
                        mac = addrs[netifaces.AF_LINK][0]['addr']
                        if mac != '00:00:00:00:00:00':
                            return mac
        except:
            pass
        return None
    
    def _get_device_info(self) -> dict:
        """Get comprehensive device information"""
        info = {
            'device_id': self.device_id,
            'hostname': socket.gethostname(),
            'device_type': 'raspberry_pi',
            'ip_address': self._get_primary_ip(),
            'mac_address': self._get_primary_mac_address(),
            'services': self._get_available_services(),
            'system_info': self._get_system_info(),
            'timestamp': datetime.now().isoformat()
        }
        return info
    
    def _get_primary_ip(self) -> Optional[str]:
        """Get primary IP address"""
        try:
            # Connect to a remote address to determine the primary interface
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                # Fallback method
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except:
                return None
    
    def _get_available_services(self) -> dict:
        """Check which services are available on this Pi"""
        services = {}
        
        # Check SSH (port 22)
        if self._is_port_open(22):
            services['ssh'] = {'port': 22, 'status': 'available'}
        
        # Check web service (port 5000)
        if self._is_port_open(5000):
            services['web'] = {'port': 5000, 'status': 'available'}
        
        # Check if barcode scanner service is running
        try:
            result = subprocess.run(['systemctl', 'is-active', 'barcode-scanner'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                services['barcode_scanner'] = {'status': 'active'}
        except:
            pass
        
        return services
    
    def _is_port_open(self, port: int) -> bool:
        """Check if a port is open on localhost"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _get_system_info(self) -> dict:
        """Get system information"""
        info = {}
        try:
            # Get uptime
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                info['uptime_hours'] = round(uptime_seconds / 3600, 1)
        except:
            pass
        
        try:
            # Get load average
            with open('/proc/loadavg', 'r') as f:
                load = f.readline().split()[:3]
                info['load_average'] = [float(x) for x in load]
        except:
            pass
        
        try:
            # Get memory info
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    if line.startswith(('MemTotal:', 'MemAvailable:')):
                        key, value = line.split(':')
                        meminfo[key] = int(value.split()[0]) * 1024  # Convert to bytes
                
                if 'MemTotal' in meminfo and 'MemAvailable' in meminfo:
                    info['memory'] = {
                        'total': meminfo['MemTotal'],
                        'available': meminfo['MemAvailable'],
                        'used_percent': round((1 - meminfo['MemAvailable'] / meminfo['MemTotal']) * 100, 1)
                    }
        except:
            pass
        
        return info
    
    def connect(self) -> bool:
        """Connect to MQTT broker on server"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            self.logger.info(f"🔌 Connecting to MQTT broker at {self.server_host}:{self.mqtt_port}")
            self.client.connect(self.server_host, self.mqtt_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if self.connected:
                self.logger.info("✅ Connected to MQTT broker")
                self.running = True
                self._start_heartbeat()
                return True
            else:
                self.logger.error("❌ Failed to connect to MQTT broker")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ MQTT connection error: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            self.connected = True
            self.logger.info("📡 MQTT connected successfully")
            
            # Subscribe to server requests
            client.subscribe(self.SERVER_REQUESTS_TOPIC)
            self.logger.info(f"📥 Subscribed to: {self.SERVER_REQUESTS_TOPIC}")
            
            # Announce device presence
            self._announce_device()
            
        else:
            self.logger.error(f"❌ MQTT connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.connected = False
        self.logger.warning("📡 MQTT disconnected")
        
        # Try to reconnect
        if self.running:
            self.logger.info("🔄 Attempting to reconnect...")
            time.sleep(5)
            try:
                client.reconnect()
            except Exception as e:
                self.logger.error(f"❌ Reconnection failed: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == self.SERVER_REQUESTS_TOPIC:
                self._handle_server_request(payload)
                
        except Exception as e:
            self.logger.error(f"❌ Error processing MQTT message: {e}")
    
    def _handle_server_request(self, payload: dict):
        """Handle server requests"""
        try:
            action = payload.get('action')
            
            if action == 'announce_request':
                self.logger.info("📢 Server requested device announcement")
                self._announce_device()
            elif action == 'status_request':
                self.logger.info("📊 Server requested status update")
                self._send_status_update()
                
        except Exception as e:
            self.logger.error(f"❌ Error handling server request: {e}")
    
    def _announce_device(self):
        """Announce device presence to server"""
        try:
            if not self.connected:
                return
            
            # Update device info with current data
            self.device_info = self._get_device_info()
            
            self.client.publish(self.DEVICE_ANNOUNCE_TOPIC, json.dumps(self.device_info))
            self.logger.info(f"📢 Announced device: {self.device_id} at {self.device_info['ip_address']}")
            
        except Exception as e:
            self.logger.error(f"❌ Error announcing device: {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            if not self.connected:
                return
            
            heartbeat_data = {
                'device_id': self.device_id,
                'ip_address': self._get_primary_ip(),
                'timestamp': datetime.now().isoformat(),
                'status': 'online'
            }
            
            self.client.publish(self.DEVICE_HEARTBEAT_TOPIC, json.dumps(heartbeat_data))
            self.logger.debug(f"💓 Sent heartbeat: {self.device_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error sending heartbeat: {e}")
    
    def _send_status_update(self):
        """Send detailed status update"""
        try:
            if not self.connected:
                return
            
            status_data = {
                'device_id': self.device_id,
                'services': self._get_available_services(),
                'system_info': self._get_system_info(),
                'timestamp': datetime.now().isoformat(),
                'status': 'online'
            }
            
            self.client.publish(self.DEVICE_STATUS_TOPIC, json.dumps(status_data))
            self.logger.info(f"📊 Sent status update: {self.device_id}")
            
        except Exception as e:
            self.logger.error(f"❌ Error sending status update: {e}")
    
    def _start_heartbeat(self):
        """Start heartbeat thread"""
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            return
        
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        self.logger.info(f"💓 Started heartbeat (interval: {self.heartbeat_interval}s)")
    
    def _heartbeat_loop(self):
        """Heartbeat loop"""
        while self.running:
            try:
                if self.connected:
                    self._send_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"❌ Error in heartbeat loop: {e}")
                time.sleep(self.heartbeat_interval)
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            self.running = False
            
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.connected = False
                self.logger.info("📡 Disconnected from MQTT broker")
                
        except Exception as e:
            self.logger.error(f"❌ Error disconnecting from MQTT: {e}")

def start_pi_announcement_service(server_host: str, device_id: str = None):
    """Start the Pi announcement service"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    client = MQTTPiClient(server_host, device_id=device_id)
    
    if client.connect():
        print(f"✅ Pi announcement service started for device: {client.device_id}")
        print(f"📡 Connected to server: {server_host}")
        print("💓 Sending heartbeats every 30 seconds...")
        
        try:
            while True:
                time.sleep(10)
                if not client.connected:
                    print("⚠️ Connection lost, attempting to reconnect...")
        except KeyboardInterrupt:
            print("\n🛑 Shutting down Pi announcement service...")
            client.disconnect()
    else:
        print("❌ Failed to start Pi announcement service")
        return False
    
    return True

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python mqtt_pi_client.py <server_host> [device_id]")
        print("Example: python mqtt_pi_client.py iot.caleffionline.it")
        sys.exit(1)
    
    server_host = sys.argv[1]
    device_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    start_pi_announcement_service(server_host, device_id)
