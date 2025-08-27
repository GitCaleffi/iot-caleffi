#!/usr/bin/env python3
"""
MQTT-based Device Discovery System
Enables automatic Raspberry Pi detection regardless of network changes
"""

import json
import time
import threading
import logging
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import paho.mqtt.client as mqtt

class MQTTDeviceDiscovery:
    """Discovers and monitors MQTT devices on the network"""
    
    def __init__(self, mqtt_broker_host: str = "localhost", mqtt_broker_port: int = 1883):
        self.mqtt_broker_host = mqtt_broker_host
        self.mqtt_broker_port = mqtt_broker_port
        self.client = None
        self.connected = False
        self.discovered_devices = {}  
        self.device_callbacks = []  # List of callback functions
        self.logger = logging.getLogger(__name__)
        self.stats = {
            'devices_discovered': 0,
            'messages_received': 0,
            'last_discovery': None,
            'connection_attempts': 0,
            'connection_errors': 0
        }
        
        # MQTT Topics
        self.DEVICE_ANNOUNCE_TOPIC = "devices/announce"
        self.DEVICE_HEARTBEAT_TOPIC = "devices/heartbeat"
        self.DEVICE_STATUS_TOPIC = "devices/status"
        self.SERVER_DISCOVERY_TOPIC = "server/discovery"
        
        # Device timeout (if no heartbeat for 5 minutes, consider offline)
        self.DEVICE_TIMEOUT = 300  # seconds
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_offline_devices, daemon=True)
        self.cleanup_thread.start()
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            self.logger.info(f"🔌 Connecting to MQTT broker at {self.mqtt_broker_host}:{self.mqtt_broker_port}")
            self.client.connect(self.mqtt_broker_host, self.mqtt_broker_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if self.connected:
                self.logger.info("✅ Connected to MQTT broker")
                return True
            else:
                self.logger.error("❌ Failed to connect to MQTT broker")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ MQTT connection error: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        connection_status = {
            0: "Connection successful",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }.get(rc, f"Unknown error: {rc}")
        
        self.stats['connection_attempts'] += 1
        
        if rc == 0:
            self.connected = True
            self.connection_time = time.time()
            
            self.logger.info("🔍 MQTT Device Discovery")
            self.logger.info(f"   - Broker: {self.mqtt_broker_host}:{self.mqtt_broker_port}")
            self.logger.info(f"   - Client ID: {client._client_id.decode()}")
            self.logger.info(f"   - Session Present: {flags.get('session present', False)}")
            
            # Subscribe to device topics
            topics = [
                self.DEVICE_ANNOUNCE_TOPIC,
                self.DEVICE_HEARTBEAT_TOPIC,
                self.DEVICE_STATUS_TOPIC
            ]
            
            for topic in topics:
                result, mid = client.subscribe(topic, qos=1)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self.logger.debug(f"✅ Subscribed to: {topic}")
                else:
                    self.logger.error(f"❌ Failed to subscribe to {topic}: {mqtt.error_string(result)}")
        else:
            self.connected = False
            self.stats['connection_errors'] += 1
            self.logger.error(f"❌ MQTT Connection Failed")
            self.logger.error(f"   - Error: {connection_status}")
            self.logger.error(f"   - Broker: {self.mqtt_broker_host}:{self.mqtt_broker_port}")
            self.logger.error(f"   - Client ID: {client._client_id.decode() if hasattr(client, '_client_id') else 'Unknown'}")
            
            # Schedule reconnection attempt
            if self.running:
                retry_delay = 5
                self.logger.info(f"🔄 Will retry connection in {retry_delay} seconds...")
                time.sleep(retry_delay)
                self.connect()
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        self.connected = False
        self.logger.warning("📡 MQTT disconnected")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            self.stats['messages_received'] += 1
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic == self.DEVICE_ANNOUNCE_TOPIC:
                self._handle_device_announce(payload)
            elif topic == self.DEVICE_HEARTBEAT_TOPIC:
                self._handle_device_heartbeat(payload)
            elif topic == self.DEVICE_STATUS_TOPIC:
                self._handle_device_status(payload)
                
        except Exception as e:
            self.logger.error(f"❌ Error processing MQTT message: {e}")
    
    def _handle_device_announce(self, payload: dict):
        """Handle device announcement"""
        try:
            device_id = payload.get('device_id')
            if not device_id:
                return
            
            device_info = {
                'device_id': device_id,
                'ip_address': payload.get('ip_address'),
                'hostname': payload.get('hostname'),
                'mac_address': payload.get('mac_address'),
                'device_type': payload.get('device_type', 'raspberry_pi'),
                'services': payload.get('services', {}),
                'last_seen': datetime.now(),
                'status': 'online',
                'first_seen': datetime.now() if device_id not in self.discovered_devices else self.discovered_devices[device_id].get('first_seen', datetime.now())
            }
            
            is_new_device = device_id not in self.discovered_devices
            self.discovered_devices[device_id] = device_info
            
            if is_new_device:
                self.logger.info(f"🆕 New device discovered: {device_id} at {device_info['ip_address']}")
                self.stats['devices_discovered'] += 1
                self.stats['last_discovery'] = time.time()
            else:
                self.logger.info(f"📍 Device reconnected: {device_id} at {device_info['ip_address']}")
            
            # Notify callbacks
            for callback in self.device_callbacks:
                try:
                    callback('device_discovered', device_info)
                except Exception as e:
                    self.logger.error(f"❌ Error in device callback: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error handling device announce: {e}")
    
    def _handle_device_heartbeat(self, payload: dict):
        """Handle device heartbeat"""
        try:
            device_id = payload.get('device_id')
            if device_id in self.discovered_devices:
                self.discovered_devices[device_id]['last_seen'] = datetime.now()
                self.discovered_devices[device_id]['status'] = 'online'
                
                # Update IP if changed
                new_ip = payload.get('ip_address')
                if new_ip and new_ip != self.discovered_devices[device_id]['ip_address']:
                    old_ip = self.discovered_devices[device_id]['ip_address']
                    self.discovered_devices[device_id]['ip_address'] = new_ip
                    self.logger.info(f"📍 Device {device_id} IP changed: {old_ip} → {new_ip}")
                    
                    # Notify callbacks of IP change
                    for callback in self.device_callbacks:
                        try:
                            callback('device_ip_changed', self.discovered_devices[device_id])
                        except Exception as e:
                            self.logger.error(f"❌ Error in device callback: {e}")
                            
        except Exception as e:
            self.logger.error(f"❌ Error handling device heartbeat: {e}")
    
    def _handle_device_status(self, payload: dict):
        """Handle device status updates"""
        try:
            device_id = payload.get('device_id')
            if device_id in self.discovered_devices:
                self.discovered_devices[device_id]['last_seen'] = datetime.now()
                
                # Update status information
                if 'status' in payload:
                    self.discovered_devices[device_id]['status'] = payload['status']
                if 'services' in payload:
                    self.discovered_devices[device_id]['services'] = payload['services']
                    
        except Exception as e:
            self.logger.error(f"❌ Error handling device status: {e}")
    
    def _publish_server_discovery(self):
        """Publish server discovery message to announce server presence"""
        try:
            if not self.connected:
                return
                
            server_info = {
                'server_id': socket.gethostname(),
                'timestamp': datetime.now().isoformat(),
                'services': {
                    'mqtt': {'port': self.mqtt_broker_port},
                    'web': {'port': 80},
                    'api': {'port': 5000}
                }
            }
            
            self.client.publish(self.SERVER_DISCOVERY_TOPIC, json.dumps(server_info))
            self.logger.info("📢 Published server discovery message")
            
        except Exception as e:
            self.logger.error(f"❌ Error publishing server discovery: {e}")
    
    def _cleanup_offline_devices(self):
        """Background thread to clean up offline devices"""
        while True:
            try:
                current_time = datetime.now()
                offline_devices = []
                
                for device_id, device_info in self.discovered_devices.items():
                    last_seen = device_info.get('last_seen', current_time)
                    if (current_time - last_seen).total_seconds() > self.DEVICE_TIMEOUT:
                        if device_info.get('status') != 'offline':
                            device_info['status'] = 'offline'
                            offline_devices.append(device_id)
                            self.logger.warning(f"⚠️ Device {device_id} marked as offline (no heartbeat for {self.DEVICE_TIMEOUT}s)")
                            
                            # Notify callbacks
                            for callback in self.device_callbacks:
                                try:
                                    callback('device_offline', device_info)
                                except Exception as e:
                                    self.logger.error(f"❌ Error in device callback: {e}")
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"❌ Error in cleanup thread: {e}")
                time.sleep(60)
    
    def get_discovered_devices(self) -> Dict[str, dict]:
        """Get all discovered devices"""
        return self.discovered_devices.copy()
    
    def get_online_devices(self) -> Dict[str, dict]:
        """Get only online devices"""
        return {
            device_id: device_info 
            for device_id, device_info in self.discovered_devices.items()
            if device_info.get('status') == 'online'
        }
    
    def get_device_by_id(self, device_id: str) -> Optional[dict]:
        """Get specific device by ID"""
        return self.discovered_devices.get(device_id)
    
    def get_primary_raspberry_pi(self) -> Optional[dict]:
        """Get the primary (most recently seen) Raspberry Pi"""
        online_pis = [
            device for device in self.discovered_devices.values()
            if device.get('status') == 'online' and device.get('device_type') == 'raspberry_pi'
        ]
        
        if not online_pis:
            return None
            
        # Return most recently seen
        return max(online_pis, key=lambda d: d.get('last_seen', datetime.min))
    
    def add_device_callback(self, callback: Callable[[str, dict], None]):
        """Add callback for device events"""
        self.device_callbacks.append(callback)
    
    def remove_device_callback(self, callback: Callable[[str, dict], None]):
        """Remove device callback"""
        if callback in self.device_callbacks:
            self.device_callbacks.remove(callback)
    
    def request_device_announcement(self):
        """Request all devices to announce themselves"""
        try:
            if self.connected:
                request_msg = {
                    'action': 'announce_request',
                    'timestamp': datetime.now().isoformat()
                }
                self.client.publish("server/requests", json.dumps(request_msg))
                self.logger.info("📢 Requested device announcements")
        except Exception as e:
            self.logger.error(f"❌ Error requesting device announcements: {e}")
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        try:
            if self.client:
                self.client.loop_stop()
                self.client.disconnect()
                self.connected = False
                self.logger.info("📡 Disconnected from MQTT broker")
        except Exception as e:
            self.logger.error(f"❌ Error disconnecting from MQTT: {e}")

