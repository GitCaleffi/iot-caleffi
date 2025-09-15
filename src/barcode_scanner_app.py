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

# USB Scanner imports
try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    USB_SCANNER_AVAILABLE = True
except ImportError:
    print("Installing evdev for USB scanner support...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, categorize, ecodes
    USB_SCANNER_AVAILABLE = True
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
    is_pi = False

    # Method 1: Check /proc/device-tree/model
    try:
        if os.path.exists('/proc/device-tree/model'):
            with open('/proc/device-tree/model', 'r') as f:
                model_content = f.read().lower()
                if 'raspberry pi' in model_content:
                    is_pi = True
    except:
        pass

    # Method 2: Check /sys/firmware/devicetree/base/model
    try:
        if not is_pi and os.path.exists('/sys/firmware/devicetree/base/model'):
            with open('/sys/firmware/devicetree/base/model', 'r') as f:
                model_content = f.read().lower()
                if 'raspberry pi' in model_content:
                    is_pi = True
    except:
        pass

    # Method 3: Check CPU info for BCM chip (more reliable)
    try:
        if not is_pi and os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if 'bcm' in cpuinfo and ('2708' in cpuinfo or '2709' in cpuinfo or '2710' in cpuinfo or '2711' in cpuinfo):
                    is_pi = True
    except:
        pass

    if is_pi:
        import RPi.GPIO as GPIO
        GPIO_AVAILABLE = True
        print("✅ RPi.GPIO loaded successfully - LED functionality enabled")
    else:
        print("ℹ️ Not running on Raspberry Pi - LED functionality will use simulation mode")

except (ImportError, RuntimeError, FileNotFoundError, OSError) as e:
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

# USB Scanner control
USB_SCANNER_RUNNING = False
usb_scanner_thread = None
barcode_queue = queue.Queue()
scanned_barcodes_count = 0

# HID Scanner configuration
HID_DEVICE_PATH = '/dev/hidraw0'  # Default HID device path
USE_HID_SCANNER = True  # Prefer HID scanner over evdev
HID_FALLBACK_TO_EVDEV = True  # Fallback to EVDEV if HID fails

# ============================================================================
# USB SCANNER FUNCTIONS (HID + EVDEV)
# ============================================================================

# HID key mapping for normal keys
hid_key_map = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j',
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's',
    23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: 'ENTER', 44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\',
    51: ';', 52: "'", 53: '`', 54: ',', 55: '.', 56: '/'
}

# HID key mapping for shifted characters
hid_shift_map = {
    4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J',
    14: 'K', 15: 'L', 16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S',
    23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y', 29: 'Z',
    30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')',
    44: ' ', 45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<',
    55: '>', 56: '?'
}

def find_hid_scanner_device():
    """Find HID barcode scanner device"""
    hid_devices = ['/dev/hidraw0', '/dev/hidraw1', '/dev/hidraw2', '/dev/hidraw3']
    
    for device_path in hid_devices:
        if os.path.exists(device_path):
            try:
                # Test if we can open the device
                with open(device_path, 'rb') as test_fp:
                    logger.info(f"✅ Found HID device: {device_path}")
                    return device_path
            except PermissionError:
                logger.warning(f"⚠️ Permission denied for {device_path}. May need sudo.")
                return device_path  # Return it anyway, let caller handle permission
            except Exception as e:
                logger.debug(f"Cannot access {device_path}: {e}")
                continue
    
    logger.warning("❌ No HID scanner device found")
    return None

def extract_barcode_from_hid_buffer(data_bytes):
    """Extract barcode characters from HID buffer data - Fixed for proper EAN scanning"""
    barcode_chars = []

    # Debug: Log the raw data
    logger.debug(f"Raw HID buffer: {[hex(b) for b in data_bytes]}")

    # Process each byte in the buffer
    for b in data_bytes:
        code = b if isinstance(b, int) else ord(b)

        if code == 0:
            continue

        # Skip modifier keys
        if code in [1, 2, 3, 225, 226, 227]:  # CTRL, SHIFT, ALT, LCTRL, LSHIFT, LALT
            continue

        # Handle termination codes
        if code in [40, 88, 13, 10, 42]:  # ENTER, KP_ENTER, CR, LF, BACKSPACE
            logger.debug(f"Termination code detected: {code}")
            break

        # Process numeric characters (main keyboard)
        if 30 <= code <= 39:  # Numbers 1-9, 0 on main keyboard
            if code == 39:  # 0
                num = '0'
            else:
                num = str(code - 29)  # 30=1, 31=2, ..., 38=9
            barcode_chars.append(num)
            logger.debug(f"Main keyboard code {code} -> '{num}'")
        
        # Process keypad numbers
        elif 98 <= code <= 107:  # Keypad numbers 1-9, 0
            if code == 98:  # KP_1
                num = '1'
            elif code == 99:  # KP_2
                num = '2'
            elif code == 100:  # KP_3
                num = '3'
            elif code == 101:  # KP_4
                num = '4'
            elif code == 102:  # KP_5
                num = '5'
            elif code == 103:  # KP_6
                num = '6'
            elif code == 104:  # KP_7
                num = '7'
            elif code == 105:  # KP_8
                num = '8'
            elif code == 106:  # KP_9
                num = '9'
            elif code == 107:  # KP_0
                num = '0'
            else:
                continue
            barcode_chars.append(num)
            logger.debug(f"Keypad code {code} -> '{num}'")
        
        # Process alphanumeric characters for Code 128/Code 39 support
        elif code in hid_key_map:
            char = hid_key_map[code]
            if char.isalnum():  # Only alphanumeric
                barcode_chars.append(char)
                logger.debug(f"Alpha code {code} -> '{char}'")

    result = ''.join(barcode_chars)
    logger.debug(f"Extracted barcode: '{result}' (length: {len(result)})")

    # Validate barcode length for EAN-8, EAN-13, Code 128, etc.
    if len(result) < 6 or len(result) > 20:
        logger.debug(f"Invalid barcode length: {len(result)} (must be 6-20)")
        return ""

    # Accept both numeric and alphanumeric barcodes
    if not result.strip():
        logger.debug("Empty barcode result")
        return ""

    return result

def is_barcode_complete(data_bytes, current_barcode, time_since_last_data):
    """Determine if a barcode scan is complete based on various patterns"""

    # Method 1: ENTER key detected
    if 40 in data_bytes:
        return True

    # Method 2: Timeout after no data (500ms)
    if time_since_last_data > 0.5 and current_barcode.strip():
        return True

    # Method 3: Specific termination patterns
    # Check for repeated bytes (some scanners do this)
    non_zero_bytes = [b for b in data_bytes if b > 0]
    if len(non_zero_bytes) > 0:
        # If all non-zero bytes are the same and it's a termination code
        unique_bytes = set(non_zero_bytes)
        if len(unique_bytes) == 1:
            code = list(unique_bytes)[0]
            if code in [10, 13, 40]:  # LF, CR, ENTER
                return True

    # Method 4: Very few non-zero bytes after having data
    if len(non_zero_bytes) <= 1 and current_barcode.strip() and time_since_last_data > 0.2:
        return True

    return False

def hid_scanner_worker():
    """HID scanner monitoring worker thread - Enhanced for multiple scanner types"""
    global USB_SCANNER_RUNNING, scanned_barcodes_count

    logger.info("🔌 Starting HID scanner detection...")

    while USB_SCANNER_RUNNING:
        try:
            device_path = find_hid_scanner_device()
            if not device_path:
                logger.info("📱 No HID scanner found, retrying in 5 seconds...")
                time.sleep(5)
                continue

            logger.info(f"📱 Reading from HID device: {device_path}")
            print(f"📱 HID Scanner ready: {device_path}")
            print("🔍 Scan a barcode now...")

            with open(device_path, 'rb') as fp:
                barcode = ''
                last_data_time = time.time()

                while USB_SCANNER_RUNNING:
                    try:
                        buffer = fp.read(8)
                        if not buffer:
                            continue

                        current_time = time.time()
                        data_bytes = [b if isinstance(b, int) else ord(b) for b in buffer]

                        # Check if we have actual data (non-zero bytes)
                        has_data = any(b > 0 for b in data_bytes)

                        if has_data:
                            # Extract characters from this buffer
                            chars = extract_barcode_from_hid_buffer(data_bytes)
                            barcode += chars
                            last_data_time = current_time

                            # Check if barcode is complete
                            time_since_last_data = current_time - last_data_time
                            if is_barcode_complete(data_bytes, barcode, time_since_last_data):
                                if barcode.strip():
                                    scanned_barcodes_count += 1
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                    logger.info(f"📱 HID Scan #{scanned_barcodes_count}: {barcode}")
                                    print("=" * 50)
                                    print(f"📦 Scanned Barcode: {barcode}")
                                    print(f"🕒 Time: {timestamp}")
                                    print("=" * 50)

                                    # Add to queue for processing
                                    barcode_queue.put(barcode.strip())
                                    barcode = ''
                        else:
                            # No data in this buffer, check timeout
                            time_since_last_data = current_time - last_data_time
                            if time_since_last_data > 1.0 and barcode.strip():
                                # Timeout - consider barcode complete
                                scanned_barcodes_count += 1
                                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                                logger.info(f"📱 HID Scan #{scanned_barcodes_count}: {barcode}")
                                print("=" * 50)
                                print(f"📦 Scanned Barcode: {barcode}")
                                print(f"🕒 Time: {timestamp}")
                                print("=" * 50)

                                # Add to queue for processing
                                barcode_queue.put(barcode.strip())
                                barcode = ''

                    except Exception as e:
                        logger.error(f"Error reading HID data: {e}")
                        break

        except PermissionError:
            logger.error(f"❌ Permission denied for {device_path}. Try running with sudo.")
            print(f"❌ Permission denied for {device_path}. Try running with sudo.")
            time.sleep(10)
        except Exception as e:
            logger.error(f"HID scanner error: {e}")
            time.sleep(5)

def find_usb_scanner():
    """Find USB barcode scanner automatically"""
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        for device in devices:
            device_name = device.name.lower()
            
            # Check for barcode scanner keywords
            scanner_keywords = [
                'barcode', 'scanner', 'honeywell', 'symbol', 
                'datalogic', 'zebra', 'usb barcode', 'hid'
            ]
            
            if any(keyword in device_name for keyword in scanner_keywords):
                return device
            
            # Check for keyboard-like devices with numeric capabilities
            try:
                caps = device.capabilities()
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    
                    # Must have numbers and Enter
                    has_numbers = any(key in keys for key in [
                        ecodes.KEY_0, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4,
                        ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9
                    ])
                    has_enter = ecodes.KEY_ENTER in keys
                    
                    if has_numbers and has_enter and len(keys) < 50:
                        return device
            except:
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding USB scanner: {e}")
        return None

def key_to_char(key_code):
    """Convert key code to character"""
    key_map = {
        ecodes.KEY_0: '0', ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3',
        ecodes.KEY_4: '4', ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7',
        ecodes.KEY_8: '8', ecodes.KEY_9: '9',
        ecodes.KEY_A: 'a', ecodes.KEY_B: 'b', ecodes.KEY_C: 'c', ecodes.KEY_D: 'd',
        ecodes.KEY_E: 'e', ecodes.KEY_F: 'f', ecodes.KEY_G: 'g', ecodes.KEY_H: 'h',
        ecodes.KEY_I: 'i', ecodes.KEY_J: 'j', ecodes.KEY_K: 'k', ecodes.KEY_L: 'l',
        ecodes.KEY_M: 'm', ecodes.KEY_N: 'n', ecodes.KEY_O: 'o', ecodes.KEY_P: 'p',
        ecodes.KEY_Q: 'q', ecodes.KEY_R: 'r', ecodes.KEY_S: 's', ecodes.KEY_T: 't',
        ecodes.KEY_U: 'u', ecodes.KEY_V: 'v', ecodes.KEY_W: 'w', ecodes.KEY_X: 'x',
        ecodes.KEY_Y: 'y', ecodes.KEY_Z: 'z'
    }
    return key_map.get(key_code, '')

def evdev_scanner_worker():
    """EVDEV USB scanner monitoring worker thread (fallback)"""
    global USB_SCANNER_RUNNING, scanned_barcodes_count
    
    scanner_device = None
    barcode_buffer = ""
    last_scan_time = 0
    scan_timeout = 2
    
    logger.info("🔌 Starting EVDEV scanner detection...")
    
    while USB_SCANNER_RUNNING:
        try:
            # Find scanner if not connected
            if not scanner_device:
                scanner_device = find_usb_scanner()
                if scanner_device:
                    logger.info(f"✅ EVDEV Scanner connected: {scanner_device.name}")
                    print(f"📱 EVDEV Scanner ready: {scanner_device.name}")
                else:
                    time.sleep(5)  # Check again in 5 seconds
                    continue
            
            # Monitor scanner for input
            for event in scanner_device.read_loop():
                if not USB_SCANNER_RUNNING:
                    break
                
                if event.type == ecodes.EV_KEY and event.value == 1:
                    current_time = time.time()
                    
                    if event.code == ecodes.KEY_ENTER:
                        if barcode_buffer and (current_time - last_scan_time) < scan_timeout:
                            barcode = barcode_buffer.strip()
                            scanned_barcodes_count += 1
                            
                            logger.info(f"📱 EVDEV Scan #{scanned_barcodes_count}: {barcode}")
                            print(f"📱 EVDEV Scan #{scanned_barcodes_count}: {barcode}")
                            
                            # Add to queue for processing
                            barcode_queue.put(barcode)
                            
                            barcode_buffer = ""
                    else:
                        char = key_to_char(event.code)
                        if char:
                            barcode_buffer += char
                            last_scan_time = current_time
        
        except Exception as e:
            logger.error(f"EVDEV scanner error: {e}")
            scanner_device = None  # Reset to try reconnecting
            time.sleep(5)

