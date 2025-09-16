from azure.iot.device import IoTHubDeviceClient, Message
from azure.iot.device.exceptions import ConnectionDroppedError, ConnectionFailedError
import json
import logging
from datetime import datetime, timezone
import time
import traceback
import threading

# Configure logging to show more details
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HubClient:
    def __init__(self, connection_string):
        """Initialize IoT Hub client with connection string"""
        logger.info("Initializing IoT Hub client...")
        self.connection_string = connection_string
        self.client = None
        self.messages_sent = 0
        self.last_message_time = None
        self.connected = False
        self.connection_lock = threading.Lock()
        self.keep_alive = 60  # MQTT keep-alive in seconds
        self.retry_count = 0
        self.max_retries = 3
        
        # Extract device ID from connection string
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
            else:
                logger.warning("Disconnected from IoT Hub")
                self.connected = False
        except Exception as e:
            logger.error(f"Error in connection state change handler: {e}")
            self.connected = False

    def _on_message_sent(self, message_id):
        """Handle message sent confirmation"""
        logger.info(f"Message {message_id} confirmed by IoT Hub")

    def _on_connection_failure(self, error):
        """Handle connection failures"""
        logger.error(f"Connection failure: {error}")
        self.connected = False

    def _schedule_reconnect(self):
        """Schedule a reconnection attempt with exponential backoff"""
        # Reconnection disabled to prevent connection loops and timeout errors
        logger.info("Reconnection disabled to prevent connection conflicts")
        return


    def _reconnect(self):
        """Attempt to reconnect to IoT Hub"""
        # Reconnection disabled to prevent connection loops and timeout errors
        logger.info("Reconnection disabled to prevent connection conflicts")
        return

        
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
            
    def send_message(self, message_or_barcode, device_id, sku=None):
        """Send message to IoT Hub with tracking
        
        Args:
            message_or_barcode: Either a barcode string or a complete message dictionary
            device_id: Device ID for the message
            sku: Optional SKU parameter
        """
        logger.info(f"Sending message with device ID: {device_id}")

        # First check basic internet connectivity
        try:
            # Use Python socket connection instead of ping for live server compatibility
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex(("8.8.8.8", 53))  # DNS port
                
            if result != 0:
                logger.error("No internet connectivity - cannot send to IoT Hub")
                return False
        except Exception as e:
            logger.error(f"Connectivity check failed: {e}")
            return False

        if not self.client or not self.connected:
            logger.info("No active connection, attempting to connect...")
            if not self.connect():
                logger.error("Failed to establish connection to IoT Hub")
                return False

        # Handle both barcode strings and message dictionaries
        if isinstance(message_or_barcode, dict):
            # Complete message dictionary provided
            message_data = message_or_barcode
            logger.info("Using provided message dictionary")
            
            # Create message object from dictionary
            message = Message(json.dumps(message_data))
            message.message_id = f"{device_id}-{int(time.time())}"
        else:
            # Barcode string provided - validate and create message
            barcode = message_or_barcode
            
            # Basic validation
            if not barcode or not barcode.strip():
                logger.error("Invalid barcode: empty or None")
                return False
            
            barcode = barcode.strip()
            
            # Import validation function at the top level
            try:
                from utils.barcode_validator import validate_ean, BarcodeValidationError
            except ImportError:
                logger.error("barcode_validator module not found, cannot validate barcode")
                return False
            
            # Strict EAN validation
            try:
                validate_ean(barcode)
                logger.info(f"Barcode {barcode} passed EAN validation")
                
                # Create message payload for barcode
                message_data = {
                    "scannedBarcode": barcode,
                    "deviceId": device_id,
                    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z'
                }
                
                # Create message with ID
                message = Message(json.dumps(message_data))
                message.message_id = f"{device_id}-{int(time.time())}"
                
            except BarcodeValidationError as e:
                logger.error(f"Invalid EAN barcode format: {e}")
                return False

        logger.info(f"Message to send: {json.dumps(message_data, indent=2)}")
        logger.info(f"Message ID: {message.message_id}")

        # Send message with retry logic
        for attempt in range(self.max_retries):
            try:
                with self.connection_lock:
                    logger.info("Sending message to IoT Hub...")
                    self.client.send_message(message)

                self.messages_sent += 1
                self.last_message_time = datetime.now(timezone.utc)
                self.retry_count = 0

                logger.info(f"Message sent successfully! Total messages sent: {self.messages_sent}")
                return True

            except ConnectionDroppedError as e:
                logger.warning(f"Connection dropped (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep((attempt + 1) * 2)
                    if not self.connect():
                        logger.error("Failed to reconnect")
                        return False
                else:
                    logger.error("Failed to send message after retries")
                    raise

            except Exception as e:
                logger.error(f"Send failed (attempt {attempt + 1}/{self.max_retries}): {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    self.disconnect()
                    if not self.connect():
                        logger.error("Failed to reconnect")
                else:
                    logger.error("All retry attempts failed")

        return False


    def send_device_twin_update(self, twin_properties: dict) -> bool:
        """
        Send Device Twin reported properties update to IoT Hub.
        Used for reporting Pi connection status and other device state.
        """
        try:
            if not self.connected:
                logger.warning("Not connected to IoT Hub - cannot send Device Twin update")
                return False
            
            logger.info(f"Sending Device Twin update: {json.dumps(twin_properties, indent=2)}")
            
            # Send the twin properties update
            self.client.patch_twin_reported_properties(twin_properties)
            
            logger.info("✅ Device Twin properties updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update Device Twin properties: {e}")
            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False

    def send_barcode_message(self, barcode, message_data=None):
        """Send barcode message to IoT Hub - compatibility method"""
        if message_data:
            return self.send_message(message_data, message_data.get('deviceId', self.device_id))
        else:
            return self.send_message(barcode, self.device_id)

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
                logger.info("Successfully disconnected from IoT Hub")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
                logger.error(f"Stack trace: {traceback.format_exc()}")
                self.client = None
                self.connected = False
