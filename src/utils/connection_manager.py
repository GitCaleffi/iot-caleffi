"""
Connection manager for handling persistent connections to IoT Hub
"""
import logging
import json
import time
import threading
from typing import Dict, Optional, Callable, Any
from queue import Queue, Empty
from datetime import datetime, timezone

# Azure IoT Hub imports
try:
    from azure.iot.device import IoTHubDeviceClient, Message, MethodResponse
    from azure.iot.device.exceptions import ConnectionFailedError, ConnectionDroppedError, OperationTimeout
    AZURE_IOT_AVAILABLE = True
except ImportError:
    AZURE_IOT_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Azure IoT Device SDK not available. Install with: pip install azure-iot-device")

class ConnectionManager:
    """Manages persistent connections to IoT Hub for multiple devices"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0):
        """
        Initialize the connection manager
        
        Args:
            max_retries: Maximum number of retry attempts for failed messages
            retry_delay: Delay between retries in seconds
        """
        if not AZURE_IOT_AVAILABLE:
            raise ImportError("Azure IoT Device SDK is not available. Install with: pip install azure-iot-device")
            
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.device_clients: Dict[str, IoTHubDeviceClient] = {}
        self.message_queues: Dict[str, Queue] = {}
        self.running = False
        self._lock = threading.Lock()
        self._worker_thread = None
        self._callback = None
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    def check_raspberry_pi_availability(self) -> bool:
        """
        Check if the current system is a Raspberry Pi
        
        Returns:
            bool: True if running on a Raspberry Pi, False otherwise
        """
        try:
            with open('/sys/firmware/devicetree/base/model', 'r') as f:
                return 'Raspberry Pi' in f.read()
        except (FileNotFoundError, PermissionError):
            return False

    def start(self, callback: Optional[Callable[[str, str, Any], None]] = None) -> bool:
        """
        Start the connection manager
        
        Args:
            callback: Optional callback function to handle incoming messages
                     Signature: callback(device_id: str, message_type: str, message: Any)
                     
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("Connection manager already running")
            return True
            
        self._callback = callback
        self.running = True
        
        # Start worker thread
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
        self.logger.info("Connection manager started")
        return True
    
    def stop(self):
        """Stop the connection manager and clean up resources"""
        if not self.running:
            return
            
        self.running = False
        
        # Disconnect all clients
        with self._lock:
            for device_id, client in list(self.device_clients.items()):
                self._disconnect_device(device_id)
            
            # Clear queues
            self.message_queues.clear()
        
        # Wait for worker thread to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        
        self.logger.info("Connection manager stopped")
    
    def add_device(self, device_id: str, connection_string: str) -> bool:
        """
        Add a device to the connection manager
        
        Args:
            device_id: Unique device ID
            connection_string: IoT Hub device connection string
            
        Returns:
            bool: True if device was added successfully, False otherwise
        """
        if not device_id or not connection_string:
            self.logger.error("Device ID and connection string are required")
            return False
            
        with self._lock:
            if device_id in self.device_clients:
                self.logger.warning(f"Device {device_id} already exists in connection manager")
                return True
                
            try:
                # Create client
                client = IoTHubDeviceClient.create_from_connection_string(connection_string)
                
                # Set up callbacks
                client.on_connection_state_change = self._on_connection_state_change
                client.on_message_received = self._on_message_received
                client.on_method_request_received = self._on_method_request_received
                
                # Connect
                client.connect()
                
                # Store client and create message queue
                self.device_clients[device_id] = client
                self.message_queues[device_id] = Queue()
                
                self.logger.info(f"Added device {device_id} to connection manager")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to add device {device_id}: {str(e)}")
                return False
    
    def remove_device(self, device_id: str) -> bool:
        """
        Remove a device from the connection manager
        
        Args:
            device_id: Device ID to remove
            
        Returns:
            bool: True if device was removed, False if not found
        """
        with self._lock:
            if device_id not in self.device_clients:
                return False
                
            self._disconnect_device(device_id)
            
            # Remove from dictionaries
            self.device_clients.pop(device_id, None)
            self.message_queues.pop(device_id, None)
            
            self.logger.info(f"Removed device {device_id} from connection manager")
            return True
    
    def send_message(self, device_id: str, message: Any) -> bool:
        """
        Send a message to a device
        
        Args:
            device_id: Target device ID
            message: Message to send (will be JSON-serialized)
            
        Returns:
            bool: True if message was queued successfully, False otherwise
        """
        if not self.running:
            self.logger.warning("Cannot send message: Connection manager not running")
            return False
            
        with self._lock:
            if device_id not in self.message_queues:
                self.logger.error(f"Device {device_id} not found in connection manager")
                return False
                
            # Add message to device's queue
            self.message_queues[device_id].put({
                'data': message,
                'retry_count': 0,
                'timestamp': time.time()
            })
            
            return True
    
    def _worker_loop(self):
        """Worker thread for processing message queues"""
        while self.running:
            try:
                with self._lock:
                    # Make a copy of device IDs to avoid modification during iteration
                    device_ids = list(self.device_clients.keys())
                
                # Process each device's queue
                for device_id in device_ids:
                    self._process_device_queue(device_id)
                
                # Small sleep to prevent busy-waiting
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
                time.sleep(1)  # Prevent tight error loop
    
    def _process_device_queue(self, device_id: str):
        """Process messages for a specific device"""
        try:
            with self._lock:
                if device_id not in self.message_queues:
                    return
                    
                queue = self.message_queues[device_id]
                client = self.device_clients.get(device_id)
                
                if not client or not queue.qsize():
                    return
                
                # Get the next message (without removing it yet)
                try:
                    msg = queue.queue[0]
                except IndexError:
                    return
                
                # Skip if we've exceeded retry count
                if msg['retry_count'] >= self.max_retries:
                    self.logger.error(
                        f"Max retries ({self.max_retries}) exceeded for message to {device_id}"
                    )
                    queue.get()  # Remove from queue
                    return
                
                # Try to send the message
                try:
                    # Convert message to JSON if it's not already a string
                    message = msg['data']
                    if not isinstance(message, str):
                        message = json.dumps(message)
                    
                    # Create and send message
                    iot_message = Message(message)
                    client.send_message(iot_message)
                    
                    # Message sent successfully, remove from queue
                    queue.get()
                    self.logger.debug(f"Message sent to {device_id}")
                    
                except (ConnectionFailedError, ConnectionDroppedError) as e:
                    # Connection issue, will retry
                    msg['retry_count'] += 1
                    self.logger.warning(
                        f"Connection error sending to {device_id} (attempt {msg['retry_count']}): {str(e)}"
                    )
                    time.sleep(self.retry_delay)
                    
                except Exception as e:
                    # Other error, log and remove from queue
                    self.logger.error(
                        f"Error sending message to {device_id}: {str(e)}",
                        exc_info=True
                    )
                    queue.get()  # Remove failed message
        
        except Exception as e:
            self.logger.error(f"Error processing queue for {device_id}: {str(e)}", exc_info=True)
    
    def _disconnect_device(self, device_id: str):
        """Disconnect a device and clean up resources"""
        try:
            client = self.device_clients.get(device_id)
            if client:
                client.disconnect()
                client.shutdown()
        except Exception as e:
            self.logger.error(f"Error disconnecting device {device_id}: {str(e)}")
    
    def _on_connection_state_change(self, connection_status, reason, connection_status_context):
        """Callback for connection state changes"""
        self.logger.info(
            f"Connection status changed: {connection_status}"
            f" (reason: {reason}, context: {connection_status_context})"
        )
    
    def _on_message_received(self, message):
        """Callback for incoming messages"""
        try:
            # Extract device ID from connection string in message
            device_id = None
            if hasattr(message, 'connection_device_id'):
                device_id = message.connection_device_id
            
            # Try to parse message data
            try:
                data = message.data.decode('utf-8')
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    pass  # Not JSON, keep as string
            except Exception:
                data = str(message.data)
            
            # Log the message
            self.logger.info(f"Message received from {device_id or 'unknown'}: {data}")
            
            # Call the callback if set
            if self._callback and device_id:
                try:
                    self._callback(device_id, 'message', data)
                except Exception as e:
                    self.logger.error(f"Error in message callback: {str(e)}", exc_info=True)
        
        except Exception as e:
            self.logger.error(f"Error processing received message: {str(e)}", exc_info=True)
    
    def _on_method_request_received(self, method_request):
        """Callback for direct method requests"""
        try:
            device_id = None
            if hasattr(method_request, 'connection_device_id'):
                device_id = method_request.connection_device_id
            
            self.logger.info(
                f"Method {method_request.name} received from {device_id or 'unknown'} "
                f"with payload: {method_request.payload}"
            )
            
            # Default response
            response_payload = {"status": "success"}
            status = 200
            
            # Call the callback if set
            if self._callback and device_id:
                try:
                    response = self._callback(
                        device_id,
                        'method',
                        {
                            'name': method_request.name,
                            'payload': method_request.payload,
                            'request_id': method_request.request_id
                        }
                    )
                    
                    if isinstance(response, dict):
                        if 'payload' in response:
                            response_payload = response['payload']
                        if 'status' in response:
                            status = response['status']
                
                except Exception as e:
                    self.logger.error(f"Error in method callback: {str(e)}", exc_info=True)
                    response_payload = {"error": str(e)}
                    status = 500
            
            # Send response
            method_response = MethodResponse.create_from_method_request(
                method_request,
                status,
                response_payload
            )
            
            # Find the client for this device
            with self._lock:
                client = self.device_clients.get(device_id) if device_id else None
                
            if client:
                client.send_method_response(method_response)
            else:
                self.logger.warning(f"No client found for device {device_id}, cannot send method response")
        
        except Exception as e:
            self.logger.error(f"Error processing method request: {str(e)}", exc_info=True)

# Singleton instance
_connection_manager = None

def get_connection_manager() -> ConnectionManager:
    """
    Get or create the singleton connection manager instance
    
    Returns:
        ConnectionManager: The singleton instance
    """
    global _connection_manager
    
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    
    return _connection_manager
