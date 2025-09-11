"""
MQTT-based device discovery for IoT devices on the network
"""
import paho.mqtt.client as mqtt
import socket
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class DiscoveredDevice:
    """Class representing a discovered device"""
    device_id: str
    ip_address: str
    mac_address: str = ""
    hostname: str = ""
    device_type: str = "unknown"
    last_seen: float = 0.0
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary"""
        return {
            'device_id': self.device_id,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'hostname': self.hostname,
            'device_type': self.device_type,
            'last_seen': datetime.fromtimestamp(self.last_seen, tz=timezone.utc).isoformat(),
            'metadata': self.metadata or {}
        }

class MQTTDiscovery:
    """MQTT-based device discovery service"""
    
    def __init__(
        self,
        broker: str = "localhost",
        port: int = 1883,
        discovery_topic: str = "devices/discover",
        response_topic: str = "devices/response",
        keepalive: int = 60,
        client_id: str = None
    ):
        """
        Initialize MQTT discovery service
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
            discovery_topic: Topic for discovery messages
            response_topic: Topic for device responses
            keepalive: MQTT keepalive in seconds
            client_id: Optional client ID for MQTT client
        """
        self.broker = broker
        self.port = port
        self.discovery_topic = discovery_topic
        self.response_topic = response_topic
        self.keepalive = keepalive
        self.client_id = client_id or f"discovery-{socket.gethostname()}-{int(time.time())}"
        
        self.devices: Dict[str, DiscoveredDevice] = {}
        self.callbacks = []
        self.running = False
        self.client = None
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the MQTT discovery service"""
        if self.running:
            logger.warning("MQTT discovery already running")
            return True
            
        try:
            self.client = mqtt.Client(client_id=self.client_id, clean_session=True)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            
            # Set last will and testament
            self.client.will_set(
                f"devices/status/{self.client_id}",
                payload="offline",
                qos=1,
                retain=True
            )
            
            # Connect to broker
            self.client.connect(self.broker, self.port, self.keepalive)
            
            # Start network loop in a separate thread
            self.client.loop_start()
            self.running = True
            
            # Publish online status
            self.client.publish(
                f"devices/status/{self.client_id}",
                payload="online",
                qos=1,
                retain=True
            )
            
            logger.info(f"MQTT discovery started on {self.broker}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MQTT discovery: {e}")
            self.stop()
            return False
    
    def stop(self):
        """Stop the MQTT discovery service"""
        if not self.running:
            return
            
        try:
            # Publish offline status
            if self.client:
                self.client.publish(
                    f"devices/status/{self.client_id}",
                    payload="offline",
                    qos=1,
                    retain=True
                )
                
                # Disconnect
                self.client.loop_stop()
                self.client.disconnect()
                
        except Exception as e:
            logger.error(f"Error during MQTT disconnect: {e}")
            
        finally:
            self.running = False
            self.client = None
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to response topic
            client.subscribe(self.response_topic + "/#")
            logger.info(f"Subscribed to {self.response_topic}/#")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Skip our own messages
            if topic.startswith("devices/status/") and topic.endswith(self.client_id):
                return
                
            # Handle discovery responses
            if topic.startswith(self.response_topic):
                try:
                    device_info = json.loads(payload)
                    self._handle_device_response(device_info, topic)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {payload}")
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_device_response(self, device_info: Dict, topic: str):
        """Handle a device response to discovery"""
        try:
            device_id = device_info.get('device_id')
            if not device_id:
                logger.warning("Received device response without device_id")
                return
                
            # Get IP from topic if available (last part of topic)
            ip_address = topic.split('/')[-1] if '/' in topic else ""
            
            with self._lock:
                # Update existing device or create new one
                if device_id in self.devices:
                    device = self.devices[device_id]
                    device.last_seen = time.time()
                else:
                    device = DiscoveredDevice(
                        device_id=device_id,
                        ip_address=ip_address,
                        last_seen=time.time()
                    )
                    self.devices[device_id] = device
                
                # Update device info
                device.mac_address = device_info.get('mac_address', device.mac_address)
                device.hostname = device_info.get('hostname', device.hostname)
                device.device_type = device_info.get('device_type', device.device_type)
                device.metadata = device_info.get('metadata', {})
                
                # If IP wasn't in topic, try to get it from metadata
                if not device.ip_address and 'ip_address' in device.metadata:
                    device.ip_address = device.metadata['ip_address']
                
                logger.info(f"Discovered device: {device_id} ({device.ip_address})")
                
                # Notify callbacks
                self._notify_callbacks(device)
                
        except Exception as e:
            logger.error(f"Error handling device response: {e}")
    
    def discover_devices(self, timeout: float = 5.0) -> List[DiscoveredDevice]:
        """
        Discover devices on the network
        
        Args:
            timeout: Time to wait for responses in seconds
            
        Returns:
            List of discovered devices
        """
        if not self.running:
            if not self.start():
                return []
        
        try:
            # Clear previous devices
            with self._lock:
                self.devices.clear()
            
            # Publish discovery message
            discovery_msg = {
                'discovery': True,
                'timestamp': time.time(),
                'requester': self.client_id
            }
            
            self.client.publish(
                self.discovery_topic,
                payload=json.dumps(discovery_msg),
                qos=1
            )
            
            # Wait for responses
            time.sleep(timeout)
            
            # Return discovered devices
            with self._lock:
                return list(self.devices.values())
                
        except Exception as e:
            logger.error(f"Error during device discovery: {e}")
            return []
    
    def add_callback(self, callback: Callable[[DiscoveredDevice], None]):
        """
        Add a callback to be called when a new device is discovered
        
        Args:
            callback: Function that takes a DiscoveredDevice as argument
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[DiscoveredDevice], None]):
        """Remove a callback"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _notify_callbacks(self, device: DiscoveredDevice):
        """Notify all registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(device)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")

# Singleton instance
_discovery_instance = None

def get_mqtt_discovery(
    broker: str = "localhost",
    port: int = 1883,
    discovery_topic: str = "devices/discover",
    response_topic: str = "devices/response",
    keepalive: int = 60,
    client_id: str = None
) -> MQTTDiscovery:
    """
    Get or create the singleton MQTT discovery instance
    
    Args:
        broker: MQTT broker address
        port: MQTT broker port
        discovery_topic: Topic for discovery messages
        response_topic: Topic for device responses
        keepalive: MQTT keepalive in seconds
        client_id: Optional client ID for MQTT client
        
    Returns:
        MQTTDiscovery: The singleton discovery instance
    """
    global _discovery_instance
    
    if _discovery_instance is None:
        _discovery_instance = MQTTDiscovery(
            broker=broker,
            port=port,
            discovery_topic=discovery_topic,
            response_topic=response_topic,
            keepalive=keepalive,
            client_id=client_id
        )
    
    return _discovery_instance

def discover_raspberry_pi_devices(
    broker: str = "localhost",
    port: int = 1883,
    timeout: float = 5.0
) -> List[Dict]:
    """
    Convenience function to discover Raspberry Pi devices using MQTT
    
    Args:
        broker: MQTT broker address
        port: MQTT broker port
        timeout: Time to wait for responses in seconds
        
    Returns:
        List of discovered Raspberry Pi devices as dictionaries
    """
    try:
        discovery = get_mqtt_discovery(broker=broker, port=port)
        devices = discovery.discover_devices(timeout=timeout)
        
        # Filter for Raspberry Pi devices
        pi_devices = []
        for device in devices:
            if device.device_type.lower() in ['raspberry_pi', 'rpi'] or \
               'raspberry' in device.hostname.lower() or \
               (device.metadata and device.metadata.get('os', '').lower() == 'raspbian'):
                pi_devices.append(device.to_dict())
        
        return pi_devices
        
    except Exception as e:
        logger.error(f"Error discovering Raspberry Pi devices: {e}")
        return []

def get_primary_raspberry_pi_ip(
    broker: str = "localhost",
    port: int = 1883,
    timeout: float = 5.0
) -> Optional[str]:
    """
    Get the IP address of the primary Raspberry Pi on the network
    
    Args:
        broker: MQTT broker address
        port: MQTT broker port
        timeout: Time to wait for responses in seconds
        
    Returns:
        str: IP address of the primary Pi, or None if not found
    """
    try:
        # First check if this is a Pi
        import platform
        if 'arm' in platform.machine().lower() or 'raspberry' in platform.platform().lower():
            # This is a Pi, return its IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Doesn't need to be reachable
                s.connect(('10.255.255.255', 1))
                ip = s.getsockname()[0]
            except Exception:
                ip = '127.0.0.1'
            finally:
                s.close()
            return ip
            
        # Otherwise, try to discover Pis on the network
        pi_devices = discover_raspberry_pi_devices(broker, port, timeout)
        if pi_devices:
            # Return the first Pi found
            return pi_devices[0].get('ip_address')
            
    except Exception as e:
        logger.error(f"Error getting primary Raspberry Pi IP: {e}")
    
    return None
