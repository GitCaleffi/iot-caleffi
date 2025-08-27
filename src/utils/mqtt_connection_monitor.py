"""
MQTT Connection Monitor
Monitors MQTT connection status and handles device-specific MQTT connections
"""

import logging
import json
import time
import threading
import paho.mqtt.client as mqtt
from typing import Dict, Optional, Any, Callable
from .mqtt_device_discovery import get_mqtt_discovery

logger = logging.getLogger(__name__)

class MQTTConnectionMonitor:
    """Manages MQTT connections for device communication"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
        self.mqtt_client = None
        self.device_id = None
        self.connected = False
        self.last_status = None
        self.running = False
        self.monitor_thread = None
        self.initialization_error = None
        self.callbacks = {}
        
        # MQTT configuration
        self.broker_host = 'localhost'
        self.broker_port = 1883
        self.keepalive = 60
        
        # Initialize MQTT client
        self._init_mqtt_client()
    
    def _init_mqtt_client(self):
        """Initialize the MQTT client with proper callbacks"""
        try:
            self.mqtt_client = mqtt.Client(client_id=f"barcode_scanner_{time.time()}")
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.on_publish = self._on_publish
            
            # Set last will message
            self.mqtt_client.will_set(
                topic=f"devices/{self.device_id or 'unknown'}/status",
                payload=json.dumps({"status": "offline"}),
                qos=1,
                retain=True
            )
            
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"⚠️ Failed to initialize MQTT client: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection established"""
        connection_status = {
            0: "Connection successful",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }.get(rc, f"Unknown error: {rc}")
        
        if rc == 0:
            self.connected = True
            self.last_status = True
            self.connection_time = time.time()
            self.disconnect_reason = None
            
            # Log connection details
            logger.info("✅ MQTT Connection Established")
            logger.info(f"   - Broker: {self.broker_host}:{self.broker_port}")
            logger.info(f"   - Client ID: {client._client_id.decode()}")
            logger.info(f"   - Session Present: {flags.get('session present', False)}")
            
            # Subscribe to device-specific topics if device_id is set
            if self.device_id:
                logger.info(f"🔔 Subscribing to device topics for {self.device_id}")
                self._subscribe_to_device_topics()
            else:
                logger.warning("⚠️  No device ID set - not subscribing to device topics")
                
        else:
            self.connected = False
            self.last_status = False
            self.disconnect_reason = connection_status
            logger.error(f"❌ MQTT Connection Failed")
            logger.error(f"   - Error: {connection_status}")
            logger.error(f"   - Broker: {self.broker_host}:{self.broker_port}")
            logger.error(f"   - Client ID: {client._client_id.decode() if hasattr(client, '_client_id') else 'Unknown'}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection"""
        disconnect_reasons = {
            0: "Normal disconnection",
            1: "Transport error",
            2: "Protocol error",
            3: "Client error",
            4: "Network error",
            5: "Client was not authorized to connect",
            6: "Client was not authorized to connect with this configuration"
        }
        
        self.connected = False
        self.last_status = False
        self.disconnect_reason = disconnect_reasons.get(rc, f"Unknown error: {rc}")
        
        # Calculate connection duration if we were connected
        duration = ""
        if hasattr(self, 'connection_time'):
            duration = f" (was connected for {time.time() - self.connection_time:.1f} seconds)"
        
        logger.warning(f"⚠️ MQTT Disconnected")
        logger.warning(f"   - Reason: {self.disconnect_reason}{duration}")
        logger.warning(f"   - Broker: {self.broker_host}:{self.broker_port}")
        
        # Try to reconnect if we're still running
        if self.running:
            retry_delay = 5
            logger.info(f"🔄 Attempting to reconnect in {retry_delay} seconds...")
            time.sleep(retry_delay)
            try:
                self.connect()
            except Exception as e:
                logger.error(f"❌ Reconnection attempt failed: {e}")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # Call registered callbacks for this topic
            if topic in self.callbacks:
                for callback in self.callbacks[topic]:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in MQTT callback for {topic}: {e}")
                        
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message on {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_publish(self, client, userdata, mid):
        """Handle successful message publish"""
        logger.debug(f"Message published (mid: {mid})")
    
    def _subscribe_to_device_topics(self):
        """Subscribe to device-specific topics"""
        if not self.device_id:
            return
            
        base_topic = f"devices/{self.device_id}/#"
        try:
            result, mid = self.mqtt_client.subscribe(base_topic, qos=1)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"✅ Subscribed to MQTT topic: {base_topic}")
            else:
                logger.error(f"❌ Failed to subscribe to {base_topic}")
        except Exception as e:
            logger.error(f"Error subscribing to MQTT topic: {e}")
    
    def register_callback(self, topic: str, callback: Callable[[str, dict], None]):
        """Register a callback for a specific MQTT topic"""
        if topic not in self.callbacks:
            self.callbacks[topic] = []
        self.callbacks[topic].append(callback)
        
        # If already connected, subscribe to the topic
        if self.connected and self.mqtt_client:
            self.mqtt_client.subscribe(topic, qos=1)
        
    def connect(self, device_id: str = None):
        """Connect to the MQTT broker"""
        if device_id and device_id != self.device_id:
            logger.info(f"🆔 Updating device ID to: {device_id}")
            self.device_id = device_id
            
        if not self.mqtt_client:
            logger.debug("Initializing new MQTT client...")
            self._init_mqtt_client()
        
        if not self.mqtt_client:
            logger.error("❌ Cannot connect: MQTT client initialization failed")
            return False
            
        try:
            logger.info(f"🔌 Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            logger.debug(f"   - Client ID: {self.mqtt_client._client_id.decode()}")
            logger.debug(f"   - Keepalive: {self.keepalive}s")
            
            # Record connection attempt time
            connect_start = time.time()
            
            # Connect with timeout
            self.mqtt_client.connect(
                host=self.broker_host,
                port=self.broker_port,
                keepalive=self.keepalive
            )
            
            # Start network loop in a separate thread
            self.mqtt_client.loop_start()
            
            # Wait briefly for connection to complete
            time.sleep(0.5)
            
            if self.connected:
                logger.info(f"✅ MQTT connection established in {(time.time() - connect_start):.2f}s")
                return True
            else:
                logger.error(f"❌ MQTT connection failed - check broker status and credentials")
                return False
                
        except socket.gaierror as e:
            logger.error(f"❌ DNS resolution failed for {self.broker_host}: {e}")
        except ConnectionRefusedError as e:
            logger.error(f"❌ Connection refused by broker at {self.broker_host}:{self.broker_port}")
            logger.error("   - Check if the MQTT broker is running and accessible")
        except TimeoutError as e:
            logger.error(f"❌ Connection timed out while connecting to {self.broker_host}:{self.broker_port}")
            logger.error("   - Check network connectivity and firewall settings")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MQTT broker: {str(e)}")
            
        self.connected = False
        self.last_status = False
        return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                self.connected = False
                logger.info("Disconnected from MQTT broker")
            except Exception as e:
                logger.error(f"Error disconnecting from MQTT broker: {e}")
    
    def publish(self, topic: str, payload: dict, qos: int = 1, retain: bool = False) -> bool:
        """Publish a message to an MQTT topic"""
        if not self.connected or not self.mqtt_client:
            logger.warning("Cannot publish: Not connected to MQTT broker")
            return False
            
        try:
            result = self.mqtt_client.publish(
                topic=topic,
                payload=json.dumps(payload),
                qos=qos,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {mqtt.error_string(result.rc)}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing MQTT message: {e}")
            return False
    
    def start(self):
        """Start the MQTT connection monitoring"""
        if self.running:
            logger.info("MQTT monitor already running")
            return
            
        logger.info("🚀 Starting MQTT connection monitor")
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop(self):
        """Stop the MQTT connection monitoring and clean up"""
        logger.info("🛑 Stopping MQTT connection monitor")
        self.running = False
        
        # Publish offline status
        if self.connected and self.device_id:
            self.publish(
                topic=f"devices/{self.device_id}/status",
                payload={"status": "offline", "timestamp": time.time()},
                qos=1,
                retain=True
            )
        
        # Disconnect from MQTT broker
        self.disconnect()
        
        # Stop monitor thread
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            self.monitor_thread = None
        
        logger.info("✅ MQTT connection monitor stopped")
    
    def _monitor_loop(self):
        """Background thread to monitor MQTT connection status"""
        logger.info("🔍 Starting MQTT connection monitoring loop")
        
        if self.initialization_error:
            logger.warning(f"⚠️ MQTT monitoring starting in degraded mode: {self.initialization_error}")
            logger.info("ℹ️ System will continue with limited functionality")
            time.sleep(2)  # Back off before next check
        
        while self.running:
            try:
                # Check connection status and reconnect if needed
                if not self.connected and self.running:
                    logger.info("Attempting to connect to MQTT broker...")
                    self.connect()
                
                # Publish device status if connected
                if self.connected and self.device_id:
                    self.publish(
                        topic=f"devices/{self.device_id}/status",
                        payload={
                            "status": "online",
                            "timestamp": time.time(),
                            "ip": self._get_local_ip()
                        },
                        qos=1,
                        retain=True
                    )
                
                # Log status changes
                if self.last_status is None:
                    logger.info(f"🔌 Initial MQTT connection status: {'connected' if self.connected else 'disconnected'}")
                elif self.last_status != self.connected:
                    status_change = "✅ Connected" if self.connected else "⚠️ Disconnected"
                    logger.info(f"{status_change} from MQTT broker")
                    self._handle_status_change(self.connected)
                
                self.last_status = self.connected
                
                # Adjust polling interval based on connection state
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Unexpected error in MQTT monitor loop: {e}", exc_info=True)
                time.sleep(5)  # Prevent tight loop on repeated errors
                
    def _handle_status_change(self, connected: bool):
        """
        Handle MQTT connection status changes and update system state accordingly.
        
        Args:
            connected: Boolean indicating if MQTT connection is established
        """
        try:
            if connected:
                logger.info("✅ MQTT connection established")
                # Update connection status first
                self.connection_manager.update_connection_status(
                    iot_hub_connected=True,
                    reason="MQTT connection established"
                )
                
                # Then trigger a full reconnection check
                self.connection_manager.check_iot_hub_connectivity(force_check=True)
                
                # Log the successful connection with broker details
                if self.mqtt_discovery and hasattr(self.mqtt_discovery, 'broker_host'):
                    broker = self.mqtt_discovery.broker_host
                    port = getattr(self.mqtt_discovery, 'broker_port', 'unknown')
                    logger.info(f"🔌 Connected to MQTT broker at {broker}:{port}")
                
            else:
                logger.warning("⚠️ MQTT connection lost")
                # Update connection status immediately
                self.connection_manager.update_connection_status(
                    iot_hub_connected=False,
                    reason="MQTT connection lost"
                )
                
                # Log the last known state for debugging
                logger.debug("MQTT connection lost, last known state: %s", 
                           f"connected to {getattr(self.mqtt_discovery, 'broker_host', 'unknown')}" 
                           if hasattr(self.mqtt_discovery, 'broker_host') else "no broker information")
                
        except Exception as e:
            logger.error(f"Error handling MQTT status change: {e}", exc_info=True)
            # Ensure we don't get stuck in an inconsistent state
            if connected:  # If we were trying to handle a connection event
                self.connection_manager.update_connection_status(
                    iot_hub_connected=False,
                    reason=f"Error handling MQTT connection: {str(e)[:100]}"
                )

# Global instance
mqtt_monitor = None

def init_mqtt_monitor(connection_manager):
    """Initialize the global MQTT monitor instance"""
    global mqtt_monitor
    if mqtt_monitor is None:
        mqtt_monitor = MQTTConnectionMonitor(connection_manager)
        mqtt_monitor.start()
    return mqtt_monitor

def get_mqtt_monitor():
    """Get the global MQTT monitor instance"""
    return mqtt_monitor
