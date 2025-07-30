from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionDroppedError, ConnectionFailedError
import json
import logging
from datetime import datetime, timezone, timedelta
import time
import traceback
import threading
import redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HubClient:
    def __init__(self, connection_string,redis_host='localhost', redis_port=6379, redis_db=0):
        """Initialize IoT Hub client with connection string"""
        logger.info("Initializing IoT Hub client...")
        self.connection_string = connection_string
        self.client = None
        self.redis_ttl = 7 * 24 * 3600
        self.redis = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.messages_sent = 0
        self.last_message_time = None
        self.connected = False
        self.reconnect_timer = None
        self.reconnect_interval = 5
        self.max_reconnect_interval = 300
        self.connection_lock = threading.Lock()
        self.keep_alive = 60
        self.retry_count = 0
        self.max_retries = 1
    
        try:
            parts = dict(part.split('=', 1) for part in connection_string.split(';'))
            self.device_id = parts.get('DeviceId')
            if not self.device_id:
                raise ValueError("DeviceId not found in connection string")
            logger.info(f"Device ID extracted: {self.device_id}")
        except Exception as e:
            logger.error(f"Error parsing connection string: {e}")
            raise

    def _on_connection_state_change(self, *args):
        """Handle connection state changes"""
        try:
            if self.client and hasattr(self.client, 'connected'):
                status = self.client.connected
            else:
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
                    if attempt < max_retries - 1:
                        logger.warning(f"Connection attempt failed: {e}. Retrying...")
                        time.sleep(2 ** attempt)
                    else:
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
            
    def send_message(self, barcode_or_payload, device_id=None, quantity=1):
        """
        Send message to IoT Hub - supports both simple barcode string or full JSON payload
        
        Args:
            barcode_or_payload: Either a barcode string or a complete message payload dict
            device_id: The device ID (required if barcode_or_payload is a string)
            quantity: The quantity value (only used if barcode_or_payload is a string)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Determine if we're dealing with a barcode string or a full payload
        if isinstance(barcode_or_payload, dict):
            # This is a full payload
            message_data = barcode_or_payload
            device_id = message_data.get("deviceId", device_id)
            barcode = message_data.get("scannedBarcode")
        else:
            # This is just a barcode string
            barcode = barcode_or_payload
            # Create message data with quantity
            message_data = {
                "scannedBarcode": barcode,
                "deviceId": device_id or self.device_id,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        # Validate required fields
        if not device_id and not message_data.get("deviceId"):
            device_id = self.device_id
            message_data["deviceId"] = device_id
            logger.info(f"Using default device ID: {device_id}")

        if not device_id and not message_data.get("deviceId"):
            logger.error("No device ID provided and no default device ID available.")
            return False

        if not barcode and not message_data.get("scannedBarcode"):
            logger.error("Barcode cannot be empty")
            return False
            
        barcode_to_check = barcode or message_data.get("scannedBarcode", "")
        if len(barcode_to_check) > 20:
            logger.error(f"Invalid barcode length: {len(barcode_to_check)}. Must be 20 or fewer characters.")
            return False

        # Create new connection for each message
        if self.client:
            try:
                self.disconnect()
            except:
                pass
            self.client = None

        # Connect fresh for this message
        logger.info("Creating fresh connection for new message...")
        if not self.connect():
            logger.error("Failed to establish connection")
            return False

        # Ensure the message has a timestamp if not already provided
        if "timestamp" not in message_data:
            current_time = datetime.now(timezone.utc)
            message_data["timestamp"] = current_time.isoformat()

        # Extract device ID from message data for message ID
        msg_device_id = message_data.get("deviceId", device_id or self.device_id)
        
        # Prepare IoT Hub message
        message = Message(json.dumps(message_data))
        message.message_id = f"{msg_device_id}-{int(time.time())}"

        logger.info(f"Sending new message: {json.dumps(message_data)}")

        sent = False

        for attempt in range(self.max_retries):
            if sent:
                break

            try:
                with self.connection_lock:
                    logger.info(f"Sending message (attempt {attempt + 1})...")
                    self.client.send_message(message)
                    sent = True

                # Send message and disconnect immediately
                self.messages_sent += 1
                self.last_message_time = current_time
                logger.info(f"✅ Message sent successfully")
                self.disconnect()
                return True

            except ConnectionDroppedError as e:
                logger.warning(f"Connection dropped (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    self.disconnect()
                    time.sleep((attempt + 1) * 2)
                    if not self.connect():
                        logger.error("Failed to reconnect after connection drop")
                        return False
                else:
                    logger.error("Max retries reached. Message not sent.")
                    return False

            except Exception as e:
                logger.error(f"Send failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                logger.debug(traceback.format_exc())
                if attempt < self.max_retries - 1:
                    self.disconnect()
                    time.sleep(2 ** attempt)
                    if not self.connect():
                        logger.error("Failed to reconnect after exception")
                        return False
                else:
                    logger.error("All retry attempts failed")
                    return False

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
        """Disconnect from IoT Hub"""
        if self.client:
            try:
                logger.info("Disconnecting from IoT Hub...")
                self.client.disconnect()
                self.client = None
                self.connected = False
                logger.info("Creating fresh connection for new message...")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                self.client = None
                self.connected = False