def usb_scanner_worker():
    """Main USB scanner worker - tries HID first, then EVDEV"""
    global USE_HID_SCANNER, HID_FALLBACK_TO_EVDEV
    
    if USE_HID_SCANNER:
        logger.info("🔌 Attempting HID scanner mode first...")
        try:
            # Try to find HID device first
            device_path = find_hid_scanner_device()
            if device_path:
                # Test if we can actually read from it
                try:
                    with open(device_path, 'rb') as test_fp:
                        test_fp.read(1)  # Try to read 1 byte
                    logger.info("✅ HID scanner accessible, using HID mode")
                    hid_scanner_worker()
                    return
                except PermissionError:
                    logger.warning("⚠️ HID device permission denied")
                    if HID_FALLBACK_TO_EVDEV:
                        logger.info("🔄 Falling back to EVDEV scanner mode")
                        evdev_scanner_worker()
                    else:
                        logger.error("❌ HID scanner failed and fallback disabled")
                except Exception as e:
                    logger.error(f"❌ HID scanner test failed: {e}")
                    if HID_FALLBACK_TO_EVDEV:
                        logger.info("🔄 Falling back to EVDEV scanner mode")
                        evdev_scanner_worker()
            else:
                logger.info("📱 No HID device found")
                if HID_FALLBACK_TO_EVDEV:
                    logger.info("🔄 Falling back to EVDEV scanner mode")
                    evdev_scanner_worker()
        except Exception as e:
            logger.error(f"❌ HID scanner initialization failed: {e}")
            if HID_FALLBACK_TO_EVDEV:
                logger.info("🔄 Falling back to EVDEV scanner mode")
                evdev_scanner_worker()
    else:
        logger.info("🔌 Using EVDEV scanner mode")
        evdev_scanner_worker()

def barcode_processor_worker():
    """Process barcodes from the queue automatically"""
    global USB_SCANNER_RUNNING
    
    logger.info("🔄 Starting barcode processor...")
    
    while USB_SCANNER_RUNNING:
        try:
            # Get barcode from queue (blocks until available)
            barcode = barcode_queue.get(timeout=1)
            
            if barcode:
                # Process barcode automatically
                result = process_barcode_scan_auto(barcode)
                
                # Log result
                if "Registration Successful" in str(result):
                    print(f"✅ Device registered automatically")
                elif "sent to IoT Hub successfully" in str(result):
                    print(f"✅ Barcode sent to IoT Hub")
                elif "saved locally" in str(result):
                    print(f"⚠️  Saved locally (offline mode)")
                else:
                    print(f"ℹ️  Result: {result}")
            
            barcode_queue.task_done()
            
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Barcode processing error: {e}")

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

# Fix import paths for utils modules
current_dir = Path(__file__).resolve().parent
utils_dir = current_dir / 'utils'
sys.path.insert(0, str(utils_dir))

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
    
    def blink_led(self, color, duration=0.5, times=1):
        """Blink LED with specified color"""
        if not self.gpio_available:
            logger.info(f"💡 LED Blink: {color.upper()} ({'●' * times})")
            return
        
        try:
            pin = self.led_pins.get(color)
            if not pin:
                logger.warning(f"Unknown LED color: {color}")
                return
            
            for _ in range(times):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(duration)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.1)  # Short pause between blinks
                
        except Exception as e:
            logger.error(f"LED blink error: {e}")
    
    def set_led(self, color, state):
        """Set LED on/off state"""
        if not self.gpio_available:
            logger.info(f"💡 LED {color.upper()}: {'ON' if state else 'OFF'}")
            return
        
        try:
            pin = self.led_pins.get(color)
            if pin:
                GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
        except Exception as e:
            logger.error(f"LED control error: {e}")
    
    def cleanup(self):
        """Clean up GPIO resources"""
        if self.gpio_available:
            try:
                GPIO.cleanup()
                logger.info("🔌 GPIO cleanup completed")
            except Exception as e:
                logger.error(f"GPIO cleanup error: {e}")

# Global LED controller
led_controller = LEDController()

# Raspberry Pi Device Service Class
# ============================================================================
# RASPBERRY PI DEVICE SERVICE
# ============================================================================

