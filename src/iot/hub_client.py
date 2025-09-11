from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionDroppedError, ConnectionFailedError
import json
import logging
from datetime import datetime, timezone
import time
import traceback
import threading

logging.basicConfig(
    level=logging.WARNING,  
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

azure_logger = logging.getLogger('azure.iot.device')
azure_logger.setLevel(logging.ERROR)
logger = logging.getLogger(__name__)

class HubClient:
    def __init__(self, connection_string, device_id=None):
        """Initialize IoT Hub client with connection string"""
        logger.info("Initializing IoT Hub client...")
        self.connection_string = connection_string
        self.client = None
        self.messages_sent = 0
        self.last_message_time = None
        self.connected = False
        self.reconnect_timer = None
        self.reconnect_interval = 5  # Start with 5 seconds
        self.max_reconnect_interval = 300  # Maximum 5 minutes
        self.connection_lock = threading.Lock()
        self.keep_alive = 60  # MQTT keep-alive in seconds
        self.retry_count = 0
        self.max_retries = 3
        
        # Use provided device_id or extract from connection string
        try:
            parts = dict(part.split('=', 1) for part in connection_string.split(';'))
            
            if device_id:
                self.device_id = device_id
                logger.info(f"Using provided device ID: {self.device_id}")
            else:
                self.device_id = parts.get('DeviceId')
                if not self.device_id:
                    raise ValueError("DeviceId not found in connection string and no device_id provided")
                logger.info(f"Device ID extracted from connection string: {self.device_id}")
                
        except Exception as e:
            logger.error(f"Error parsing connection string: {e}")
            raise

    def _on_connection_state_change(self, *args):
        """Handle connection state changes"""
        # The callback might be called with different argument patterns
        # We'll check the connection state directly from the client
        try:
            if self.client and hasattr(self.client, 'connected'):
                status = self.client.connected
            else:
                # If we can't determine the state, assume we're disconnected
                status = False

            if status:
                logger.info("Connected to IoT Hub")
                self.connected = True
                self.reconnect_interval = 5  # Reset reconnect interval on successful connection
            else:
                logger.warning("Disconnected from IoT Hub")
                self.connected = False
                self._schedule_reconnect()
        except Exception as e:
            logger.error(f"Error in connection state change handler: {e}")
            self.connected = False
            self._schedule_reconnect()

    def _on_message_sent(self, message_id):
        """Handle message sent confirmation"""
        logger.info(f"Message {message_id} confirmed by IoT Hub")

    def _on_connection_failure(self, error):
        """Handle connection failures"""
        logger.error(f"Connection failure: {error}")
        self.connected = False
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt with exponential backoff"""
        if not self.reconnect_timer:
            logger.info(f"Scheduling reconnection in {self.reconnect_interval} seconds")
            self.reconnect_timer = threading.Timer(self.reconnect_interval, self._reconnect)
            self.reconnect_timer.daemon = True
            self.reconnect_timer.start()
            # Increase reconnect interval with exponential backoff
            self.reconnect_interval = min(self.reconnect_interval * 2, self.max_reconnect_interval)

    def _reconnect(self):
        """Attempt to reconnect to IoT Hub"""
        self.reconnect_timer = None
        logger.info("Attempting to reconnect to IoT Hub...")
        try:
            with self.connection_lock:
                if self.client:
                    try:
                        self.client.disconnect()
                    except:
                        pass
                    self.client = None
                self.connect()
        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            self._schedule_reconnect()
        
    def connect(self):
        """Connect to IoT Hub and return connection status"""
        try:
            # Create client if it doesn't exist
            if not self.client:
                logger.info("Creating IoT Hub client...")
                self.client = IoTHubDeviceClient.create_from_connection_string(
                    self.connection_string,
                    keep_alive=self.keep_alive
                )
                self.client.on_connection_state_change = self._on_connection_state_change
                self.client.on_message_sent = self._on_message_sent

            # Connect to hub with retry logic
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Connection attempt {attempt + 1}/{max_attempts}")
                    logger.info("Connecting to Hub...")
                    self.client.connect()
                    self.connected = True
                    logger.info("Successfully connected to Hub")
                    self.retry_count = 0  # Reset retry count on successful connection
                    return True
                except (ConnectionDroppedError, ConnectionFailedError) as e:
                    if attempt < max_attempts - 1:
                        wait_time = (attempt + 1) * 2  # Exponential backoff
                        logger.info(f"Connection attempt failed, retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Connection attempt {attempt + 1}/{max_attempts} failed: {e}")
                        if attempt == max_attempts - 1:
                            raise
            
        except Exception as e:
            logger.error(f"Failed to connect to IoT Hub: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            self.client = None
            self.connected = False
            return False
    
    def test_connection(self):
        """Test connection to IoT Hub"""
        try:
            if not self.client or not self.connected:
                logger.info("No active connection, attempting to connect...")
                if not self.connect():
                    raise Exception("Failed to establish connection")
                    
            # Try to get device twin to test connection
            logger.info("Testing connection by retrieving device twin...")
            twin = self.client.get_twin()
            logger.info(f"Successfully retrieved device twin")
            return True
            
        except Exception as e:
            logger.error(f"IoT Hub connection error: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            raise Exception(f"IoT Hub connection error: {e}")
            
    def send_message(self, barcode, device_id, sku=None):
        """Send barcode to IoT Hub with persistent connection"""
        logger.info(f"Sending message with device ID: {device_id}")

        # Validate barcode format - allow EAN barcodes (8-13 characters)
        if not barcode or len(barcode) < 8 or len(barcode) > 13:
            logger.error(f"Invalid barcode length: {len(barcode) if barcode else 0}. Must be 8-13 characters for EAN barcodes.")
            return False
        
        # Allow alphanumeric characters for various barcode formats (Code 128, Code 39, etc.)
        if not barcode.replace('-', '').replace('_', '').isalnum():
            logger.error(f"Invalid barcode format: {barcode}. Must contain only alphanumeric characters, hyphens, or underscores.")
            return False

        # Ensure connection is active
        if not self.client or not self.connected:
            logger.info("Establishing persistent connection...")
            if not self.connect():
                logger.error("Failed to establish connection")
                return False

        # Create message payload
        message_data = {
            "scannedBarcode": barcode,
            "deviceId": device_id,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z'
        }

        # Create message with ID
        message = Message(json.dumps(message_data))
        message.message_id = f"{device_id}-{int(time.time())}"

        logger.info(f"Message ID: {message.message_id}")

        # Send message with retry logic but maintain connection
        for attempt in range(self.max_retries):
            try:
                with self.connection_lock:
                    logger.info("Sending message via persistent connection...")
                    self.client.send_message(message)

                self.messages_sent += 1
                self.last_message_time = datetime.now(timezone.utc)
                self.retry_count = 0

                logger.info(f"✅ Message sent successfully! Total: {self.messages_sent} (Connection maintained)")
                return True

            except ConnectionDroppedError as e:
                logger.warning(f"Connection dropped (attempt {attempt + 1}/{self.max_retries}), reconnecting...")
                if attempt < self.max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    if not self.connect():
                        logger.error("Failed to reconnect")
                        return False
                else:
                    logger.error("Failed to send message after retries")
                    return False

            except Exception as e:
                logger.error(f"Send failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    # Try to reconnect without disconnecting first
                    if not self.connect():
                        logger.error("Failed to reconnect")
                else:
                    logger.error("All retry attempts failed")

        return False


    def get_status(self):
        """Get current IoT Hub client status"""
        return {
            "connected": self.connected,
            "deviceId": self.device_id,
            "messages_sent": self.messages_sent,
            "last_message_time": self.last_message_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z' if self.last_message_time else None
        }
        
    def disconnect(self):
        """Disconnect from IoT Hub (only when explicitly needed)"""
        if self.client:
            try:
                logger.info("Explicitly disconnecting from IoT Hub...")
                self.client.disconnect()
                self.client = None
                self.connected = False
                logger.info("Successfully disconnected from IoT Hub")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
                self.client = None
                self.connected = False
                
    def __del__(self):
        """Cleanup on object destruction"""
        try:
            if self.client and self.connected:
                self.disconnect()
        except:
            pass
