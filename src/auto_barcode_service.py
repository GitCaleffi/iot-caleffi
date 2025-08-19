#!/usr/bin/env python3
import os
import sys
import time
import logging
import threading
import uuid
import signal
from pathlib import Path
from datetime import datetime, timezone
import subprocess
import select
import fcntl
import termios

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add project root to Python path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

# Import required modules
from utils.config import load_config, save_config
from iot.hub_client import HubClient
from database.local_storage import LocalStorage
from api.api_client import ApiClient
from utils.dynamic_device_manager import device_manager
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.dynamic_device_id import generate_dynamic_device_id
from barcode_validator import validate_ean, BarcodeValidationError

class AutoBarcodeService:
    def __init__(self):
        """Initialize the automatic barcode scanning service"""
        logger.info("🚀 Starting Automatic Barcode Scanning Service")
        
        # Initialize components
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        
        # Generate or retrieve device ID
        self.device_id = self._get_or_create_device_id()
        
        # Register device if needed
        self._ensure_device_registered()
        
        # Setup barcode input handling
        self.running = True
        self.input_thread = None
        
        # Process any unsent messages
        self._process_unsent_messages()
        
        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("📴 Shutting down Automatic Barcode Scanning Service...")
        self.running = False
        if self.input_thread and self.input_thread.is_alive():
            self.input_thread.join(timeout=2)
        logger.info("👋 Service stopped. Goodbye!")
        sys.exit(0)
    
    def _get_or_create_device_id(self):
        """Get existing device ID or create a new one based on hardware"""
        # Try to get device ID from local storage
        device_id = self.local_db.get_device_id()
        
        if device_id:
            logger.info(f"✅ Using existing device ID: {device_id}")
            return device_id
        
        # Generate a new device ID based on hardware
        device_id = self._generate_hardware_based_device_id()
        logger.info(f"🆕 Generated new device ID: {device_id}")
        
        return device_id
    
    def _generate_hardware_based_device_id(self):
        """Generate a device ID based on hardware identifiers"""
        try:
            # Try to get CPU serial number (works on Raspberry Pi)
            cpu_serial = "unknown"
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('Serial'):
                            cpu_serial = line.split(':')[1].strip()
                            break
            except:
                pass
            
            # Try to get MAC address
            mac_address = "unknown"
            try:
                from uuid import getnode
                mac = getnode()
                mac_address = ':'.join(("%012X" % mac)[i:i+2] for i in range(0, 12, 2))
            except:
                pass
            
            # Create a unique ID based on hardware identifiers
            if cpu_serial != "unknown":
                return f"device-{cpu_serial[:8]}"
            elif mac_address != "unknown":
                return f"device-{mac_address.replace(':', '')[:8]}"
            else:
                # Fallback to a random ID with hostname prefix
                import socket
                hostname = socket.gethostname()
                return f"{hostname}-{uuid.uuid4().hex[:8]}"
                
        except Exception as e:
            logger.error(f"Error generating hardware-based device ID: {str(e)}")
            # Final fallback
            return f"auto-device-{uuid.uuid4().hex[:8]}"
    
    def _ensure_device_registered(self):
        """Ensure the device is registered with IoT Hub"""
        try:
            # Check if device is already registered
            registered_devices = self.local_db.get_registered_devices()
            device_already_registered = any(device.get('device_id') == self.device_id for device in registered_devices)
            
            if device_already_registered:
                logger.info(f"✅ Device {self.device_id} is already registered")
                self._blink_led("green")
                return
            
            # Register the device
            logger.info(f"🔄 Registering device {self.device_id} with IoT Hub...")
            
            # Get configuration
            config = load_config()
            if not config or not config.get("iot_hub", {}).get("connection_string"):
                logger.error("❌ No IoT Hub configuration found")
                self._blink_led("red")
                return
            
            # Register with IoT Hub
            iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
            registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
            
            if not registration_service:
                logger.error("❌ Failed to initialize registration service")
                self._blink_led("red")
                return
            
            # Register device and get connection string
            device_connection_string = registration_service.register_device_with_azure(self.device_id)
            
            if not device_connection_string:
                logger.error("❌ Failed to register device with Azure IoT Hub")
                self._blink_led("red")
                return
            
            # Save registration in local database
            timestamp = datetime.now()
            self.local_db.save_device_registration(self.device_id, timestamp)
            
            # Send confirmation message to IoT Hub
            hub_client = HubClient(device_connection_string)
            message = {
                "event": "device_registered",
                "device_id": self.device_id,
                "timestamp": timestamp.isoformat()
            }
            hub_client.send_message(str(message), self.device_id)
            
            logger.info(f"✅ Device {self.device_id} registered successfully")
            self._blink_led("green")
            
        except Exception as e:
            logger.error(f"❌ Error registering device: {str(e)}")
            self._blink_led("red")
    
    def _process_unsent_messages(self):
        """Process any unsent messages in the database"""
        try:
            unsent_messages = self.local_db.get_unsent_messages()
            if not unsent_messages:
                return
            
            logger.info(f"🔄 Processing {len(unsent_messages)} unsent messages...")
            
            # Get configuration
            config = load_config()
            if not config or not config.get("iot_hub", {}).get("connection_string"):
                logger.error("❌ No IoT Hub configuration found")
                return
            
            # Get registration service
            iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
            registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
            
            if not registration_service:
                logger.error("❌ Failed to initialize registration service")
                return
            
            success_count = 0
            fail_count = 0
            
            for message in unsent_messages:
                device_id = message.get('device_id')
                barcode = message.get('barcode')
                timestamp = message.get('timestamp')
                
                # Try to send to API first
                api_result = self.api_client.send_barcode_scan(device_id, barcode, 1)
                api_success = api_result.get("success", False)
                
                # Try to send to IoT Hub
                hub_success = False
                device_connection_string = registration_service.register_device_with_azure(device_id)
                
                if device_connection_string:
                    hub_client = HubClient(device_connection_string)
                    hub_success = hub_client.send_message(barcode, device_id)
                
                if api_success or hub_success:
                    self.local_db.mark_sent(device_id, barcode, timestamp)
                    success_count += 1
                else:
                    fail_count += 1
            
            logger.info(f"✅ Processed {len(unsent_messages)} unsent messages. Success: {success_count}, Failed: {fail_count}")
            
        except Exception as e:
            logger.error(f"❌ Error processing unsent messages: {str(e)}")
    
    def _blink_led(self, color):
        """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error."""
        try:
            logger.info(f"💡 Blinking {color} LED on Raspberry Pi.")
            # Implement LED blinking based on your hardware setup
            # This is a placeholder for actual LED control code
        except Exception as e:
            logger.error(f"LED blink error: {str(e)}")
    
    def _process_barcode(self, barcode):
        """Process a scanned barcode"""
        try:
            if not barcode or barcode.strip() == "":
                self._blink_led("red")
                logger.error("❌ Empty barcode received")
                return
            
            barcode = barcode.strip()
            logger.info(f"📊 Processing barcode: {barcode}")
            
            # Validate the barcode format (optional - can be disabled for more flexibility)
            try:
                validated_barcode = validate_ean(barcode)
                logger.info(f"✅ Barcode format validation passed: {validated_barcode}")
                # Use the validated barcode for further processing
                barcode = validated_barcode
            except BarcodeValidationError as e:
                logger.warning(f"⚠️ Barcode validation warning: {str(e)}")
                # Continue processing - dynamic system is more flexible with non-EAN barcodes
            
            # Check for duplicate barcode scan to prevent looping/repeated hits
            recent_scans = self.local_db.get_recent_scans(self.device_id, barcode, minutes=5)
            if recent_scans:
                logger.info(f"⚠️ Duplicate barcode scan detected: {barcode}")
                self._blink_led("yellow")  # Yellow LED for duplicate scan
                return
            
            # Check if we're online
            is_online = self.api_client.is_online()
            
            # Save scan to local database
            timestamp = datetime.now()
            self.local_db.save_barcode_scan(self.device_id, barcode, timestamp)
            
            if not is_online:
                # Store barcode locally for later processing
                self.local_db.save_unsent_message(self.device_id, barcode, timestamp)
                self._blink_led("orange")
                logger.warning(f"⚠️ Device is offline. Barcode '{barcode}' saved locally for later processing.")
                return
            
            # Process barcode online
            # Send to API first
            api_result = self.api_client.send_barcode_scan(self.device_id, barcode, 1)
            api_success = api_result.get("success", False)
            
            # Send to IoT Hub
            config = load_config()
            hub_success = False
            
            if config and config.get("iot_hub", {}).get("connection_string"):
                try:
                    # Get device connection string via dynamic registration
                    iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                    registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                    
                    if registration_service:
                        device_connection_string = registration_service.register_device_with_azure(self.device_id)
                        
                        if device_connection_string:
                            hub_client = HubClient(device_connection_string)
                            hub_success = hub_client.send_message(barcode, self.device_id)
                        else:
                            logger.error("❌ Failed to get device connection string for barcode send")
                    else:
                        logger.error("❌ Failed to initialize registration service for barcode send")
                except Exception as hub_error:
                    logger.error(f"❌ IoT Hub error: {hub_error}")
            else:
                logger.error("❌ No IoT Hub configuration found for barcode send")
            
            # Determine overall success and provide feedback
            if api_success and hub_success:
                self._blink_led("green")
                logger.info(f"✅ Barcode {barcode} processed successfully (API + IoT Hub)")
            elif api_success and not hub_success:
                # Store for IoT Hub retry
                self.local_db.save_unsent_message(self.device_id, barcode, timestamp)
                self._blink_led("orange")
                logger.warning(f"⚠️ Barcode {barcode} sent to API but failed to send to IoT Hub")
            elif not api_success and hub_success:
                self._blink_led("orange")
                logger.warning(f"⚠️ Barcode {barcode} sent to IoT Hub but failed to send to API")
            else:
                # Both failed - store for retry
                self.local_db.save_unsent_message(self.device_id, barcode, timestamp)
                self._blink_led("red")
                logger.error(f"❌ Failed to send barcode {barcode} to both API and IoT Hub")
            
        except Exception as e:
            logger.error(f"❌ Error processing barcode: {str(e)}")
            self._blink_led("red")
    
    def _setup_input_device(self):
        """Set up the input device for barcode scanning"""
        try:
            # Try to find a barcode scanner device
            # This is a simplified approach - in production, you might want to 
            # identify the specific input device more precisely
            
            # For now, we'll just use stdin in non-blocking mode
            # This allows the service to read from standard input (keyboard/scanner)
            # without blocking the main thread
            
            fd = sys.stdin.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            logger.info("✅ Input device setup complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up input device: {str(e)}")
            return False
    
    def _listen_for_barcodes(self):
        """Listen for barcode input in a separate thread"""
        logger.info("👂 Starting barcode input listener...")
        
        buffer = ""
        
        while self.running:
            try:
                # Check if there's input available
                r, _, _ = select.select([sys.stdin], [], [], 0.1)
                
                if r:
                    # Read a character
                    char = sys.stdin.read(1)
                    
                    # If it's a newline or carriage return, process the buffer as a barcode
                    if char in ['\n', '\r']:
                        if buffer:
                            self._process_barcode(buffer)
                            buffer = ""
                    else:
                        # Add character to buffer
                        buffer += char
                
                # Small sleep to prevent CPU hogging
                time.sleep(0.01)
                
            except Exception as e:
                if not isinstance(e, BlockingIOError):  # Ignore blocking IO errors
                    logger.error(f"❌ Error in barcode listener: {str(e)}")
                time.sleep(0.1)
    
    def start(self):
        """Start the automatic barcode scanning service"""
        logger.info("🚀 Starting automatic barcode scanning service...")
        
        # Setup input device
        if not self._setup_input_device():
            logger.error("❌ Failed to set up input device. Exiting.")
            return False
        
        # Start barcode listening thread
        self.input_thread = threading.Thread(target=self._listen_for_barcodes)
        self.input_thread.daemon = True
        self.input_thread.start()
        
        logger.info(f"""
✅ Automatic Barcode Scanner Service Started!
-----------------------------------------
🆔 Device ID: {self.device_id}
📊 Ready to scan barcodes
💾 Local storage: {self.local_db.db_path}
-----------------------------------------
Simply scan any barcode to process it automatically.
No manual submission required!
        """)
        
        # Keep the main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("👋 Received keyboard interrupt. Shutting down...")
            self.running = False
            if self.input_thread and self.input_thread.is_alive():
                self.input_thread.join(timeout=2)
        
        return True

if __name__ == "__main__":
    service = AutoBarcodeService()
    service.start()