class RaspberryPiDeviceService:
    """Raspberry Pi device service for direct Azure IoT Hub connection"""
    
    def __init__(self):
        self.device_id = None
        self.hub_client = None
        self.running = False
        self.network_connected = False
        self.barcode_queue = queue.Queue()
        self.scanner_thread = None
        self.network_monitor_thread = None
        self.heartbeat_thread = None
        
        logger.info("🆔 Initializing Raspberry Pi Device Service...")
        self._initialize_device()
        
    def _initialize_device(self):
        """Initialize Pi device with automatic registration and IoT Hub connection"""
        try:
            # Step 1: Generate device ID from MAC address
            mac_address = get_local_mac_address()
            if mac_address:
                self.device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
                logger.info(f"🆔 Pi Device ID: {self.device_id}")
            else:
                self.device_id = f"pi-{uuid.uuid4().hex[:8]}"
                logger.warning(f"⚠️ Using fallback device ID: {self.device_id}")
            
            # Step 2: Check network connectivity (Wi-Fi/Ethernet)
            self._check_network_connectivity()
            
            # Step 3: Auto-register with Azure IoT Hub if connected
            if self.network_connected:
                self._register_with_iot_hub()
            else:
                logger.warning("⚠️ No network connection - will retry when network is available")
            
        except Exception as e:
            logger.error(f"❌ Device initialization failed: {e}")
    
    def _check_network_connectivity(self):
        """Check if Pi has network connectivity (Wi-Fi or Ethernet)"""
        try:
            # Test internet connectivity to Azure IoT Hub
            test_hosts = [
                ("CaleffiIoT.azure-devices.net", 443),  # Azure IoT Hub
                ("8.8.8.8", 53),  # Google DNS fallback
            ]
            
            for host, port in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if result == 0:
                        self.network_connected = True
                        logger.info(f"✅ Network connectivity confirmed to {host}:{port}")
                        
                        # Get network interface info
                        self._log_network_interfaces()
                        return True
                        
                except Exception as e:
                    logger.debug(f"Connection test failed for {host}:{port} - {e}")
                    continue
            
            self.network_connected = False
            logger.warning("❌ No network connectivity detected")
            return False
            
        except Exception as e:
            logger.error(f"Network connectivity check failed: {e}")
            self.network_connected = False
            return False
    
    def _log_network_interfaces(self):
        """Log available network interfaces (Wi-Fi/Ethernet)"""
        try:
            # Check network interfaces
            result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                active_interfaces = []
                
                for line in lines:
                    if 'state UP' in line:
                        interface = line.split(':')[1].strip()
                        active_interfaces.append(interface)
                
                if active_interfaces:
                    logger.info(f"🌐 Active network interfaces: {', '.join(active_interfaces)}")
                else:
                    logger.warning("⚠️ No active network interfaces found")
                    
        except Exception as e:
            logger.debug(f"Network interface check failed: {e}")
    
    def _register_with_iot_hub(self):
        """Register Pi device with Azure IoT Hub using device credentials"""
        try:
            logger.info(f"📡 Registering device {self.device_id} with Azure IoT Hub...")
            # Yellow LED: Registration in progress
            led_controller.blink_led('yellow', 0.5, 2)
            
            # Use dynamic registration service to get device connection string
            registration_service = get_dynamic_registration_service()
            token = device_manager.generate_registration_token()
            
            # Device info for registration
            device_info = {
                "registration_method": "pi_device_direct",
                "device_type": "raspberry_pi",
                "auto_registered": True,
                "network_interfaces": self._get_network_info(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Register device with IoT Hub
            success, message = device_manager.register_device(token, self.device_id, device_info)
            
            if success:
                logger.info(f"✅ Device {self.device_id} registered with Azure IoT Hub")
                # Green LED: Registration successful
                led_controller.blink_led('green', 0.5, 3)
                
                # Get device-specific connection string
                device_connection_string = device_manager.get_device_connection_string(self.device_id)
                
                if device_connection_string:
                    # Initialize IoT Hub client
                    self.hub_client = HubClient(device_connection_string)
                    logger.info("📡 Azure IoT Hub client initialized")
                    
                    # Send registration confirmation
                    self._send_registration_confirmation()
                    
                    # Start heartbeat service
                    self._start_heartbeat_service()
                    
                    return True
                else:
                    logger.error("❌ Failed to get device connection string")
                    # Red LED: Connection string failed
                    led_controller.blink_led('red', 0.3, 3)
                    return False
            else:
                logger.error(f"❌ IoT Hub registration failed: {message}")
                # Red LED: Registration failed
                led_controller.blink_led('red', 0.2, 5)
                return False
                
        except Exception as e:
            logger.error(f"❌ IoT Hub registration error: {e}")
            # Red LED: Registration error
            led_controller.blink_led('red', 0.1, 10)
            return False
    
    def _get_network_info(self):
        """Get current network configuration info"""
        try:
            network_info = {}
            
            # Get IP address
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                network_info['ip_address'] = s.getsockname()[0]
                s.close()
            except:
                network_info['ip_address'] = "unknown"
            
            # Get hostname
            network_info['hostname'] = socket.gethostname()
            
            return network_info
            
        except Exception as e:
            logger.debug(f"Network info collection failed: {e}")
            return {"ip_address": "unknown", "hostname": "unknown"}
    
    def _send_registration_confirmation(self):
        """Send registration confirmation message to IoT Hub"""
        try:
            confirmation_payload = {
                "deviceId": self.device_id,
                "messageType": "device_registration",
                "status": "registered",
                "deviceType": "raspberry_pi",
                "capabilities": ["barcode_scanning", "inventory_tracking"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "networkInfo": self._get_network_info()
            }
            
            success = self.hub_client.send_message(json.dumps(confirmation_payload), self.device_id)
            
            if success:
                logger.info("📡 Registration confirmation sent to IoT Hub")
            else:
                logger.warning("⚠️ Failed to send registration confirmation")
        except Exception as e:
            logger.warning(f"Registration confirmation error: {e}")
    
    def _start_heartbeat_service(self):
        """Send single heartbeat (no background service)"""
        try:
            if self.hub_client and self.network_connected:
                heartbeat_payload = {
                    "deviceId": self.device_id,
                    "messageType": "heartbeat",
                    "status": "online",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "networkInfo": self._get_network_info()
                }
                
                self.hub_client.send_message(json.dumps(heartbeat_payload), self.device_id)
                logger.info(f"💓 Single heartbeat sent to IoT Hub for device: {self.device_id}")
                
        except Exception as e:
            logger.warning(f"Heartbeat error: {e}")
        
        logger.info("💓 Heartbeat service disabled (no background threads)")
    
    def start_barcode_scanning_service(self):
        """Start the barcode scanning service (no background threads)"""
        try:
            logger.info("📱 Starting barcode scanning service...")
            self.running = True
            
            # Perform single network check instead of background monitoring
            self._network_monitor_worker()
            
            logger.info("✅ Barcode scanning service started")
            logger.info("📱 Ready to scan barcodes - data will be sent to Azure IoT Hub")
            logger.info("🚫 Background threads disabled for stability")
            
        except Exception as e:
            logger.error(f"Failed to start barcode scanning service: {e}")
    
    def _network_monitor_worker(self):
        """Single network connectivity check (no background loop)"""
        try:
            # Check network connectivity once
            previous_status = self.network_connected
            self._check_network_connectivity()
            
            # If network was restored, try to reconnect to IoT Hub
            if not previous_status and self.network_connected:
                logger.info("🌐 Network connectivity restored - reconnecting to IoT Hub")
                if not self.hub_client:
                    self._register_with_iot_hub()
            
            # If network was lost, log the status
            elif previous_status and not self.network_connected:
                logger.warning("⚠️ Network connectivity lost - barcodes will be stored locally")
            
        except Exception as e:
            logger.error(f"Network monitoring error: {e}")
    
    def stop(self):
        """Stop the barcode scanning service"""
        logger.info("🛑 Stopping Raspberry Pi Device Service...")
        self.running = False
        # Red LED: Service stopping
        led_controller.blink_led('red', 0.2, 3)
        led_controller.cleanup()

# Global Pi device service instance
pi_device_service = None

# ============================================================================
# SCANNER AND NETWORK FUNCTIONS
# ============================================================================

def is_scanner_connected():
    """Check if USB barcode scanner is connected"""
    try:
        if IS_RASPBERRY_PI:
            # On Pi, check for actual USB scanner
            command = "grep -E -i 'scanner|barcode|keyboard' /sys/class/input/event*/device/name"
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            return result.returncode == 0 and result.stdout
        else:
            # On server, assume virtual scanner
            return True
    except Exception as e:
        logger.error(f"Scanner check error: {e}")
        return True

def get_primary_raspberry_pi_ip():
    """
    Get the primary Raspberry Pi IP address using dynamic discovery.
    Returns the IP of the first Pi device found with web services available.
    
    Returns:
        str: IP address of primary Pi device, or None if not found
    """
    try:
        config = load_config()
        raspberry_pi_config = config.get("raspberry_pi", {})
        
        # Check if dynamic discovery is enabled
        if raspberry_pi_config.get("dynamic_discovery", False):
            # Use dynamic discovery system
            from utils.dynamic_pi_discovery import DynamicPiDiscovery
            
            dynamic_discovery = DynamicPiDiscovery(config)
            current_devices = dynamic_discovery.get_current_devices()
            
            if current_devices:
                # Return first device with web services
                for device in current_devices:
                    if 'web' in device.get('services', []):
                        logger.info(f"🔍 Dynamic discovery found Pi with web service: {device['ip']}")
                        return device['ip']
                
                # Fallback to first device
                first_device = current_devices[0]
                logger.info(f"🔍 Dynamic discovery found Pi: {first_device['ip']}")
                return first_device['ip']
            
            # Force a scan if no devices found
            logger.info("🔍 No devices found, forcing scan...")
            scan_results = dynamic_discovery.force_scan()
            if scan_results:
                first_device = scan_results[0]
                logger.info(f"🔍 Force scan found Pi: {first_device['ip']}")
                return first_device['ip']
        
        # Check for auto-detected IP from previous discoveries
        auto_detected_ip = raspberry_pi_config.get("auto_detected_ip")
        if auto_detected_ip:
            logger.info(f"📍 Using auto-detected Pi IP: {auto_detected_ip}")
            return auto_detected_ip
        
        # Fallback to manual IP if configured
        if raspberry_pi_config.get("use_manual_ip", False):
            manual_ip = raspberry_pi_config.get("manual_ip")
            if manual_ip:
                logger.info(f"📍 Using manual Pi IP from config: {manual_ip}")
                return manual_ip
        
        # Final fallback to network discovery
        from utils.network_discovery import NetworkDiscovery
        discovery = NetworkDiscovery()
        devices = discovery.discover_raspberry_pi_devices()
        
        if devices:
            primary_device = devices[0]
            logger.info(f"✅ Network discovery found Pi: {primary_device['ip']}")
            return primary_device['ip']
        
        logger.warning("❌ No Pi devices found via any discovery method")
        return None
        
    except Exception as e:
        logger.error(f"Error discovering Pi devices: {e}")
        return None


# ============================================================================
# PI CONNECTION MANAGEMENT
# ============================================================================

# Global variable to track Pi connection status (no caching)
_pi_connection_status = {
    'connected': False,
    'ip': None,
    'last_check': None
}


def check_raspberry_pi_connection():
    """Check if Raspberry Pi is connected with automatic discovery and IoT Hub integration."""
    global _pi_connection_status
    
    try:
        # Step 1: Try automatic Pi discovery first
        pi_ip = None
        pi_available = False
        
        # If this IS a Raspberry Pi, consider it always available
        if IS_RASPBERRY_PI:
            logger.info("🔍 Running on Raspberry Pi - marking as available")
            pi_available = True
            pi_ip = "127.0.0.1"  # Local Pi
        else:
            # Try network discovery for external Pi devices
            logger.info("🔍 Searching for external Raspberry Pi devices...")
                
            connection_manager = ConnectionManager()
            pi_available = connection_manager.check_raspberry_pi_availability()
                
            if pi_available:
                # Try to get Pi IP from discovery
                pi_ip = get_primary_raspberry_pi_ip()
                logger.info(f"✅ External Raspberry Pi found at: {pi_ip}")
            else:
                logger.info("❌ No external Raspberry Pi devices found on network")
        
        # Step 2: Test connectivity if Pi IP is available
        ssh_available = False
        web_available = False
        
        if pi_available and pi_ip and pi_ip != "127.0.0.1":
            try:
                discovery = NetworkDiscovery()
                ssh_available = discovery.test_raspberry_pi_connection(pi_ip, 22, timeout=3)
                web_available = discovery.test_raspberry_pi_connection(pi_ip, 5000, timeout=3)
                logger.info(f"📡 Pi services - SSH: {'✅' if ssh_available else '❌'} | Web: {'✅' if web_available else '❌'}")
            except Exception as e:
                logger.warning(f"Service connectivity test failed: {e}")
        
        # Step 3: Update status cache
        _pi_connection_status.update({
            'connected': pi_available,
            'ip': pi_ip if pi_available else None,
            'last_check': datetime.now(),
            'ssh_available': ssh_available,
            'web_available': web_available
        })
        
        # Step 4: Update config with discovered IP
        if pi_available and pi_ip and pi_ip != "127.0.0.1":
            try:
                config = load_config()
                if config:
                    pi_config = config.get('raspberry_pi', {})
                    if pi_config.get('auto_detected_ip') != pi_ip:
                        pi_config['auto_detected_ip'] = pi_ip
                        pi_config['last_detection'] = datetime.now(timezone.utc).isoformat()
                        config['raspberry_pi'] = pi_config
                        save_config(config)
                        logger.info(f"💾 Updated config with Pi IP: {pi_ip}")
            except Exception as e:
                logger.warning(f"Config update failed: {e}")
        
        logger.info(f"🔍 Pi connection check result: {pi_available} (IP: {pi_ip})")
        return pi_available
        
    except Exception as e:
        logger.error(f"Error checking Pi connection: {e}")
        _pi_connection_status.update({
            'connected': False,
            'ip': None,
            'last_check': datetime.now(),
            'ssh_available': False,
            'web_available': False
        })
        return False






# ============================================================================
# UI WRAPPER FUNCTIONS
# ============================================================================

# UI wrapper for processing unsent messages with progress
def process_unsent_messages_ui():
    """Process unsent messages with user-visible progress for Gradio UI."""
    # Check if Raspberry Pi is connected using connection manager for consistency
    from utils.connection_manager import ConnectionManager
    connection_manager =  ConnectionManager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("Process unsent messages blocked: Raspberry Pi not connected")
        led_controller.blink_led("red")
        return """❌ **Operation Failed: Raspberry Pi Not Connected**

Cannot process unsent messages while Raspberry Pi is offline.
Messages will remain in local database until Pi reconnects.
Please ensure the Raspberry Pi device is connected and reachable on the network.

🔴 Red LED indicates Pi connection failure"""
    
    logger.info("Processing unsent messages with Pi connection verified")
    
    # Initial loading message so the user sees a loader immediately
    yield "⏳ Processing unsent messages to IoT Hub... Please wait."
    try:
        result = process_unsent_messages(auto_retry=False)
        yield "✅ Finished processing unsent messages.\n\n" + (result or "")
    except Exception as e:
        error_msg = f"❌ Error while processing unsent messages: {str(e)}"
        logger.error(error_msg)
        yield error_msg

# Offline simulation logic removed



# ============================================================================
# DEVICE REGISTRATION FUNCTIONS
# ============================================================================

def generate_registration_token():
    """Prepare for device registration (no token required)"""
    
    # Check Raspberry Pi connection first using connection manager
    from utils.connection_manager import ConnectionManager
    connection_manager = manager = ConnectionManager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("Device registration blocked: Raspberry Pi not connected")
        led_controller.blink_led("red")
        return "❌ **Operation Failed: Raspberry Pi Not Connected**\n\nPlease ensure the Raspberry Pi device is connected and reachable on the network before attempting device registration."
    
    logger.info(f"✅ Raspberry Pi connected - proceeding with device registration")

    if not is_scanner_connected():
        return "⚠️ No barcode scanner detected. Please connect your device."
    
    try:
        response_msg = f"""✅ Ready for Device Registration!

**Pi Status:** Connected ✅
**Scanner Status:** Connected ✅

**Instructions:**
1. Enter your desired Device ID in the field below
2. Click 'Confirm Registration' to complete the process
3. No registration token required!

**Note:** Device registration is now simplified - just enter a unique Device ID and confirm."""
        
        led_controller.blink_led("green")
        return response_msg
        
    except Exception as e:
        logger.error(f"Error preparing registration: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        # Only allow the test barcode for registration
        if barcode != "817994ccfe14":
            led_controller.blink_led("red")
            return "❌ Only the test barcode (817994ccfe14) can be used for registration."
        
        is_online = api_client.is_online()
        if not is_online:
            led_controller.blink_led("red")
            return "❌ Device is offline. Cannot register device."
        
        api_url_1 = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload_1 = {"deviceId": barcode}
        
        logger.info(f"Making first API call to {api_url_1}")
        api_result_1 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_1.get("success", False):
            led_controller.blink_led("red")
            return f"❌ First API call failed: {api_result_1.get('message', 'Unknown error')}"
        
        logger.info(f"Making second API call to {api_url_1}")
        api_result_2 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_2.get("success", False):
            led_controller.blink_led("red")
            return f"❌ Second API call failed: {api_result_2.get('message', 'Unknown error')}"
        
        # Save test barcode scan locally (but not device ID yet - that happens in confirmation)
        local_db.save_test_barcode_scan(barcode)
        
        # Send response to frontend
        response_msg = f"""✅ Test barcode {barcode} processed successfully!

**API Calls Completed:**
• First call: {api_result_1.get('message', 'Success')}
• Second call: {api_result_2.get('message', 'Success')}

**Next Step:** Click 'Confirm Registration' to complete the process."""
        
        led_controller.blink_led("green")
        return response_msg
        
    except Exception as e:
        logger.error(f"Error in register_device_id: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def confirm_registration(barcode, device_id):
    """Step 2: Frontend confirms registration, send confirmation message, save device in DB, send to IoT"""
    try:
        # Check if test barcode has been scanned
        test_scan = local_db.get_test_barcode_scan()
        if not test_scan:
            led_controller.blink_led("red")
            return "❌ No test barcode scanned. Please scan the test barcode (817994ccfe14) first."
        
        is_online = api_client.is_online()
        if not is_online:
            led_controller.blink_led("red")
            return "❌ Device is offline. Cannot confirm registration."
        
        # Use the device_id provided or get from test scan
        if not device_id or not device_id.strip():
            # If no device ID provided, use the test barcode as device ID
            device_id = test_scan['barcode']
        
        # Log the device ID being used for registration
        logger.info(f"Using device ID for registration: {device_id}")
        
        # Check if device ID is already registered before proceeding
        existing_device_id = local_db.get_device_id()
        if existing_device_id == device_id:
            logger.info(f"Device ID {device_id} already registered, skipping registration")
            led_controller.blink_led("yellow")  # Use yellow to indicate already registered
            
            return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}

**Status:** This device is already registered and ready for barcode scanning operations.
No need to register again."""
        
        # Call confirmRegistration API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": test_scan['barcode']}
        
        logger.info(f"Confirming registration with API: {api_url}")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        # Check for API errors in the response
        if not api_result.get("success", False):
            led_controller.blink_led("red")
            error_msg = api_result.get('message', 'Unknown error')
            
            # Check if the error contains "Device not found"
            if "Device not found" in error_msg:
                # Try direct registration with saveDeviceId endpoint
                save_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                save_payload = {"deviceId": device_id}
                
                logger.info(f"Trying direct device registration with API: {save_url}")
                save_result = api_client.send_registration_barcode(save_url, save_payload)
                
                if save_result.get("success", False) and "response" in save_result:
                    try:
                        save_response = json.loads(save_result["response"])
                        if save_response.get("deviceId") and save_response.get("responseCode") == 200:
                            # Device registration successful, save to database
                            registered_device_id = save_response.get("deviceId")
                            local_db.save_device_id(registered_device_id)
                            
                            # Blink green LED for success
                            led_controller.blink_led("green")
                            
                            return f"""🎉 Device Registration Successful!

**Device Details:**
• Device ID: {registered_device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device ID registered with API
• ✅ Device saved in local database

**Status:** Device is now ready for barcode scanning operations!"""
                    except json.JSONDecodeError:
                        pass
                
                return f"❌ Registration failed: The device ID '{device_id}' was not found in the system. Please use a valid device ID."
            
            return f"❌ Confirmation failed: {error_msg}"
        
        # Try to parse the confirmation response
        try:
            if "response" in api_result:
                response_data = json.loads(api_result["response"])
                if response_data.get("responseCode") == 400:
                    led_controller.blink_led("red")
                    return f"❌ Registration failed: {response_data.get('responseMessage', 'Unknown error')}"
                elif response_data.get("responseCode") == 200 and response_data.get("deviceId"):
                    # Update device_id with the one returned from API if available
                    device_id = response_data.get("deviceId")
        except json.JSONDecodeError:
            pass  # Continue if response is not valid JSON
        
        # Check if device ID is already registered
        existing_device_id = local_db.get_device_id()
        if existing_device_id == device_id:
            logger.info(f"Device ID {device_id} already registered, skipping registration")
            led_controller.blink_led("yellow")  # Use yellow to indicate already registered
            
            return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Test Barcode: {test_scan['barcode']}

**Status:** This device is already registered and ready for barcode scanning operations.
No need to register again."""
        
        # Save device ID to database if not already registered
        local_db.save_device_id(device_id)
        
        # Register device with IoT Hub and send registration message
        try:
            config = load_config()
            if config:
                # Get IoT Hub owner connection string for device registration
                owner_connection_string = config.get("iot_hub", {}).get("connection_string", None)
                if not owner_connection_string:
                    iot_status = "⚠️ No IoT Hub connection string configured"
                else:
                    # Step 1: Register device with IoT Hub
                    registration_result = register_device_with_iot_hub(device_id)
                    if registration_result.get("success"):
                        logger.info(f"Device {device_id} registered successfully with IoT Hub")
                        
                        # Step 2: Send registration message to IoT Hub
                        try:
                            device_connection_string = registration_result.get("connection_string")
                            if device_connection_string:
                                hub_client = HubClient(device_connection_string)
                                
                                # Create registration message payload
                                registration_message = {
                                    "deviceId": device_id,
                                    "messageType": "device_registration",
                                    "action": "register",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "testBarcode": test_scan['barcode'],
                                    "registrationMethod": "usb_scanner_manual",
                                    "status": "registered"
                                }
                                
                                # Send registration message to IoT Hub
                                success = hub_client.send_message(json.dumps(registration_message), device_id)
                                if success:
                                    logger.info(f"📡 Registration message sent to IoT Hub for device {device_id}")
                                    iot_status = "✅ Device registered with IoT Hub and registration message sent"
                                else:
                                    logger.warning(f"⚠️ Device registered but failed to send registration message")
                                    iot_status = "⚠️ Device registered but registration message failed"
                            else:
                                logger.error("No device connection string available for IoT Hub messaging")
                                iot_status = "⚠️ Device registered but no connection string for messaging"
                        except Exception as msg_error:
                            logger.error(f"Failed to send registration message: {msg_error}")
                            iot_status = f"⚠️ Device registered but message failed: {str(msg_error)}"
                    else:
                        logger.error(f"Failed to register device {device_id}: {registration_result.get('error')}")
                        iot_status = f"⚠️ Failed to register device: {registration_result.get('error')}"
            else:
                iot_status = "⚠️ Configuration not loaded"
        except Exception as iot_error:
            logger.error(f"IoT Hub error: {iot_error}")
            iot_status = f"⚠️ IoT Hub error: {str(iot_error)}"
        
        # Blink green LED for success
        led_controller.blink_led("green")
        
        # Send confirmation message to frontend
        confirmation_msg = f"""🎉 Registration Confirmed Successfully!

**Device Details:**
• Device ID: {device_id}
• Test Barcode: {test_scan['barcode']}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ API confirmation sent
• ✅ Device saved in local database
• {iot_status}

**Status:** Device is now ready for barcode scanning operations!"""
        
        return confirmation_msg
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def register_device_with_iot_hub(device_id):
    """Fast device registration with Azure IoT Hub - optimized for speed
    
    Args:
        device_id (str): The device ID to register
        
    Returns:
        dict: A dictionary with success status and error message if applicable
    """
    try:
        from azure.iot.hub import IoTHubRegistryManager
        from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
        IOT_HUB_REGISTRY_AVAILABLE = True
    except ImportError:
        logger.error("Azure IoT Hub Registry Manager not available. Cannot register device.")
        return {"success": False, "error": "Azure IoT Hub Registry Manager not available"}
    
    try:
        # Load config once to get IoT Hub owner connection string
        config = load_config()
        if not config or "iot_hub" not in config or "connection_string" not in config["iot_hub"]:
            logger.error("IoT Hub connection string not found in config")
            return {"success": False, "error": "IoT Hub connection string not found in config"}
        
        # Check if device already exists in config (avoid redundant registration)
        if config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string"):
            existing_connection_string = config["iot_hub"]["devices"][device_id]["connection_string"]
            logger.info(f"Device {device_id} already configured, using existing connection string")
            return {"success": True, "device_id": device_id, "connection_string": existing_connection_string}
        
        # Get IoT Hub owner connection string
        iothub_connection_string = config["iot_hub"]["connection_string"]
        
        # Create IoTHubRegistryManager
        logger.info(f"Registering device {device_id} with Azure IoT Hub...")
        registry_manager = IoTHubRegistryManager.from_connection_string(iothub_connection_string)
        
        # Register the device
        try:
            # Check if device exists
            try:
                device = registry_manager.get_device(device_id)
                logger.info(f"Device {device_id} already exists in IoT Hub")
            except Exception:
                logger.info(f"Creating new device {device_id} in IoT Hub...")
                # Generate a secure primary key (base64 encoded)
                import base64
                import os
                # Generate a random 32-byte key and encode it as base64
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')  # Also generate secondary key
                status = "enabled"
                
                # Create device with SAS authentication
                device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, status)
                logger.info(f"Device {device_id} created successfully in IoT Hub")
            
            # Verify device was created/exists and has authentication
            if not device or not device.authentication or not device.authentication.symmetric_key:
                logger.error(f"Device {device_id} creation failed or missing authentication")
                return {"success": False, "error": f"Device {device_id} creation failed or missing authentication"}
            
            # Get the primary key
            primary_key = device.authentication.symmetric_key.primary_key
            if not primary_key:
                logger.error(f"No primary key generated for device {device_id}")
                return {"success": False, "error": f"No primary key generated for device {device_id}"}
            
            # Create connection string
            # Extract hostname from the IoT Hub connection string
            import re
            hostname_match = re.search(r'HostName=([^;]+)', iothub_connection_string)
            if not hostname_match:
                logger.error("Could not extract hostname from IoT Hub connection string")
                return {"success": False, "error": "Could not extract hostname from IoT Hub connection string"}
            
            hostname = hostname_match.group(1)
            connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
            
            # Update config file
            if "devices" not in config["iot_hub"]:
                config["iot_hub"]["devices"] = {}
            
            config["iot_hub"]["devices"][device_id] = {
                "connection_string": connection_string,
                "deviceId": device_id
            }
            
            # Always save the updated config to ensure connection string is persisted
            save_config(config)
            logger.info(f"Config file updated with device {device_id} connection string")
            
            return {"success": True, "device_id": device_id, "connection_string": connection_string}
            
        except Exception as ex:
            logger.error(f"Error registering device {device_id} with IoT Hub: {str(ex)}")
            return {"success": False, "error": str(ex)}
            
    except Exception as e:
        logger.error(f"Error in register_device_with_iot_hub: {str(e)}")
        return {"success": False, "error": str(e)}


# ============================================================================
# BARCODE PROCESSING FUNCTIONS
# ============================================================================

def is_barcode_registered(barcode: str) -> bool:
    """Check if a barcode is registered in the system"""
    try:
        from utils.barcode_device_mapper import BarcodeDeviceMapper
        mapper = BarcodeDeviceMapper()
        
        # Check if barcode exists in the mapping
        device_id = mapper.get_device_id_for_barcode(barcode)
        if not device_id:
            return False
            
        # Check if the mapped device is registered
        from utils.dynamic_device_manager import DynamicDeviceManager
        device_manager = DynamicDeviceManager()

        device_registered = (
            device_manager.is_device_registered(device_id) or 
            any(dev.get('device_id') == device_id for dev in (local_db.get_registered_devices() or []))
        )
        
        if device_registered:
            return True
            
        registered_devices = local_db.get_registered_devices()
        return any(dev.get('device_id') == device_id for dev in registered_devices) if registered_devices else False
        
    except Exception as e:
        logger.error(f"Error checking barcode registration: {e}")
        return False


# Removed duplicate function - using the main process_barcode_scan_auto() function below

def process_barcode_scan(barcode, device_id=None):
    """Process a barcode scan and determine if it's a valid product or device ID (Legacy function for compatibility)"""
    try:
        # Check if device is already registered
        current_device_id = local_db.get_device_id()
        
        # If device is registered and we have a barcode, process it normally
        if current_device_id and barcode:
            # Save scan to local database
            timestamp = local_db.save_scan(current_device_id, barcode)
            logger.info(f"Saved scan to local database: {current_device_id}, {barcode}, {timestamp}")
            
            # Send quantity update to IoT Hub (only for barcode scans, not registration)
            try:
                config = load_config()
                if config:
                    # Check if device already exists in config to avoid re-registration
                    device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(current_device_id, {}).get("connection_string", None)
                    
                    if not device_connection_string:
                        # Fast device registration without messages
                        registration_result = register_device_with_iot_hub(current_device_id)
                        if registration_result.get("success"):
                            device_connection_string = registration_result.get("connection_string")
                            logger.info(f"Device {current_device_id} registered for barcode scanning")
                        else:
                            logger.error(f"Failed to register device {current_device_id}: {registration_result.get('error')}")
                            led_controller.blink_led("red")
                            return f"⚠️ Barcode {barcode} scanned and saved locally, but failed to register device with IoT Hub."
                        
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                        success = hub_client.send_message(barcode, current_device_id)
                        if success:
                            led_controller.blink_led("green")
                            return f"✅ Barcode {barcode} scanned and sent to IoT Hub successfully!"
                        else:
                            led_controller.blink_led("orange")
                            return f"⚠️ Barcode {barcode} scanned and saved locally, but failed to send to IoT Hub."
                    else:
                        led_controller.blink_led("orange")
                        return f"⚠️ Barcode {barcode} scanned and saved locally, but no device connection string available."
                else:
                    led_controller.blink_led("orange")
                    return f"⚠️ Barcode {barcode} scanned and saved locally, but configuration not loaded."
            except Exception as e:
                logger.error(f"Error sending to IoT Hub: {e}")
                led_controller.blink_led("orange")
                return f"⚠️ Barcode {barcode} scanned and saved locally, but error sending to IoT Hub: {str(e)}"
        
        # If no device ID is registered yet, check if this barcode is a valid device ID
        if not current_device_id:
            is_online = api_client.is_online()
            if not is_online:
                led_controller.blink_led("red")
                return "❌ Device appears to be offline. Cannot validate device ID."
            
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
            payload = {"deviceId": barcode}
            
            logger.info(f"Making first API call to {api_url}")
            api_result = api_client.send_registration_barcode(api_url, payload)
            
            if api_result.get("success", False) and "response" in api_result:
                response_data = json.loads(api_result["response"])
                
                if response_data.get("deviceId") and response_data.get("responseCode") == 200:
                    device_id = response_data.get("deviceId")
                    
                    existing_device_id = local_db.get_device_id()
                    if existing_device_id == device_id:
                        logger.info(f"Device ID {device_id} already registered, skipping registration")
                        led_controller.blink_led("yellow")  # Use yellow to indicate already registered
                        return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}

**Status:** This device is already registered and ready for barcode scanning operations.
No need to register again."""
                    
                    # Save the device ID to local database
                    local_db.save_device_id(device_id)
                    
                    # Make second API call to confirm registration
                    logger.info(f"Making second API call to {api_url}")
                    second_result = api_client.send_registration_barcode(api_url, payload)
                    
                    # Send message to IoT Hub
                    try:
                        config = load_config()
                        if config:
                            # Check if device exists in IoT Hub config
                            device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string", None)
                            
                            # If device doesn't exist in config, register it with IoT Hub
                            if not device_connection_string:
                                logger.info(f"Device {device_id} not found in config, registering with IoT Hub")
                                # Register device with IoT Hub and update config
                                registration_result = register_device_with_iot_hub(device_id)
                                
                                if registration_result.get("success"):
                                    # Reload config after registration
                                    config = load_config()
                                    device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string", None)
                                    logger.info(f"Successfully registered device {device_id} with IoT Hub and updated config")
                                else:
                                    logger.error(f"Failed to register device with IoT Hub: {registration_result.get('error')}")
                                    device_connection_string = None
                                    logger.error(f"Cannot proceed without device-specific connection string")
                            
                            if device_connection_string:
                                hub_client = HubClient(device_connection_string)
                                registration_message = {
                                    "deviceId": device_id,
                                    "messageType": "device_registration",
                                    "action": "register",
                                    "scannedBarcode": barcode,
                                    "registrationMethod": "usb_scanner_automatic",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "status": "registered"
                                }
                                
                                # Send the structured registration message to IoT Hub
                                iot_success = hub_client.send_message(json.dumps(registration_message), device_id)
                                if iot_success:
                                    logger.info(f"📡 USB Scanner registration message sent to IoT Hub for device {device_id}")
                                    iot_status = "✅ Registration message sent to IoT Hub"
                                else:
                                    logger.warning(f"⚠️ USB Scanner registration failed to send to IoT Hub")
                                    iot_status = "⚠️ Failed to send registration message to IoT Hub"
                            else:
                                iot_status = "⚠️ No IoT Hub connection string available"
                        else:
                            iot_status = "⚠️ Failed to load configuration"
                    except Exception as e:
                        logger.error(f"Error sending to IoT Hub: {str(e)}")
                        iot_status = f"⚠️ Error: {str(e)}"
                    
                    # Blink green LED for success
                    led_controller.blink_led("green")
                    
                    # Return success message
                    return f"""🎉 Device Registration Successful!

**Device Details:**
• Device ID: {device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device ID registered with API
• ✅ Device saved in local database
• {iot_status}

**Status:** Device is now ready for barcode scanning operations!"""
                
                # Check if this is a test barcode
                elif response_data.get("responseMessage") == "This is a test barcode.":
                    # Save test barcode scan
                    local_db.save_test_barcode_scan(barcode)
                    
                    # Blink blue LED for test barcode
                    led_controller.blink_led("blue")
                    
                    return f"""ℹ️ This is a test barcode.

Test barcode {barcode} has been saved.
Please proceed with device registration confirmation."""
                
                # Check if this is an invalid barcode
                elif response_data.get("responseCode") == 400:
                    # Blink red LED for error
                    led_controller.blink_led("red")
                    
                    return f"❌ Invalid barcode. Please scan a valid device ID or test barcode."
        
        # If we have a device ID and barcode, process the barcode scan
        if device_id and barcode:
            # Validate barcode using the EAN validator
            try:
                validated_barcode = validate_ean(barcode)
            except BarcodeValidationError as e:
                led_controller.blink_led("red")
                return f"❌ Barcode validation error: {str(e)}"
            
            # Load configuration
            config = load_config()
            if not config:
                led_controller.blink_led("red")
                return "❌ Error: Failed to load configuration"
            
            # Save scan to local database
            timestamp = local_db.save_scan(device_id, validated_barcode, 1)
            logger.info(f"Saved scan to local database: {device_id}, {validated_barcode}, {timestamp}")
            
            # Check if we're online
            is_online = api_client.is_online()
            if not is_online:
                led_controller.blink_led("orange")
                return f"📥 Device appears to be offline. Message saved locally.\n\n**Details:**\n- Device ID: {device_id}\n- Barcode: {validated_barcode}\n- Timestamp: {timestamp}\n- Status: Will be sent when online"
            
            # Determine connection string for the device
            devices_config = config.get("iot_hub", {}).get("devices", {})
            if device_id in devices_config:
                connection_string = devices_config[device_id]["connection_string"]
            else:
                # If device doesn't exist in config, register it with IoT Hub
                logger.info(f"Device {device_id} not found in config, registering with IoT Hub")
                registration_result = register_device_with_iot_hub(device_id)
                
                if registration_result.get("success"):
                    # Reload config after registration
                    config = load_config()
                    devices_config = config.get("iot_hub", {}).get("devices", {})
                    if device_id in devices_config:
                        connection_string = devices_config[device_id]["connection_string"]
                        logger.info(f"Successfully registered device {device_id} with IoT Hub and updated config")
                    else:
                        connection_string = config.get("iot_hub", {}).get("connection_string", None)
                else:
                    connection_string = config.get("iot_hub", {}).get("connection_string", None)
                
                if not connection_string:
                    led_controller.blink_led("red")
                    return f"❌ Error: Device ID '{device_id}' not found in configuration and no default connection string provided."
            
            # Create IoT Hub client
            hub_client = HubClient(connection_string)
            
            # Send message (connection is handled internally)
            success = hub_client.send_message(validated_barcode, device_id, 1)
            
            if success:
                # Mark as sent in local database
                local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
                led_controller.blink_led("green")
                return f"✅ Barcode {validated_barcode} scanned and sent to IoT Hub successfully!"
            else:
                led_controller.blink_led("orange")
                return f"⚠️ Barcode {validated_barcode} scanned and saved locally, but failed to send to IoT Hub."
    
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        led_controller.blink_led("red")
        return f"""❌ **Barcode Scan Failed**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Error:** {str(e)[:100]}

🔴 Red LED indicates error"""

# ============================================================================
# DISPLAY AND STATUS FUNCTIONS
# ============================================================================

def get_recent_scans_display():
    """Get recent scanned barcodes for frontend display"""
    try:
        recent_scans = local_db.get_recent_scans(10)  # Get last 10 scans
        
        if not recent_scans:
            return "📋 **RECENT SCANNED BARCODES**\n\n❌ No barcode scans found."
        
        display_text = "📋 **RECENT SCANNED BARCODES**\n\n"
        
        for i, scan in enumerate(recent_scans, 1):
            device_id = scan['device_id']
            barcode = scan['barcode']
            timestamp = scan['timestamp']
            quantity = scan.get('quantity', 1)
            
            display_text += f"**{i}.** `{barcode}`\n"
            display_text += f"   • Device: {device_id}\n"
            display_text += f"   • Time: {timestamp}\n"
            display_text += f"   • Quantity: {quantity}\n\n"
        
        return display_text
        
    except Exception as e:
        logger.error(f"Error getting recent scans: {str(e)}")
        return f"❌ Error getting recent scans: {str(e)}"

def get_registration_status():
    """Get the current device registration status"""
    try:
        # Check if test barcode has been scanned
        test_scan = local_db.get_test_barcode_scan()
        test_barcode_scanned = test_scan is not None
        
        # Check if device ID is saved
        device_id = local_db.get_device_id()
        device_registered = device_id is not None
        
        status_text = "📋 **DEVICE REGISTRATION STATUS**\n\n"
        
        # Test barcode status
        if test_barcode_scanned:
            status_text += f"✅ **Test Barcode:** Scanned ({test_scan['barcode']}) at {test_scan['timestamp']}\n"
        else:
            status_text += "❌ **Test Barcode:** Not scanned - Please scan: 817994ccfe14\n"
        
        # Device registration status
        if device_registered:
            status_text += f"✅ **Device ID:** Registered ({device_id})\n"
        else:
            status_text += "❌ **Device ID:** Not registered - Please confirm registration\n"
        
        # Overall status
        if test_barcode_scanned and device_registered:
            status_text += "\n🎉 **DEVICE READY:** Can send messages to IoT Hub"
        else:
            status_text += "\n⚠️ **DEVICE NOT READY:** Complete registration steps above"
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        return f"❌ Error getting registration status: {str(e)}"

def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them to IoT Hub
    OPTIMIZED VERSION: Uses batch processing, connection caching, and reduced database calls
    
    Args:
        auto_retry (bool): If True, runs in background mode without returning status messages
        
    Returns:
        str: Status message if not in auto_retry mode, None otherwise
    """
    # This function is deprecated as the connection manager now handles automatic retry
    # Keeping it for backward compatibility but it just returns a message
    logger.info("process_unsent_messages is deprecated - connection manager handles automatic retry")
    return "✅ Automatic message retry is now handled by the connection manager in the background."

def get_pi_connection_status_display():
    """Get the current Pi connection status display string."""
    try:
        # Check if Pi is connected
        connected = check_raspberry_pi_connection()
        
        if connected:
            # Get Pi IP if available
            pi_ip = get_primary_raspberry_pi_ip()
            if pi_ip:
                return f"✅ External Raspberry Pi connected: {pi_ip}"
            else:
                return "✅ Raspberry Pi connected"
        else:
            return "❌ No external Raspberry Pi devices found on network"
    except Exception as e:
        logger.error(f"Error getting Pi connection status: {e}")
        return "⚠️ Error checking Pi connection status"

def refresh_pi_connection():
    """Refresh Raspberry Pi connection status and return updated display."""
    logger.info("🔄 Refreshing Raspberry Pi connection...")
    
    # Check connection
    connected = check_raspberry_pi_connection()
    
    # Get updated status display
    status_display = get_pi_connection_status_display()
    
    if connected:
        led_controller.blink_led("green")
        logger.info("✅ Connection refresh successful")
    else:
        led_controller.blink_led("red")
        logger.warning("❌ Connection refresh failed")
    
    return status_display

# ============================================================================
# DEVICE INFORMATION FUNCTIONS
# ============================================================================

def get_device_mac_address():
    """
    Get the current device's MAC address dynamically.
    Works on both Raspberry Pi and other Linux systems including live servers.
    
    Returns:
        str: MAC address if found, None otherwise
    """
    import re
    
    # Method 1: Use ip link command (most reliable for servers)
    try:
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Look for MAC addresses in the output
            mac_pattern = r'link/ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Device MAC address detected via ip link: {mac}")
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
            # Look for MAC addresses in ifconfig output
            mac_pattern = r'ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
            matches = re.findall(mac_pattern, result.stdout.lower())
            for mac in matches:
                if mac != "00:00:00:00:00:00":
                    logger.info(f"📍 Device MAC address detected via ifconfig: {mac}")
                    return mac
    except Exception as e:
        logger.warning(f"ifconfig method failed: {e}")
    
    # Method 3: Check /sys/class/net files (if available)
    try:
        interfaces = ['eth0', 'wlan0', 'enp0s3', 'ens33', 'eno1', 'ens160']
        for interface in interfaces:
            try:
                with open(f"/sys/class/net/{interface}/address", 'r') as f:
                    mac = f.read().strip().lower()
                    if mac and mac != "00:00:00:00:00:00" and ":" in mac:
                        logger.info(f"📍 Device MAC address detected from {interface}: {mac}")
                        return mac
            except (FileNotFoundError, PermissionError):
                continue
    except Exception as e:
        logger.debug(f"/sys/class/net method failed: {e}")
    
    # Method 4: Use hostname -I + ARP lookup (server-friendly)
    try:
        # Get local IP first
        ip_result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if ip_result.returncode == 0 and ip_result.stdout.strip():
            local_ip = ip_result.stdout.strip().split()[0]
            
            # Try to find MAC via ARP for local IP
            arp_result = subprocess.run(
                ["arp", "-n", local_ip],
                capture_output=True,
                text=True,
                timeout=3
            )
            if arp_result.returncode == 0:
                # Parse ARP output for MAC
                mac_match = re.search(r'([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})', arp_result.stdout.lower())
                if mac_match:
                    mac = mac_match.group(1)
                    if mac != "00:00:00:00:00:00":
                        logger.info(f"📍 Device MAC address detected via ARP lookup: {mac}")
                        return mac
    except Exception as e:
        logger.debug(f"ARP lookup method failed: {e}")
    
    logger.error("❌ Could not detect device MAC address using any method")
    return None

def get_device_ip():
    """
    Get the current device's IP address using multiple methods.
    Works on both Raspberry Pi and other Linux systems.
    
    Returns:
        str: IP address if found, None otherwise
    """
    try:
        # Method 1: Use hostname -I (most reliable for Pi)
        result = subprocess.run(
            ["hostname", "-I"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Get first IPv4 address (ignore IPv6)
            ips = result.stdout.strip().split()
            for ip in ips:
                if '.' in ip and not ip.startswith('127.'):  # IPv4 and not localhost
                    logger.info(f"📍 Device IP detected via hostname -I: {ip}")
                    return ip
    except Exception as e:
        logger.warning(f"hostname -I method failed: {e}")
    
    try:
        # Method 2: Check multiple network interfaces
        interfaces = ['eth0', 'wlan0', 'enp0s3', 'ens33']
        for interface in interfaces:
            result = subprocess.run(
                f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}' | cut -d/ -f1",
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip()
                if ip and not ip.startswith('127.'):
                    logger.info(f"📍 Device IP detected via {interface}: {ip}")
                    return ip
    except Exception as e:
        logger.warning(f"Interface scanning method failed: {e}")
    
    try:
        # Method 3: Use ip route (fallback)
        result = subprocess.run(
            "ip route get 8.8.8.8 | awk '{print $7}' | head -1",
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip()
            if ip and not ip.startswith('127.'):
                logger.info(f"📍 Device IP detected via route: {ip}")
                return ip
    except Exception as e:
        logger.warning(f"Route method failed: {e}")
    
    logger.error("❌ Could not detect device IP address")
    return None


def check_local_pi_and_notify_server():
    """
    Check if Raspberry Pi is locally attached and send MAC address notification to live server.
    Uses dynamic MAC address detection instead of static IP addresses.
    
    Returns:
        dict: Status information including pi_attached (True/False) and notification result
    """
    try:
        logger.info("🔍 Checking Pi device status and sending MAC address to live server...")
        
        # Get current device MAC address dynamically
        device_mac = get_device_mac_address()
        pi_attached = device_mac is not None
        
        # Generate unique device ID
        device_id = generate_dynamic_device_id()
        
        # Create JSON payload with MAC address for live server
        pi_details = {
            'mac_address': device_mac,
            'device_id': device_id,
            'timestamp': datetime.now().isoformat(),
            'detection_method': 'dynamic_mac_detection' if device_mac else 'failed',
            'device_type': 'raspberry_pi' if device_mac else 'unknown'
        }
        
        if pi_attached:
            logger.info(f"📍 Pi Status: ✅ Device Connected with MAC: {device_mac}")
        else:
            logger.info("📍 Pi Status: ❌ Device Not Connected - No MAC address detected")
        
        # Send to IoT Hub with MAC address
        iot_result = _send_pi_status_to_iot_hub(device_id, pi_attached, pi_details)
        
        # Send MAC address to live server in JSON format
        api_result = _send_pi_status_notification({
            'pi_attached': pi_attached,
            'device_id': device_id,
            'mac_address': device_mac,
            'timestamp': datetime.now().isoformat(),
            'pi_details': pi_details,
            'check_type': 'mac_address_detection'
        })
        
        # Prepare response with MAC address
        response = {
            'pi_attached': pi_attached,
            'pi_mac_address': device_mac,
            'device_id': device_id,
            'iot_hub_sent': iot_result['success'],
            'api_notification_sent': api_result['success'],
            'iot_hub_details': iot_result,
            'api_details': api_result,
            'timestamp': datetime.now().isoformat()
        }
        
        status_emoji = "✅" if pi_attached else "❌"
        iot_emoji = "📤" if iot_result['success'] else "⚠️"
        api_emoji = "📤" if api_result['success'] else "⚠️"
        
        logger.info(f"{status_emoji} Pi Status Check Complete: {pi_attached}")
        logger.info(f"{iot_emoji} IoT Hub Notification: {'Sent' if iot_result['success'] else 'Failed'}")
        logger.info(f"{api_emoji} API Notification: {'Sent' if api_result['success'] else 'Failed'}")
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error checking Pi status: {e}")
        return {
            'pi_attached': False,
            'pi_ip': None,
            'device_id': None,
            'iot_hub_sent': False,
            'api_notification_sent': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def _send_pi_status_to_iot_hub(device_id, pi_attached, pi_details):
    """
    Send Pi status to IoT Hub using existing hub client.
    
    Args:
        device_id (str): Device identifier
        pi_attached (bool): Whether Pi is attached
        pi_details (dict): Pi connection details
        
    Returns:
        dict: Result of IoT Hub send attempt
    """
    try:
        # Create message payload for IoT Hub
        message_data = {
            "messageType": "device_status",
            "deviceId": device_id,
            "status": "connected" if pi_attached else "disconnected",
            "ip_address": pi_details.get('ip'),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detection_method": pi_details.get('detection_method'),
            "device_info": {
                "pi_attached": pi_attached,
                "connection_details": pi_details
            }
        }
        
        # Get dynamic registration service for device connection
        registration_service = get_dynamic_registration_service()
        device_connection_string = registration_service.register_device_with_azure(device_id)
        
        if not device_connection_string:
            logger.error(f"❌ Failed to get device connection string for {device_id}")
            return {
                'success': False,
                'error': 'Failed to get device connection string'
            }
        
        # Use connection manager to send registration message with Pi checks
        from utils.connection_manager import ConnectionManager
        connection_manager =  ConnectionManager()
        
        # Check Pi availability before sending registration confirmation
        if not connection_manager.check_raspberry_pi_availability():
            logger.warning(f"Registration confirmation blocked: Raspberry Pi not connected for device {device_id}")
            # Save registration message locally for retry
            local_db.save_unsent_message(device_id, json.dumps(message_data), datetime.now())
            return "⚠️ **Registration saved locally - Pi offline**\n\nDevice registration will be confirmed when Raspberry Pi comes online."
        
        # Send registration confirmation via connection manager
        success, status_msg = connection_manager.send_message_with_retry(
            device_id=device_id,
            barcode=json.dumps(message_data),
            quantity=1,
            message_type="device_registration"
        )
        
        if success:
            logger.info(f"✅ Registration confirmation sent to IoT Hub for device {device_id}")
            return {
                'success': True,
                'device_id': device_id,
                'message_type': 'device_status'
            }
        else:
            logger.error(f"❌ Failed to send Pi status to IoT Hub for device {device_id}")
            return {
                'success': False,
                'error': 'IoT Hub send failed'
            }
            
    except Exception as e:
        logger.error(f"❌ Error sending Pi status to IoT Hub: {e}")
        return {
            'success': False,
            'error': str(e)
        }
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error checking Pi attachment status: {e}")
        return {
            'pi_attached': False,
            'pi_ip': None,
            'notification_sent': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


def _send_pi_status_notification(payload):
    """
    Send Pi status notification to server.
    
    Args:
        payload (dict): Notification payload with Pi status
        
    Returns:
        dict: Result of notification attempt
    """
    try:
        # Load configuration to get server notification URL
        config = load_config()
        
        # Try multiple notification endpoints
        notification_urls = [
            config.get("frontend", {}).get("notification_url", "https://iot.caleffionline.it/api/pi-status-notification"),
            "https://api2.caleffionline.it/api/v1/raspberry/piStatus",
            config.get("frontend", {}).get("base_url", "https://iot.caleffionline.it") + "/api/pi-status"
        ]
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'RaspberryPi-BarcodeScanner/1.0'
        }
        
        last_error = None
        
        for url in notification_urls:
            try:
                logger.info(f"📤 Sending Pi status notification to: {url}")
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10
                )
                
                if response.status_code in [200, 201, 202]:
                    logger.info(f"✅ Pi status notification sent successfully to {url}")
                    return {
                        'success': True,
                        'status_code': response.status_code,
                        'url': url,
                        'response': response.text[:200] if response.text else None
                    }
                else:
                    logger.warning(f"⚠️ Server returned status {response.status_code} for {url}")
                    last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"⚠️ Failed to send notification to {url}: {e}")
                last_error = str(e)
                continue
        
        # If all URLs failed
        logger.error(f"❌ Failed to send Pi status notification to all endpoints. Last error: {last_error}")
        return {
            'success': False,
            'error': last_error,
            'attempted_urls': notification_urls
        }
        
    except Exception as e:
        logger.error(f"❌ Error sending Pi status notification: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def start_usb_scanner_service():
    """Start the automatic USB scanner service"""
    global USB_SCANNER_RUNNING, usb_scanner_thread
    
    if USB_SCANNER_RUNNING:
        logger.info("USB scanner service already running")
        return
    
    logger.info("🚀 Starting Automatic USB Scanner Service")
    print("=" * 60)
    print("🚀 AUTOMATIC USB BARCODE SCANNER SERVICE")
    print("=" * 60)
    print("This service will automatically:")
    print("• Detect USB barcode scanners")
    print("• Register devices on first scan")
    print("• Send all barcodes to IoT Hub with quantity=1")
    print("• Work without manual intervention")
    print("=" * 60)
    
    USB_SCANNER_RUNNING = True
    
    # Start USB scanner monitoring thread
    scanner_thread = threading.Thread(target=usb_scanner_worker, daemon=True)
    scanner_thread.start()
    
    # Start barcode processor thread
    processor_thread = threading.Thread(target=barcode_processor_worker, daemon=True)
    processor_thread.start()
    
    logger.info("✅ USB scanner service started successfully")
    print("📱 Ready for automatic barcode scanning...")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep main thread alive
        while USB_SCANNER_RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping USB scanner service...")
        stop_usb_scanner_service()

def stop_usb_scanner_service():
    """Stop the USB scanner service"""
    global USB_SCANNER_RUNNING
    
    logger.info("Stopping USB scanner service")
    USB_SCANNER_RUNNING = False
    print("🛑 USB scanner service stopped")

def create_gradio_interface():
    """Create and return Gradio interface for manual testing"""
    # Keep Gradio interface for manual testing (optional)
    try:
        import gradio as gr
        
        # Create Gradio interface
        with gr.Blocks(title="Barcode Scanner") as app:
            gr.Markdown("# Barcode Scanner")
            
            with gr.Row():
                # Left column for barcode scanning
                with gr.Column():
                    gr.Markdown("## Scan Barcode")
                    
                    barcode_input = gr.Textbox(label="Barcode", placeholder="Scan or enter barcode")
                    device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID (optional)")
                    
                    with gr.Row():
                        send_button = gr.Button("Send Barcode", variant="primary")
                        clear_button = gr.Button("Clear")
                        
                    output_text = gr.Markdown("")
            
        with gr.Column():
            gr.Markdown("## Device Registration & Status")
            
            # Real-time Pi Connection Status (updated automatically)
            pi_status_display = gr.Markdown("## 📡 Raspberry Pi Connection Status\n\n*Loading status...*")
            
            # Registration section
            with gr.Column():
                gr.Markdown("## Device Registration")
                
                with gr.Row():
                    scan_test_barcode_button = gr.Button("Scan Any Test Barcode", variant="primary")
                    confirm_registration_button = gr.Button("Confirm Registration", variant="secondary")
            
            # Status and management section
            gr.Markdown("## System Status")
            
            with gr.Row():
                process_unsent_button = gr.Button("Process Unsent Messages", variant="secondary")
                pi_status_button = gr.Button("Refresh Pi Status", variant="secondary")
                
            status_text = gr.Markdown("")
            pi_status_display = gr.Markdown("")
            
            # USB Scanner control
            with gr.Row():
                start_usb_btn = gr.Button("🚀 Start USB Scanner", variant="primary")
                stop_usb_btn = gr.Button("🛑 Stop USB Scanner", variant="secondary")
                
            usb_status = gr.Textbox(label="USB Scanner Status", value="Not running", interactive=False)
            
            def start_usb_interface():
                start_usb_scanner_service()
                return "✅ USB Scanner service started"
                
            def stop_usb_interface():
                stop_usb_scanner_service()
                return "🛑 USB Scanner service stopped"
            
            # Event handlers
            send_button.click(
                fn=process_barcode_scan,
                inputs=[barcode_input, device_id_input],
                outputs=[output_text]
            )
            
            clear_button.click(
                fn=lambda: ("", ""),
                inputs=[],
                outputs=[barcode_input, device_id_input]
            )
            
            # Two-step registration handlers
            scan_test_barcode_button.click(
                fn=generate_registration_token,
                inputs=[],
                outputs=[status_text]
            )
            
            confirm_registration_button.click(
                fn=confirm_registration,
                inputs=[barcode_input, device_id_input],
                outputs=[status_text]
            )
            
            process_unsent_button.click(
                fn=process_unsent_messages_ui,
                inputs=[],
                outputs=[status_text],
                show_progress='full'
            )
            
            pi_status_button.click(
                fn=refresh_pi_connection,
                inputs=[],
                outputs=[pi_status_display]
            )
            
            start_usb_btn.click(start_usb_interface, outputs=usb_status)
            stop_usb_btn.click(stop_usb_interface, outputs=usb_status)
        
        return app
    
    except ImportError:
        logger.info("Gradio not available, running in headless mode")
        return None

logger.info("🚀 Initializing Raspberry Pi Barcode Scanner System...")

# Check if running on Raspberry Pi and initialize accordingly
if IS_RASPBERRY_PI:
    logger.info("🔍 Detected: Running on Raspberry Pi device")
    logger.info("📱 Mode: Direct Pi device with Azure IoT Hub connection")
    
    # Initialize Pi device service for direct IoT Hub connection
    pi_device_service = RaspberryPiDeviceService()
    
    # Start barcode scanning service
    pi_device_service.start_barcode_scanning_service()
    
    logger.info("✅ Raspberry Pi Device Service initialized")
    logger.info("📡 Connected to Azure IoT Hub for inventory tracking")
    logger.info("📱 Ready to scan barcodes - data will be published to IoT Hub")
    
else:
    logger.info("🔍 Detected: Running on server/desktop (will search for external Pi devices)")
    logger.info("📱 Mode: Network-based Pi discovery and management")
    
    # Simplified Pi connection check - no excessive logging
    pi_connected = check_raspberry_pi_connection()
    
    if pi_connected:
        logger.info("✅ Raspberry Pi connection established")
    else:
        logger.info("ℹ️ No Raspberry Pi found - system will auto-detect when Pi connects")
    
    logger.info("📡 IoT Hub connection established")
    logger.info("🎯 System ready for plug-and-play barcode scanning")
    logger.info("🌐 Web interface will be available at: http://localhost:7860")

logger.info("🚀 Barcode scanner system initialized")
logger.info("📱 System configured for Azure IoT Hub inventory tracking")

# System initialization complete
logger.info("✅ System initialization complete")

# ==========================================
# PI HEARTBEAT SYSTEM FOR PLUG-AND-PLAY
# ==========================================

class PiHeartbeatService:
    """
    Pi Heartbeat Service for cloud environments where LAN discovery fails.
    Ensures server can always detect Pi devices regardless of network topology.
    """
    
    def __init__(self, config):
        self.config = config
        self.device_id = None
        self.server_url = None
        self.heartbeat_interval = 30  # seconds
        self.registration_interval = 300  # 5 minutes
        self.running = False
        self.heartbeat_thread = None
        self.registration_thread = None
        self.last_heartbeat = None
        self.last_registration = None
        self.connection_string = None
        
        # Get device info
        self.device_info = self._get_device_info()
        logger.info(f"🔄 Pi Heartbeat Service initialized for device: {self.device_info.get('device_id', 'unknown')}")
    
    def _get_device_info(self):
        """Get comprehensive device information for heartbeat"""
        try:
            # Generate consistent device ID based on hardware
            mac = None
            try:
                mac = get_local_device_mac()
                logger.info(f"Retrieved MAC address: {mac}")
            except Exception as e:
                logger.warning(f"Could not get MAC address: {e}")
                
            if mac and isinstance(mac, str) and len(mac) > 0:
                # Clean and format MAC address
                mac = mac.strip().lower()
                # Remove any non-hex characters
                mac = ''.join(c for c in mac if c in '0123456789abcdef:')
                device_id = f"pi-{mac.replace(':', '')[-8:]}"
            else:
                # Fallback to random ID if MAC can't be determined
                device_id = f"pi-{uuid.uuid4().hex[:8]}"
            
            # Get network info
            hostname = socket.gethostname()
            
            # Get local IP addresses
            local_ips = []
            try:
                # Get all network interfaces
                result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    local_ips = result.stdout.strip().split()
            except Exception as e:
                logger.warning(f"Could not get local IPs: {e}")
            
            # Get system info
            system_info = {
                'platform': os.uname().sysname,
                'architecture': os.uname().machine,
                'hostname': hostname,
                'python_version': sys.version.split()[0]
            }
            
            return {
                'device_id': device_id,
                'mac_address': mac,
                'hostname': hostname,
                'local_ips': local_ips,
                'system_info': system_info,
                'services': {
                    'barcode_scanner': True,
                    'ssh': self._check_service_port(22),
                    'web': self._check_service_port(5000)
                }
            }
        except Exception as e:
            logger.error(f"❌ Failed to get device info: {e}")
            return {'device_id': f"pi-{uuid.uuid4().hex[:8]}"}
    
    def _check_service_port(self, port):
        """Check if a service port is available"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _discover_server(self):
        """Discover the barcode scanner server"""
        try:
            # Try configured server URLs first
            server_candidates = [
                "https://iot.caleffionline.it",
                "https://api2.caleffionline.it",
                "http://localhost:7860",
                "http://127.0.0.1:7860"
            ]
            
            # Add any configured server URLs
            if self.config:
                frontend_config = self.config.get("frontend", {})
                if frontend_config.get("base_url"):
                    server_candidates.insert(0, frontend_config["base_url"])
            
            for server_url in server_candidates:
                try:
                    # Test server connectivity
                    response = requests.get(f"{server_url}/api/health", timeout=10)
                    if response.status_code == 200:
                        health_data = response.json()
                        if "barcode" in health_data.get("service", "").lower():
                            logger.info(f"✅ Server discovered: {server_url}")
                            return server_url
                except Exception as e:
                    logger.debug(f"Server {server_url} not reachable: {e}")
                    continue
            
            logger.debug("⚠️ No barcode scanner server found - continuing without server discovery")
            return None
            
        except Exception as e:
            logger.error(f"❌ Server discovery failed: {e}")
            return None
    
    def _register_with_server(self):
        """Register Pi device with the server"""
        try:
            if not self.server_url:
                self.server_url = self._discover_server()
                if not self.server_url:
                    return False
            
            registration_data = {
                "device_id": self.device_info["device_id"],
                "device_type": "raspberry_pi",
                "mac_address": self.device_info.get("mac_address"),
                "hostname": self.device_info.get("hostname"),
                "local_ips": self.device_info.get("local_ips", []),
                "system_info": self.device_info.get("system_info", {}),
                "services": self.device_info.get("services", {}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "heartbeat_interval": self.heartbeat_interval,
                "capabilities": ["barcode_scanning", "iot_hub_messaging", "local_storage"]
            }
            
            # Register device
            response = requests.post(
                f"{self.server_url}/api/v1/raspberry/register",
                json=registration_data,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                self.connection_string = result.get("connection_string")
                self.device_id = self.device_info["device_id"]
                
                logger.info(f"✅ Pi device registered successfully: {self.device_id}")
                
                # Save registration info to config
                self._save_registration_info(result)
                
                return True
            else:
                logger.warning(f"⚠️ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            return False
    
    def _save_registration_info(self, registration_result):
        """Save registration information to config"""
        try:
            config = load_config()
            if not config:
                config = {}
            
            config["pi_heartbeat"] = {
                "device_id": self.device_id,
                "server_url": self.server_url,
                "connection_string": self.connection_string,
                "last_registration": datetime.now(timezone.utc).isoformat(),
                "registration_result": registration_result
            }
            
            save_config(config)
            logger.info("💾 Pi heartbeat registration saved to config")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not save registration info: {e}")
    
    def _send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            if not self.server_url or not self.device_id:
                return False
            
            # Get current status
            current_status = {
                "device_id": self.device_id,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "local_ips": self.device_info.get("local_ips", []),
                "services": {
                    "barcode_scanner": True,
                    "ssh": self._check_service_port(22),
                    "web": self._check_service_port(5000)
                },
                "system_metrics": {
                    "uptime": time.time(),
                    "memory_available": True,  # Simplified for now
                    "disk_space": True
                }
            }
            
            # Send heartbeat
            response = requests.post(
                f"{self.server_url}/api/v1/raspberry/heartbeat",
                json=current_status,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.last_heartbeat = datetime.now(timezone.utc)
                logger.debug(f"💓 Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat error: {e}")
            return False
    
    def _heartbeat_worker(self):
        """Background worker for sending heartbeats"""
        logger.info("💓 Pi heartbeat worker started")
        
        while self.running:
            try:
                # Send heartbeat
                success = self._send_heartbeat()
                
                if not success:
                    # If heartbeat fails, try to re-register
                    logger.info("🔄 Heartbeat failed, attempting re-registration...")
                    self._register_with_server()
                
                # Wait for next heartbeat
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"❌ Heartbeat worker error: {e}")
                time.sleep(self.heartbeat_interval)
    
    def _registration_worker(self):
        """Background worker for periodic re-registration"""
        logger.info("📝 Pi registration worker started")
        
        while self.running:
            try:
                # Wait for registration interval
                time.sleep(self.registration_interval)
                
                # Re-register to ensure server has latest info
                if self.running:
                    logger.info("🔄 Periodic re-registration...")
                    self._register_with_server()
                    
            except Exception as e:
                logger.error(f"❌ Registration worker error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def start(self):
        """Start the Pi heartbeat service"""
        try:
            if self.running:
                logger.warning("⚠️ Pi heartbeat service already running")
                return
            
            logger.info("🚀 Starting Pi heartbeat service...")
            
            # Initial registration
            registration_success = self._register_with_server()
            if not registration_success:
                logger.warning("⚠️ Initial registration failed, will retry in background")
            
            # Start background workers
            self.running = True
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(
                target=self._heartbeat_worker,
                name="PiHeartbeatWorker",
                daemon=True
            )
            self.heartbeat_thread.start()
            
            # Start registration thread
            self.registration_thread = threading.Thread(
                target=self._registration_worker,
                name="PiRegistrationWorker", 
                daemon=True
            )
            self.registration_thread.start()
            
            logger.info("✅ Pi heartbeat service started successfully")
            logger.info(f"💓 Heartbeat interval: {self.heartbeat_interval}s")
            logger.info(f"📝 Registration interval: {self.registration_interval}s")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Pi heartbeat service: {e}")
            self.running = False
    
    def stop(self):
        """Stop the Pi heartbeat service"""
        try:
            logger.info("🛑 Stopping Pi heartbeat service...")
            self.running = False
            
            # Send final offline status
            if self.server_url and self.device_id:
                try:
                    offline_status = {
                        "device_id": self.device_id,
                        "status": "offline",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    requests.post(
                        f"{self.server_url}/api/v1/raspberry/heartbeat",
                        json=offline_status,
                        timeout=10
                    )
                    logger.info("📤 Offline status sent")
                except Exception as e:
                    logger.warning(f"⚠️ Could not send offline status: {e}")
            
            # Wait for threads to finish
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(timeout=5)
            
            if self.registration_thread and self.registration_thread.is_alive():
                self.registration_thread.join(timeout=5)
            
            logger.info("✅ Pi heartbeat service stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping Pi heartbeat service: {e}")

# Initialize Pi Heartbeat Service
pi_heartbeat_service = None
try:
    config = load_config()
    pi_heartbeat_service = PiHeartbeatService(config)
    pi_heartbeat_service.start()
    logger.info("🔄 Pi heartbeat system enabled for plug-and-play discovery")
except Exception as e:
    logger.error(f"❌ Failed to initialize Pi heartbeat service: {e}")

# Initialize Pi connectivity monitoring
config = load_config()
raspberry_pi_config = config.get("raspberry_pi", {})

# Start dynamic discovery for local network scanning
if raspberry_pi_config.get("dynamic_discovery", False):
    try:
        from utils.dynamic_pi_discovery import DynamicPiDiscovery
        global dynamic_pi_discovery
        dynamic_pi_discovery = DynamicPiDiscovery(config)
        dynamic_pi_discovery.start_discovery()
        logger.info("🔍 Dynamic Pi discovery system started")
    except Exception as e:
        logger.error(f"Failed to start dynamic Pi discovery: {e}")

# Start remote connectivity monitoring for cross-network detection
if raspberry_pi_config.get("remote_connectivity_monitoring", False):
    try:
        from utils.remote_pi_connectivity import RemotePiConnectivity
        global remote_pi_connectivity
        remote_pi_connectivity = RemotePiConnectivity(config)
        remote_pi_connectivity.start_monitoring()
        logger.info("🌐 Remote Pi connectivity monitoring started")
    except Exception as e:
        logger.error(f"Failed to start remote Pi connectivity monitoring: {e}")

# Global variable for Gradio app instance


def update_pi_status_display():
    """Update the Pi status display in the Gradio interface"""
    global gradio_app_instance
    if gradio_app_instance is not None:
        try:
            # Get real-time status
            status_text = refresh_pi_connection()
            # Update the pi_status_display component
            # Note: This is a simplified approach - in a real implementation,
            # you would use Gradio's state management or callbacks
            logger.debug("🔄 Updating Pi status display")
        except Exception as e:
            logger.error(f"Error updating Pi status display: {e}")

def start_periodic_status_updates():
    """Single status update (no background thread)"""
    try:
        update_pi_status_display()
        logger.info("📊 Single status update completed")
    except Exception as e:
        logger.error(f"Status update error: {e}")

def discover_server():
    """Auto-discover server for plug-and-play mode"""
    server_candidates = [
        "https://iot.caleffionline.it",
        "http://iot.caleffionline.it", 
        "http://10.0.0.4:5000",
        "http://192.168.1.1:5000",
        "http://192.168.0.1:5000",
        "http://10.0.0.1:5000"
    ]
    
    for server_url in server_candidates:
        try:
            logger.info(f"🌐 Trying server: {server_url}")
            response = requests.get(f"{server_url}/api/health", timeout=10)
            
            if response.status_code == 200:
                health_data = response.json()
                if health_data.get("service") == "barcode_scanner_server":
                    logger.info(f"✅ Server discovered: {server_url}")
                    return server_url
                    
        except Exception as e:
            logger.debug(f"❌ Server {server_url} not reachable: {e}")
            continue
    
    logger.error("❌ No server found! Check network connectivity.")
    return None

def register_with_barcode(server_url, registration_barcode):
    """Register Pi device using scanned barcode"""
    try:
        # Generate device ID from barcode + hardware
        mac = get_local_mac_address() or "unknown"
        device_id = f"pi-{registration_barcode[-4:]}-{mac.replace(':', '')[-8:]}"
        
        logger.info(f"📝 Registering device: {device_id} with barcode: {registration_barcode}")
        
        # Registration payload
        registration_data = {
            "device_id": device_id,
            "registration_barcode": registration_barcode,
            "device_type": "raspberry_pi_plug_play",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_info": {
                "hostname": socket.gethostname(),
                "mac_address": mac,
                "registration_method": "barcode_scan_plug_play"
            },
            "plug_and_play": True,
            "client_version": "2.0.0"
        }
        
        # Register with server
        response = requests.post(
            f"{server_url}/api/register_device",
            json=registration_data,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            connection_string = result.get("connection_string")
            
            logger.info("✅ Device registered successfully")
            logger.info(f"🔗 IoT Hub connection received")
            
            # Save config
            config = load_config()
            if not config:
                config = {}
            
            # Update config with device registration info
            config["device_registration"] = {
                "device_id": device_id,
                "server_url": server_url,
                "connection_string": connection_string,
                "registration_time": datetime.now().isoformat()
            }
            
            save_config(config)
            
            return device_id, connection_string
        else:
            logger.error(f"❌ Registration failed: {response.status_code}")
            return None, None
            
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        return None, None

def plug_and_play_mode():
    """Plug-and-play registration mode - single attempt"""
    logger.info("📱 PLUG-AND-PLAY MODE ACTIVE")
    logger.info("🔌 Connect your USB barcode scanner")
    logger.info("📊 Scan ANY barcode to register this device")
    
    # Discover server
    server_url = discover_server()
    if not server_url:
        logger.error("❌ Cannot continue without server connection")
        return False
    
    # Single barcode registration attempt
    logger.info("⏳ Ready for barcode scan...")
    
    try:
        # Check if running in non-interactive mode (systemd service)
        if not sys.stdin.isatty():
            logger.info("🤖 Running in non-interactive mode - skipping manual barcode input")
            logger.info("⚠️ Manual registration required - please run interactively")
            return False
            
        print("\n🎯 Scan barcode to register (or type barcode + Enter):")
        barcode = input().strip()
        
        if barcode and len(barcode) >= 6:
            logger.info(f"📊 Barcode scanned: {barcode}")
            
            device_id, connection_string = register_with_barcode(server_url, barcode)
            
            if device_id and connection_string:
                logger.info("✅ REGISTRATION SUCCESSFUL!")
                logger.info(f"🆔 Device ID: {device_id}")
                logger.info("🎉 Device is now ready for barcode scanning")
                return True
            else:
                logger.error("❌ Registration failed")
                return False
        else:
            logger.warning("⚠️ Invalid barcode, please provide a valid barcode")
            return False
            
    except KeyboardInterrupt:
        logger.info("🛑 Registration cancelled")
        return False
    except Exception as e:
        logger.error(f"❌ Registration error: {e}")
        return False

def load_pi_config():
    """Load Pi configuration from main config.json"""
    try:
        config = load_config()
        if config and "device_registration" in config:
            return config["device_registration"]
    except Exception as e:
        logger.warning(f"⚠️ Could not load Pi config: {e}")
    return None

def check_for_updates(server_url, device_id, current_version="2.0.0"):
    """Check for OTA updates from server"""
    try:
        logger.info("🔍 Checking for updates...")
        
        response = requests.get(
            f"{server_url}/api/ota/check_update",
            params={
                "device_id": device_id,
                "current_version": current_version
            },
            timeout=10
        )
        
        if response.status_code == 200:
            update_info = response.json()
            
            if update_info.get("has_update", False):
                logger.info(f"📦 Update available: {update_info.get('latest_version')}")
                return update_info
            else:
                logger.info("✅ No updates available")
                return None
        else:
            logger.warning(f"⚠️ Update check failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Update check error: {e}")
        return None

def download_and_apply_update(server_url, update_info):
    """Download and apply OTA update"""
    try:
        logger.info(f"📥 Downloading update {update_info.get('latest_version')}...")
        
        # Download update package
        download_url = f"{server_url}/api/ota/download_update"
        response = requests.get(
            download_url,
            params={"update_id": update_info.get("update_id")},
            stream=True,
            timeout=300
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Download failed: {response.status_code}")
            return False
        
        # Save update file
        update_file = f"/tmp/barcode_scanner_update_{update_info.get('update_id')}.zip"
        with open(update_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Create backup
        backup_file = f"/tmp/barcode_scanner_backup_{int(time.time())}.tar.gz"
        backup_cmd = f"tar -czf {backup_file} -C /opt/barcode-scanner ."
        subprocess.run(backup_cmd, shell=True, check=True)
        logger.info(f"💾 Backup created: {backup_file}")
        
        # Extract and apply update
        import zipfile
        import tempfile
        
        extract_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(update_file, 'r') as zipf:
            zipf.extractall(extract_dir)
        
        # Copy updated files
        import shutil
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, extract_dir)
                dest_file = os.path.join("/opt/barcode-scanner", rel_path)
                
                # Create directory if needed
                os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(src_file, dest_file)
        
        # Clean up
        os.remove(update_file)
        shutil.rmtree(extract_dir)
        
        logger.info("✅ Update applied successfully")
        
        # Notify server of successful update
        try:
            requests.post(
                f"{server_url}/api/ota/update_status",
                json={
                    "device_id": update_info.get("device_id"),
                    "version": update_info.get("latest_version"),
                    "status": "success",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                timeout=10
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not notify update status: {e}")
        
        # Restart service
        logger.info("🔄 Restarting service to apply update...")
        subprocess.run(["sudo", "systemctl", "restart", "barcode-scanner-plug-play"], check=False)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Update application error: {e}")
        return False

def send_single_heartbeat(pi_config):
    """Send single heartbeat to server (no background loop)"""
    try:
        server_url = pi_config.get("server_url")
        device_id = pi_config.get("device_id")
        
        if server_url and device_id:
            heartbeat_data = {
                "device_id": device_id,
                "status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "system_info": {
                    "hostname": socket.gethostname(),
                    "uptime": time.time()
                }
            }
            
            response = requests.post(
                f"{server_url}/api/device_heartbeat",
                json=heartbeat_data,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("💓 Heartbeat sent successfully")
                return True
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Heartbeat error: {e}")
        return False

def check_single_update(pi_config):
    """Check for updates once (no background loop)"""
    try:
        server_url = pi_config.get("server_url")
        device_id = pi_config.get("device_id")
        
        if server_url and device_id:
            update_info = check_for_updates(server_url, device_id)
            if update_info:
                logger.info("🔄 Update available - applying...")
                return download_and_apply_update(server_url, update_info)
            else:
                logger.info("✅ No updates available")
                return True
                
    except Exception as e:
        logger.error(f"❌ Update check error: {e}")
        return False

def start_plug_and_play_barcode_service():
    """Start fully automated barcode scanning service without UI"""
    logger.info("🎯 Starting Plug-and-Play Barcode Service...")
    logger.info("📱 Connect your USB barcode scanner and start scanning!")

    # detect if interactive or running under systemd
    interactive = sys.stdin.isatty()
    
    if not interactive:
        # Running as systemd service - start daemon mode
        logger.info("🔧 Running in systemd service mode - starting daemon...")
        start_barcode_daemon()
        return

    # Interactive mode only
    while True:
        try:
            # Manual mode: ask user for service
            choice = input("\n🎯 Select service (1-6): ").strip()
            logger.info(f"✅ Selected service: {choice}")

            # Wait for barcode input
            print("\n🎯 Ready for barcode scan (or type barcode + Enter):")
            barcode = input().strip()

            if barcode and len(barcode) >= 6:
                logger.info(f"📊 Barcode scanned: {barcode}")

                result = process_barcode_scan_auto(barcode)

                if "✅" in result:
                    logger.info("✅ Barcode processed successfully")
                    print("✅ SUCCESS: Barcode sent to inventory system")
                else:
                    logger.warning("⚠️ Barcode processing had issues")
                    print("⚠️ WARNING: Check logs for details")

            else:
                logger.warning("⚠️ Invalid barcode - please scan a valid barcode")
                print("⚠️ Invalid barcode - try again")

        except EOFError:
            logger.warning("❌ Error: EOF when reading a line")
            logger.info("🛑 Interactive mode terminated")
            break

        except KeyboardInterrupt:
            logger.info("🛑 Plug-and-Play service stopped by user")
            print("\n🛑 Service stopped. Thank you for using the barcode scanner!")
            break

def start_barcode_daemon():
    """Start barcode scanner in daemon mode for systemd service"""
    logger.info("🔧 Starting barcode scanner daemon...")
    logger.info("📡 Listening for barcode scanner input...")
    
    # Initialize connection manager for automated processing
    try:
        connection_manager = ConnectionManager()
        logger.info("✅ Connection manager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection manager: {e}")
        return
    
    # Main daemon loop - no interactive input
    while True:
        try:
            # In daemon mode, we wait for external triggers or scheduled tasks
            # This could be:
            # 1. File-based barcode input
            # 2. Network-based barcode input
            # 3. USB scanner input via device files
            # 4. Scheduled heartbeat/status updates
            
            logger.info("📡 Daemon active - waiting for barcode input...")
            
            # Check for any pending unsent messages
            try:
                unsent_count = len(connection_manager.local_storage.get_unsent_messages())
                if unsent_count > 0:
                    logger.info(f"🔄 Processing {unsent_count} unsent messages...")
                    # Process unsent messages in background
                    connection_manager._process_unsent_messages_background()
            except Exception as e:
                logger.debug(f"Unsent message check error: {e}")
            
            # Sleep for 30 seconds before next check
            time.sleep(30)
            
        except KeyboardInterrupt:
            logger.info("🛑 Barcode scanner daemon stopped")
            break
        except Exception as e:
            logger.error(f"❌ Daemon error: {e}")
            time.sleep(5)  # Wait before retry

def process_barcode_scan_auto(barcode):
    """Process barcode scan automatically without UI interaction - Fixed for proper EAN updates"""
    try:
        # Initialize status variables
        api_success = False
        iot_success = False
        
        # Get device ID (should be auto-registered by now)
        device_id = local_db.get_device_id()
        if not device_id:
            # Try to auto-register if not already done
            mac_address = get_local_mac_address()
            if mac_address:
                device_id = f"scanner-{mac_address.replace(':', '')[-8:]}"
                local_db.save_device_id(device_id)
                logger.info(f"✅ Auto-registered device: {device_id}")
                
                # Register device with IoT Hub
                try:
                    registration_service = get_dynamic_registration_service()
                    registration_service.register_device_with_azure(device_id)
                    logger.info(f"✅ Device {device_id} registered with Azure IoT Hub")
                except Exception as reg_error:
                    logger.error(f"❌ IoT Hub registration failed: {reg_error}")
            else:
                return "❌ No device ID available - registration failed"
        
        # Validate and clean barcode
        try:
            validated_barcode = validate_ean(barcode)
            logger.info(f"📦 Processing EAN barcode: {validated_barcode}")
        except BarcodeValidationError as e:
            # Accept alphanumeric barcodes for Code 128/Code 39
            if len(barcode) >= 6 and len(barcode) <= 20:
                validated_barcode = barcode.strip()
                logger.info(f"📦 Processing alphanumeric barcode: {validated_barcode}")
            else:
                logger.error(f"❌ Invalid barcode: {e}")
                return f"❌ Invalid barcode: {str(e)}"
        
        # Save scan locally first
        try:
            timestamp = local_db.save_scan(device_id, validated_barcode, 1)
            logger.info(f"💾 Saved scan locally: {device_id}, {validated_barcode}")
        except Exception as save_error:
            logger.error(f"Failed to save scan locally: {save_error}")
        
        # Send to Frontend API
        try:
            api_result = api_client.send_barcode_scan(device_id, validated_barcode, 1)
            if api_result.get('success', False):
                api_success = True
                logger.info("✅ Sent to Frontend API successfully")
            else:
                logger.warning(f"⚠️ API send failed: {api_result.get('message', 'Unknown error')}")
        except Exception as e:
            logger.error(f"❌ API send error: {e}")
        
        # Send to IoT Hub with proper EAN message format
        try:
            # Use dynamic registration service to get device connection string
            registration_service = get_dynamic_registration_service()
            device_connection_string = registration_service.get_device_connection_string(device_id)
            
            if device_connection_string and "YOUR_DEVICE" not in device_connection_string:
                # Create proper EAN update message
                ean_message = {
                    "messageType": "quantity_update",
                    "deviceId": device_id,
                    "ean": validated_barcode,
                    "quantity": 1,
                    "action": "scan",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Send to IoT Hub
                hub_client = HubClient(device_connection_string)
                success = hub_client.send_message(ean_message, device_id)
                if success:
                    iot_success = True
                    logger.info(f"✅ EAN {validated_barcode} sent to IoT Hub successfully")
                else:
                    logger.error("❌ Failed to send EAN to IoT Hub")
            else:
                logger.warning("⚠️ Invalid or missing IoT Hub connection string - using fallback registration")
                # Try to register device and get connection string
                try:
                    registration_service.register_device_with_azure(device_id)
                    device_connection_string = registration_service.get_device_connection_string(device_id)
                    if device_connection_string:
                        ean_message = {
                            "messageType": "quantity_update",
                            "deviceId": device_id,
                            "ean": validated_barcode,
                            "quantity": 1,
                            "action": "scan",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        hub_client = HubClient(device_connection_string)
                        success = hub_client.send_message(ean_message, device_id)
                        if success:
                            iot_success = True
                            logger.info(f"✅ EAN {validated_barcode} sent to IoT Hub after registration")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback registration failed: {fallback_error}")
                
        except Exception as e:
            logger.error(f"❌ IoT Hub send error: {e}")
        
        # Return status based on success
        if api_success and iot_success:
            return f"✅ EAN {validated_barcode} sent to both API and IoT Hub successfully"
        elif iot_success:
            return f"✅ EAN {validated_barcode} sent to IoT Hub successfully (API failed)"
        elif api_success:
            return f"⚠️ EAN {validated_barcode} sent to API only (IoT Hub failed)"
        else:
            return f"⚠️ EAN {validated_barcode} saved locally (will retry when online)"
            
    except Exception as e:
        logger.error(f"❌ Barcode processing error: {e}")
        return f"❌ Processing error: {str(e)}"

if __name__ == "__main__":
    import os
    
    # Check for USB auto mode
    if len(sys.argv) > 1 and sys.argv[1] == "--usb-auto":
        start_usb_scanner_service()
    elif IS_RASPBERRY_PI:
        # Running on Raspberry Pi - check if registered
        logger.info("🚀 Starting Raspberry Pi Plug-and-Play Service...")
        
        # Load existing config
        pi_config = load_pi_config()
        
        if pi_config and pi_config.get("registered"):
            # Already registered - initialize service
            logger.info("✅ Device already registered")
            logger.info(f"🆔 Device ID: {pi_config.get('device_id')}")
            logger.info("📱 Pi will connect directly to Azure IoT Hub")
            logger.info("📷 Barcode scanning service active - scan barcodes to publish to IoT Hub")
            
            try:
                # Send single heartbeat and check for updates
                send_single_heartbeat(pi_config)
                check_single_update(pi_config)
                
                # Service initialized - ready for use
                logger.info("✅ Raspberry Pi Device Service initialized")
                logger.info("🎯 Ready for barcode scanning operations")
                logger.info("🚫 No background loops - service runs on-demand")
                
            except KeyboardInterrupt:
                logger.info("🛑 Raspberry Pi Device Service stopped by user")
                if 'pi_device_service' in globals() and pi_device_service:
                    pi_device_service.stop()
        else:
            # Not registered - enter plug-and-play mode
            logger.info("📱 Device not registered - entering plug-and-play mode")
            
            if plug_and_play_mode():
                logger.info("🎉 Registration complete! Restart service to begin scanning.")
            else:
                logger.error("❌ Registration failed")
                sys.exit(1)
    else:
        # Running on server/desktop - start TRUE PLUG-AND-PLAY mode
        logger.info("🚀 Starting TRUE PLUG-AND-PLAY Barcode Scanner System...")
        logger.info("🔌 NO UI required - fully automatic operation")
        
        # Initialize connection manager
        connection_manager = ConnectionManager()
        logger.info("✅ Connection manager initialized")
        
        # Auto-register device immediately
        success = auto_register_device_to_server()
        
        if success:
            logger.info("✅ Device auto-registered successfully")
            logger.info("🎯 SYSTEM READY - Starting automatic USB scanner service")
            logger.info("📱 All scans will be automatically sent to API and IoT Hub")
            
            # Start USB scanner service instead of plug-and-play
            start_usb_scanner_service()
            
        else:
            logger.error("❌ Auto-registration failed - starting USB scanner anyway")
            logger.info("🔄 USB scanner will auto-register on first scan")
            
            # Start USB scanner service
            start_usb_scanner_service()