# Global instance for easy access
mqtt_discovery = None

def get_mqtt_discovery(mqtt_broker_host: str = "localhost") -> MQTTDeviceDiscovery:
    """Get global MQTT discovery instance"""
    global mqtt_discovery
    if mqtt_discovery is None:
        mqtt_discovery = MQTTDeviceDiscovery(mqtt_broker_host)
        if not mqtt_discovery.connect():
            raise Exception("Failed to connect to MQTT broker")
    return mqtt_discovery

def discover_raspberry_pi_devices() -> List[dict]:
    """Discover Raspberry Pi devices using MQTT"""
    try:
        discovery = get_mqtt_discovery()
        online_devices = discovery.get_online_devices()
        
        # Filter for Raspberry Pi devices
        pi_devices = [
            device for device in online_devices.values()
            if device.get('device_type') == 'raspberry_pi'
        ]
        
        return pi_devices
        
    except Exception as e:
        logging.error(f"❌ Error discovering Pi devices via MQTT: {e}")
        return []

def get_primary_raspberry_pi_ip() -> Optional[str]:
    """Get primary Raspberry Pi IP address via MQTT"""
    try:
        discovery = get_mqtt_discovery()
        primary_pi = discovery.get_primary_raspberry_pi()
        
        if primary_pi:
            return primary_pi.get('ip_address')
        return None
        
    except Exception as e:
        logging.error(f"❌ Error getting primary Pi IP via MQTT: {e}")
        return None

if __name__ == "__main__":
    # Test the MQTT discovery system
    logging.basicConfig(level=logging.INFO)
    
    def device_event_handler(event_type: str, device_info: dict):
        print(f"🔔 Device Event: {event_type}")
        print(f"   Device: {device_info.get('device_id')} at {device_info.get('ip_address')}")
    
    discovery = MQTTDeviceDiscovery()
    discovery.add_device_callback(device_event_handler)
    
    if discovery.connect():
        print("✅ MQTT Discovery Server started")
        print("📡 Listening for device announcements...")
        
        try:
            while True:
                time.sleep(10)
                devices = discovery.get_online_devices()
                print(f"📊 Online devices: {len(devices)}")
                for device_id, device_info in devices.items():
                    print(f"   - {device_id}: {device_info.get('ip_address')}")
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            discovery.disconnect()
    else:
        print("❌ Failed to start MQTT discovery")
