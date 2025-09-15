import gradio as gr
import json
import os
import sys
from pathlib import Path
import logging
import time
import threading
import queue
import subprocess
import uuid
import requests
import re
import socket
from datetime import datetime, timezone, timedelta
import glob
try:
    from .barcode_validator import validate_ean, BarcodeValidationError
except ImportError:
    try:
        # Try local barcode_validator module first
        import sys
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        sys.path.insert(0, current_dir)
        from barcode_validator import validate_ean, BarcodeValidationError
    except ImportError:
        # Fallback: create simple validation function
        class BarcodeValidationError(Exception):
            pass
        
        def validate_ean(barcode):
            """Simple barcode validation fallback"""
            if not barcode:
                raise BarcodeValidationError("Barcode cannot be empty")
            
            barcode = str(barcode).strip()
            
            # Allow alphanumeric barcodes (6-20 characters)
            if len(barcode) < 6 or len(barcode) > 20:
                raise BarcodeValidationError(f"Barcode must be 6-20 characters, got {len(barcode)}")
            
            return barcode
try:
    from utils.device_registration import get_local_mac_address as get_local_device_mac
except ImportError:
    # Fallback when running as standalone script
    def get_local_device_mac():
        return None

# GPIO LED Control for Raspberry Pi - Import only when actually on Pi
GPIO_AVAILABLE = False
try:
    # First check if we're on a Raspberry Pi before importing
    import platform
    import os
    
    # Check multiple indicators for Raspberry Pi
    is_pi = (
        os.path.exists('/proc/device-tree/model') and 
        'raspberry pi' in open('/proc/device-tree/model', 'r').read().lower()
    ) or (
        'arm' in platform.machine().lower() and 
        os.path.exists('/sys/firmware/devicetree/base/model')
    )
    
    if is_pi:
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        print("✅ RPi.GPIO loaded successfully - LED functionality enabled")
    else:
        print("ℹ️ Not running on Raspberry Pi - LED functionality will use simulation mode")
        
except (ImportError, RuntimeError, FileNotFoundError) as e:
    GPIO_AVAILABLE = False
    print(f"ℹ️ RPi.GPIO not available: {e} - LED functionality will use simulation mode")

# ============================================================================
# CONFIGURATION AND GLOBAL VARIABLES
# ============================================================================

# Global variables for Pi status reporting
pi_status_thread = None
last_pi_status = None
pi_status_queue = queue.Queue()

# Registration control
REGISTRATION_IN_PROGRESS = False
registration_lock = threading.Lock()
processed_device_ids = set()

# ============================================================================
# USB HID SCANNER CONFIGURATION
# ============================================================================

# HID key mapping for normal keys
HID_KEYS = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j',
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's',
    23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: 'ENTER', 44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\',
    51: ';', 52: "'", 53: '`', 54: ',', 55: '.', 56: '/'
}

# HID key mapping for shifted characters
HID_KEYS_SHIFT = {
    4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J',
    14: 'K', 15: 'L', 16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S',
    23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y', 29: 'Z',
    30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')',
    44: ' ', 45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<',
    55: '>', 56: '?'
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_local_mac_address() -> str:
    """Get the MAC address of the local device dynamically."""
    # Method 1: Use ip link command (most reliable for servers)
    try:
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mac_pattern = r'link/ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Found MAC address via ip link: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ip link method failed: {e}")

    # Method 2: Use ifconfig command (fallback)
    try:
        result = subprocess.run(
            ["ifconfig"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            mac_pattern = r'ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Found MAC address via ifconfig: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ifconfig method failed: {e}")

    logger.error("❌ Could not detect local device MAC address using any method")
    return None

logger = logging.getLogger(__name__)

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config, save_config
from iot.hub_client import HubClient
from database.local_storage import LocalStorage
from api.api_client import ApiClient
# FastBarcodeAPI is a separate FastAPI application - not imported here
from api.pi_device_notification import create_pi_notification_endpoint
from utils.dynamic_device_manager import device_manager
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.dynamic_device_id import generate_dynamic_device_id
from utils.network_discovery import NetworkDiscovery
from utils.connection_manager import ConnectionManager

from utils.mqtt_device_discovery import get_mqtt_discovery, discover_raspberry_pi_devices, get_primary_raspberry_pi_ip as mqtt_get_primary_pi_ip
# Removed auto IP detection - not needed for local MAC address mode

# Import IoT Hub registry manager for device registration
try:
    from azure.iot.hub import IoTHubRegistryManager
    from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
    IOT_HUB_REGISTRY_AVAILABLE = True
except ImportError:
    logger.warning("Azure IoT Hub Registry Manager not available. Device registration will be limited.")
    IOT_HUB_REGISTRY_AVAILABLE = False

# Initialize database and API client
local_db = LocalStorage()
api_client = ApiClient()

# Offline simulation removed

# Track all processed device IDs, even those not saved in the database
processed_device_ids = set()

# Auto-registration function with IoT Hub integration
def auto_register_device_to_server():
    """Automatically register device with live server and IoT Hub using local MAC address"""
    try:
        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("❌ Cannot auto-register: MAC address not found")
            return False
            
        # Generate device ID from MAC address
        device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
        
        # Check if already registered
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device.get('device_id') == device_id for device in registered_devices)
        
        if device_already_registered:
            logger.info(f"✅ Device {device_id} already registered - initializing IoT Hub connection")
            # Initialize IoT Hub connection for existing device
            _initialize_iot_hub_connection(device_id)
            return True
        
        # Get local IP address
        import socket
        try:
            # Connect to a remote server to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
            
        logger.info(f"🚀 Auto-registering new device {device_id} (MAC: {mac_address}, IP: {local_ip})")
        
        # Step 1: Register with IoT Hub using dynamic registration service
        try:
            registration_service = get_dynamic_registration_service()
            token = device_manager.generate_registration_token()
            
            device_info = {
                "registration_method": "auto_plug_and_play",
                "mac_address": mac_address,
                "ip_address": local_ip,
                "auto_registered": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            success, message = device_manager.register_device(token, device_id, device_info)
            
            if success:
                logger.info(f"✅ Device {device_id} registered with IoT Hub successfully")
                
                # Save to local database
                local_db.save_device_id(device_id)
                
                # Initialize IoT Hub connection
                _initialize_iot_hub_connection(device_id)
                
                # Step 2: Register with live server API (optional)
                _register_with_live_server(device_id, mac_address, local_ip)
                
                return True
            else:
                logger.error(f"❌ IoT Hub registration failed: {message}")
                return False
                
        except Exception as e:
            logger.error(f"❌ IoT Hub registration error: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Auto-registration error: {e}")
        return False

def _initialize_iot_hub_connection(device_id):
    """Initialize IoT Hub connection for a registered device"""
    try:
        # Get device connection string from dynamic registration service
        device_connection_string = device_manager.get_device_connection_string(device_id)
        if device_connection_string:
            # Initialize IoT Hub client with device-specific connection string
            hub_client = HubClient(device_connection_string)
            
            # Send registration confirmation to IoT Hub
            confirmation_msg = {
                "deviceId": device_id,
                "status": "auto_registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Device auto-registered via plug-and-play",
                "messageType": "device_registration"
            }
            
            hub_client.send_message(json.dumps(confirmation_msg), device_id)
            logger.info("📡 Registration confirmation sent to IoT Hub")
            
            # Send single heartbeat to IoT Hub (no background thread)
            _send_iot_hub_heartbeat(device_id, device_connection_string)
            
        else:
            logger.error(f"❌ Could not get device connection string for {device_id}")
            
    except Exception as e:
        logger.error(f"❌ IoT Hub connection initialization error: {e}")

def _register_with_live_server(device_id, mac_address, local_ip):
    """Register device with live server API (optional step)"""
    try:
        registration_data = {
            "device_id": device_id,
            "mac_address": mac_address,
            "ip_address": local_ip
        }
        
        # Send to live server - try multiple endpoints
        live_server_urls = [
            "http://localhost:5000/api/pi-device-register",  # Local web app first
            "https://iot.caleffionline.it/api/pi-device-register"  # Live server fallback
        ]
        
        # Try each URL until one works
        for url in live_server_urls:
            try:
                logger.info(f"Trying live server registration: {url}")
                response = requests.post(
                    url,
                    json=registration_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Device registered with live server: {url}")
                    
                    # Send single heartbeat to live server (no background thread)
                    heartbeat_url = url.replace('/api/pi-device-register', '/api/pi-device-heartbeat')
                    # send_heartbeat_to_server(device_id, local_ip, heartbeat_url)
                    
                    return True
                else:
                    logger.warning(f"Live server registration failed for {url}: {response.status_code}")
                    
            except Exception as e:
                logger.warning(f"Live server registration error for {url}: {e}")
                continue
        
        logger.warning("⚠️ Live server registration failed for all endpoints (IoT Hub registration still successful)")
        return False
        
    except Exception as e:
        logger.warning(f"⚠️ Live server registration error: {e}")
        return False

def _send_iot_hub_heartbeat(device_id, device_connection_string):
    """Send single heartbeat to IoT Hub (no loop)"""
    try:
        hub_client = HubClient(device_connection_string)
        
        # Send heartbeat message
        heartbeat_message = {
            "deviceId": device_id,
            "messageType": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "status": "active"
        }
        
        hub_client.send_message(heartbeat_message)
        logger.info(f"💓 Heartbeat sent to IoT Hub for device: {device_id}")
        
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")

def is_raspberry_pi():
    """Check if the current system is a Raspberry Pi using multiple methods."""
    # Method 1: Check CPU info for ARM architecture (most reliable)
    try:
        with open('/proc/cpuinfo', 'r') as cpuinfo:
            content = cpuinfo.read().lower()
            # Check for ARM architecture indicators
            if any(indicator in content for indicator in ['arm', 'bcm', 'raspberry']):
                return True
            # If we see Intel/AMD, definitely not a Pi
            if any(vendor in content for vendor in ['genuineintel', 'authenticamd']):
                return False
    except Exception:
        pass

    # Method 2: Check the model file (modern Pis)
    try:
        with open('/sys/firmware/devicetree/base/model', 'r') as model_file:
            if 'raspberry pi' in model_file.read().lower():
                return True
    except Exception:
        pass
        
    # Method 3: Check the OS release info
    try:
        with open('/etc/os-release', 'r') as os_release:
            if 'raspbian' in os_release.read().lower():
                return True
    except Exception:
        pass

    # Method 4: Check hostname as last resort (unreliable but sometimes helpful)
    try:
        import socket
        hostname = socket.gethostname().lower()
        # Only use hostname if other methods are inconclusive AND it contains 'pi'
        # This is a weak indicator, so we're conservative
        if 'pi' in hostname:
            # But double-check we're not on Intel/AMD first
            with open('/proc/cpuinfo', 'r') as cpuinfo:
                if any(vendor in cpuinfo.read().lower() for vendor in ['genuineintel', 'authenticamd']):
                    return False
            # If no Intel/AMD detected and hostname suggests Pi, tentatively yes
            # But this is still unreliable
            return False  # Being conservative - hostname alone isn't enough
    except Exception:
        pass

    return False

IS_RASPBERRY_PI = is_raspberry_pi()

# GPIO LED Configuration
# ============================================================================
# LED CONTROL SYSTEM
# ============================================================================

class LEDController:
    """Control RGB LEDs on Raspberry Pi GPIO pins"""
    
    def __init__(self):
        self.gpio_available = GPIO_AVAILABLE and IS_RASPBERRY_PI
        self.led_pins = {
            'red': 18,     # GPIO 18 (Pin 12)
            'yellow': 23,  # GPIO 23 (Pin 16) 
            'green': 24    # GPIO 24 (Pin 18)
        }
        
        if self.gpio_available:
            self._setup_gpio()
            logger.info("🔴🟡🟢 GPIO LED controller initialized")
        else:
            logger.info("💡 LED controller in simulation mode (no GPIO)")
    
    def _setup_gpio(self):
        """Initialize GPIO pins for LED control"""
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            for color, pin in self.led_pins.items():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)  # Start with LEDs off
                
        except Exception as e:
            logger.error(f"GPIO setup failed: {e}")
            self.gpio_available = False

def read_barcode_from_hid(device_path, timeout=30):
    """Read barcode from HID device with proper key mapping"""
    try:
        logger.info(f"📱 Reading from HID device: {device_path}")
        logger.info("🔍 Scan a barcode now... (waiting for input)")
        
        with open(device_path, 'rb') as fp:
            barcode = ''
            shift = False
            start_time = time.time()
            
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.warning(f"⏰ HID read timeout after {timeout}s")
                    return None
                
                try:
                    buffer = fp.read(8)
                    if not buffer:
                        continue
                        
                    for b in buffer:
                        code = b if isinstance(b, int) else ord(b)
                        
                        if code == 0:
                            continue
                        
                        if code == 40:  # ENTER key - barcode complete
                            if barcode.strip():
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                logger.info(f"📦 HID Barcode scanned: {barcode} at {timestamp}")
                                return barcode.strip()
                            barcode = ''
                        elif code == 2:  # SHIFT key
                            shift = True
                        else:
                            if shift:
                                barcode += HID_KEYS_SHIFT.get(code, '')
                                shift = False
                            else:
                                barcode += HID_KEYS.get(code, '')
                                
                except Exception as read_error:
                    logger.debug(f"HID read error (continuing): {read_error}")
                    time.sleep(0.1)
                    continue
                    
    except PermissionError:
        logger.error(f"❌ Permission denied for {device_path}. Try running with sudo.")
        return None
    except Exception as e:
        logger.error(f"❌ Error reading from HID device {device_path}: {e}")
        return None

def control_led(color, duration=1.0):
    """Control LED with specified color and duration"""
    try:
        if GPIO_AVAILABLE:
            # Define GPIO pins for different colors
            LED_PINS = {
                'red': 18,
                'green': 23,
                'blue': 24,
                'yellow': 25
            }
            
            pin = LED_PINS.get(color.lower())
            if pin:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(pin, GPIO.LOW)
                GPIO.cleanup()
                logger.info(f"💡 {color.upper()} LED activated for {duration}s")
            else:
                logger.warning(f"Unknown LED color: {color}")
        else:
            # Simulate LED on non-Pi systems
            logger.info(f"💡 [SIMULATED] {color.upper()} LED for {duration}s")
    except Exception as e:
        logger.error(f"LED control error: {e}")

# ============================================================================
# SCANNER AND NETWORK FUNCTIONS
# ============================================================================

def find_usb_hid_devices():
    """Find available USB HID devices for barcode scanning"""
    hid_devices = []
    try:
        # Look for hidraw devices
        hidraw_devices = glob.glob('/dev/hidraw*')
        for device in hidraw_devices:
            try:
                # Test if device is accessible
                with open(device, 'rb') as f:
                    hid_devices.append(device)
                    logger.info(f"📱 Found HID device: {device}")
            except (PermissionError, OSError):
                logger.debug(f"Cannot access {device} (permission or device issue)")
                continue
    except Exception as e:
        logger.warning(f"Error scanning for HID devices: {e}")
    
    return hid_devices

def is_scanner_connected():
    """Check if USB barcode scanner is connected"""
    try:
        if IS_RASPBERRY_PI:
            # On Pi, check for actual USB scanner using HID devices
            hid_devices = find_usb_hid_devices()
            if hid_devices:
                logger.info(f"📱 Found {len(hid_devices)} HID device(s): {hid_devices}")
                return True
            
            # Fallback: check for input devices
            command = "grep -E -i 'scanner|barcode|keyboard' /sys/class/input/event*/device/name"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.returncode == 0 and result.stdout
        else:
            # On server, check for HID devices
            hid_devices = find_usb_hid_devices()
            return len(hid_devices) > 0
    except Exception as e:
        logger.warning(f"Scanner check failed: {e}")
        return False

def get_primary_raspberry_pi_ip():
    """
    Get the primary Raspberry Pi IP address using dynamic discovery.
    Returns the IP of the first Pi device found with web services available.
    """
    try:
        from utils.network_discovery import NetworkDiscovery
        discovery = NetworkDiscovery()
        pi_devices = discovery.discover_raspberry_pi_devices()
        
        if pi_devices:
            # Return the first Pi device with web services
            for device in pi_devices:
                if device.get('web_available'):
                    return device['ip']
            # Fallback to first device
            return pi_devices[0]['ip']
        return None
    except Exception as e:
        logger.error(f"Error discovering Pi IP: {e}")
        return None

def start_usb_hid_scanner_service(device_id=None):
    """Start USB HID scanner service with automatic barcode detection"""
    if not device_id:
        device_id = get_local_device_mac() or f"auto-device-{uuid.uuid4().hex[:8]}"
    
    logger.info("🎯 Starting USB HID Scanner Service...")
    logger.info(f"🆔 Device ID: {device_id}")
    
    # Find available HID devices
    hid_devices = find_usb_hid_devices()
    if not hid_devices:
        logger.error("❌ No USB HID devices found. Please connect your barcode scanner.")
        return False
    
    # Use the first available HID device
    scanner_device = hid_devices[0]
    logger.info(f"📱 Using HID device: {scanner_device}")
    
    # Auto-register device if needed
    try:
        local_db = get_local_storage()
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if not device_already_registered:
            logger.info("📝 Auto-registering device...")
            registration_result = confirm_registration(device_id)
            if "successfully" in registration_result.lower():
                logger.info("✅ Device auto-registered successfully")
            else:
                logger.warning(f"⚠️ Auto-registration issue: {registration_result}")
        else:
            logger.info(f"✅ Device {device_id} already registered")
    except Exception as e:
        logger.error(f"❌ Auto-registration failed: {e}")
    
    logger.info("🚀 USB HID Scanner active - scan barcodes now!")
    control_led('green', 2.0)  # Signal ready state
    
    try:
        while True:
            # Read barcode from HID device
            barcode = read_barcode_from_hid(scanner_device, timeout=60)
            
            if barcode:
                logger.info(f"📦 Barcode detected: {barcode}")
                control_led('blue', 0.5)  # Signal scan detected
                
                try:
                    # Process the barcode
                    result = process_barcode_scan(barcode, device_id)
                    logger.info(f"📊 Processing result: {result}")
                    
                    if "successfully" in str(result).lower():
                        control_led('green', 1.0)  # Success
                    else:
                        control_led('yellow', 1.0)  # Warning
                        
                except Exception as process_error:
                    logger.error(f"❌ Error processing barcode {barcode}: {process_error}")
                    control_led('red', 1.0)  # Error
            else:
                # No barcode read (timeout or error)
                logger.debug("⏰ No barcode read in timeout period, continuing...")
                
    except KeyboardInterrupt:
        logger.info("👋 USB HID Scanner service stopped by user")
        control_led('red', 0.5)  # Signal shutdown
    except Exception as e:
        logger.error(f"❌ USB HID Scanner service error: {e}")
        control_led('red', 2.0)  # Signal error
    
    logger.info("🛑 USB HID Scanner Service stopped")
    return True

def start_plug_and_play_barcode_service():
    """Start fully automated barcode scanning service without UI"""
    logger.info("🎯 Starting Plug-and-Play Barcode Service...")
    logger.info("📱 Connect your USB barcode scanner and start scanning!")

    # detect if interactive or running under systemd
    interactive = sys.stdin.isatty()
    
    if interactive:
        logger.info("📺 Interactive mode detected - console output enabled")
    else:
        logger.info("🤖 Service mode detected - running in background")
    
    # Auto-register device on startup
    device_id = get_local_device_mac() or f"auto-device-{uuid.uuid4().hex[:8]}"
    logger.info(f"🆔 Device ID: {device_id}")
    
    # Check for USB HID scanner first
    hid_devices = find_usb_hid_devices()
    if hid_devices:
        logger.info(f"📱 USB HID scanner detected, starting HID service...")
        return start_usb_hid_scanner_service(device_id)
    
    # Fallback to original service
    # Check if device is already registered
    try:
        local_db = get_local_storage()
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if not device_already_registered:
            logger.info("📝 Auto-registering device...")
            # Register device automatically
            registration_result = confirm_registration(device_id)
            if "successfully" in registration_result.lower():
                logger.info("✅ Device auto-registered successfully")
            else:
                logger.warning(f"⚠️ Auto-registration issue: {registration_result}")
        else:
            logger.info(f"✅ Device {device_id} already registered")
    except Exception as e:
        logger.error(f"❌ Auto-registration failed: {e}")
    
    # Start the main service loop
    logger.info("🚀 Barcode service active - waiting for scans...")
    
    try:
        while True:
            # In a real implementation, this would:
            # This could be:
            # 1. File-based barcode input
            # 2. Network-based barcode input
            # 3. USB scanner input via device files
            # 4. Scheduled heartbeat/status updates
            
            logger.info("📡 Daemon active - waiting for barcode input...")
            
            if interactive:
                # In interactive mode, allow manual input for testing
                try:
                    barcode = input("Enter barcode (or 'quit' to exit): ").strip()
                    if barcode.lower() == 'quit':
                        break
                    if barcode:
                        result = process_barcode_scan(barcode, device_id)
                        logger.info(f"📊 Scan result: {result}")
                except (EOFError, KeyboardInterrupt):
                    logger.info("👋 Service interrupted by user")
                    break
            else:
                # In service mode, just sleep and wait for external triggers
                time.sleep(60)  # Check every minute
                
    except KeyboardInterrupt:
        logger.info("👋 Barcode service stopped by user")
    except Exception as e:
        logger.error(f"❌ Service error: {e}")
    
    logger.info("🛑 Plug-and-Play Barcode Service stopped")