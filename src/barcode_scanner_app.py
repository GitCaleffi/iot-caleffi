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
from typing import AsyncGenerator
from datetime import datetime, timezone, timedelta
from barcode_validator import validate_ean, BarcodeValidationError

# Global variables for Pi status reporting and automatic message processing
pi_status_thread = None
last_pi_status = None
pi_status_queue = queue.Queue()

# Initialize connection manager for automatic offline/online handling
connection_manager = None

def initialize_connection_manager():
    """Initialize the global connection manager for automatic message handling"""
    global connection_manager
    if connection_manager is None:
        connection_manager = get_connection_manager()
        logger.info("✅ Connection manager initialized with automatic offline/online message handling")
        logger.info("🔄 Automatic Pi monitoring and message retry system active")
    return connection_manager

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
from utils.dynamic_device_manager import device_manager
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.dynamic_device_id import generate_dynamic_device_id
from utils.network_discovery import NetworkDiscovery
from utils.connection_manager import get_connection_manager
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

# Initialize automatic connection management
initialize_connection_manager()

# Offline simulation removed

# Track all processed device IDs, even those not saved in the database
processed_device_ids = set()

# Auto-registration function
def auto_register_device_to_server():
    """Automatically register device with live server using local MAC address"""
    try:
        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("❌ Cannot auto-register: MAC address not found")
            return False
            
        # Generate device ID from MAC address
        device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
        
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
            
        # Registration payload
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
        
        logger.info(f"📤 Auto-registering device {device_id} to server...")
        
        # Try each URL until one works
        for url in live_server_urls:
            try:
                logger.info(f"Trying registration URL: {url}")
                response = requests.post(
                    url,
                    json=registration_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Device auto-registered successfully: {device_id} via {url}")
                    
                    # Save to local database
                    local_db.save_device_id(device_id)
                    
                    # Start heartbeat thread
                    threading.Thread(
                        target=send_heartbeat_to_server,
                        args=(device_id, local_ip, url.replace('/api/pi-device-register', '/api/pi-device-heartbeat')),
                        daemon=True
                    ).start()
                    
                    return True
                else:
                    logger.warning(f"Registration failed for {url}: {response.status_code} - {response.text[:100]}")
                    
            except Exception as e:
                logger.warning(f"Registration error for {url}: {e}")
                continue
        
        logger.error(f"❌ Auto-registration failed for all endpoints")
        return False
            
    except Exception as e:
        logger.error(f"❌ Auto-registration error: {e}")
        return False

def send_heartbeat_to_server(device_id, ip_address, heartbeat_url):
    """Send periodic heartbeat to live server"""
    
    while True:
        try:
            heartbeat_data = {
                "device_id": device_id,
                "ip_address": ip_address
            }
            
            response = requests.post(
                heartbeat_url,
                json=heartbeat_data,
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug(f"💓 Heartbeat sent for {device_id}")
            else:
                logger.warning(f"⚠️ Heartbeat failed: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ Heartbeat error: {e}")
            
        # Wait 30 seconds before next heartbeat
        time.sleep(30)

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
def get_pi_status_api():
    """Return Pi connection status for API use (True/False + IP)."""
    # Refresh status before returning
    connected = check_raspberry_pi_connection()
    return {
        "connected": connected,
        "ip": _pi_connection_status.get("ip"),
        "ssh_available": _pi_connection_status.get("ssh_available"),
        "web_available": _pi_connection_status.get("web_available"),
        "last_check": _pi_connection_status.get("last_check").isoformat() if _pi_connection_status.get("last_check") else None
    }

def is_scanner_connected():
    """Checks if a USB barcode scanner is connected - for live server, always return True."""
    try:
        # For live server deployment, skip physical scanner check
        # The server acts as the barcode input interface
        logger.info("📱 Live server mode: Virtual barcode scanner enabled")
        return True
        
        # Original physical scanner detection (commented for live server)
        # command = "grep -E -i 'scanner|barcode|keyboard' /sys/class/input/event*/device/name"
        # result = subprocess.run(command, shell=True, capture_output=True, text=True)
        # 
        # if result.returncode == 0 and result.stdout:
        #     logger.info(f"Scanner check successful, found devices:\n{result.stdout.strip()}")
        #     return True
        # else:
        #     logger.warning("No barcode scanner detected via input device names.")
        #     return False
    except Exception as e:
        logger.error(f"Error checking for scanner: {e}")
        # For live server, return True even on error
        return True

def discover_raspberry_pi_devices():
    """Automatically discover Raspberry Pi devices on the local network."""
    try:
        logger.info("🔍 Starting automatic Raspberry Pi device discovery...")
        discovery = NetworkDiscovery()
        
        # Discover all Raspberry Pi devices on the network (disable nmap to avoid root privilege issues)
        devices = discovery.discover_raspberry_pi_devices(use_nmap=False)
        
        if devices:
            logger.info(f"✅ Found {len(devices)} Raspberry Pi device(s) on the network:")
            for i, device in enumerate(devices, 1):
                logger.info(f"  📱 Device {i}: {device['ip']} ({device['mac']})")
                
                # Test connectivity
                ssh_available = discovery.test_raspberry_pi_connection(device['ip'], 22)
                web_available = discovery.test_raspberry_pi_connection(device['ip'], 5000)
                
                device['ssh_available'] = ssh_available
                device['web_available'] = web_available
                
                logger.info(f"    SSH: {'✅' if ssh_available else '❌'} | Web: {'✅' if web_available else '❌'}")
            
            return devices
        else:
            logger.info("❌ No Raspberry Pi devices found on the network")
            return []
            
    except Exception as e:
        logger.error(f"Error during Raspberry Pi discovery: {e}")
        return []

def get_primary_raspberry_pi_ip():
    """Bypasses network discovery and returns a local IP, assuming the device is the scanner."""
    logger.info("⚙️ Local mode active: Bypassing network scan for Raspberry Pi.")
    mac_address = get_local_mac_address()
    if mac_address:
        logger.info(f"🖥️ Using local MAC address for device identification: {mac_address}")
    else:
        logger.error("🚨 Could not determine local MAC address. Device ID may be incorrect.")
    # Return a loopback/local IP to signify local operation.
    return "127.0.0.1"

def get_known_raspberry_pi_ip():
    """Get the known Raspberry Pi IP address as a guaranteed fallback."""
    try:
        known_ip = "192.168.1.18"  # User's specific Raspberry Pi
        logger.info(f"🔍 Testing direct connection to known Pi at {known_ip}")
        
        # First try network-based detection
        discovery = NetworkDiscovery()
        device = discovery.discover_raspberry_pi_by_ip(known_ip)
        
        if device and device['is_raspberry_pi']:
            logger.info(f"✅ Confirmed Raspberry Pi at known IP: {known_ip}")
            return known_ip
        else:
            # If network detection fails, use static override
            logger.info(f"🔗 Network detection failed, using static IP override for {known_ip}")
            return get_static_raspberry_pi_ip()
            
    except Exception as e:
        logger.error(f"Error testing known Raspberry Pi IP: {e}")
        # Always fall back to static IP
        return get_static_raspberry_pi_ip()

def get_static_raspberry_pi_ip():
    """Return the user's static Raspberry Pi IP address without any network checks."""
    static_ip = "192.168.1.18"  # User's confirmed Raspberry Pi IP
    logger.info(f"📍 Using static Raspberry Pi IP (no network validation): {static_ip}")
    logger.info(f"ℹ️ This IP is used based on user configuration, assuming device is available")
    return static_ip

# Global variable to track Pi connection status
_pi_connection_status = {
    'connected': False,
    'ip': None,
    'last_check': None,
    'cache_duration': 30  # seconds
}

# Global flag to prevent quantity updates during registration
REGISTRATION_IN_PROGRESS = False
registration_lock = threading.Lock()

def check_raspberry_pi_connection():
    """Always returns True - no device validation needed."""
    global _pi_connection_status
    logger.info("⚙️ Auto mode: No device validation required.")
    
    pi_ip = "127.0.0.1"  # Local IP

    _pi_connection_status.update({
        'connected': True,
        'ip': pi_ip,
        'last_check': datetime.now(),
        'ssh_available': True,
        'web_available': True
    })
    
    logger.info(f"✅ Device ready for barcode scanning")
    return True

def get_pi_connection_status_display():
    """Get formatted connection status for display in Gradio UI."""
    global _pi_connection_status
    
    if not _pi_connection_status['last_check']:
        return "🔍 **Checking Raspberry Pi connection...**"
    
    if _pi_connection_status['connected']:
        ip = _pi_connection_status['ip']
        ssh = "✅" if _pi_connection_status['ssh_available'] else "❌"
        web = "✅" if _pi_connection_status['web_available'] else "❌"
        last_check = _pi_connection_status['last_check'].strftime('%H:%M:%S')
        
        return f"""🔗 **Raspberry Pi Connected**

📍 **IP Address:** {ip}
🔌 **SSH Access:** {ssh}
🌐 **Web Service:** {web}
🕓 **Last Check:** {last_check}

✅ **Status:** Ready for operations"""
    else:
        last_check = _pi_connection_status['last_check'].strftime('%H:%M:%S')
        return f"""❌ **Raspberry Pi Disconnected**

⚠️ **No connection** to Raspberry Pi found
🕓 **Last Check:** {last_check}

🚨 **Actions disabled** until connection is restored"""

def require_pi_connection(func):
    """Decorator that no longer blocks when Pi appears offline.
    We let the inner function handle offline/online via ConnectionManager,
    ensuring consistent warnings and local-save behavior.
    """
    def wrapper(*args, **kwargs):
        try:
            # Prefer live status from ConnectionManager, fall back to cached status
            cm = get_connection_manager()
            pi_available = cm.check_raspberry_pi_availability()
        except Exception:
            pi_available = _pi_connection_status.get('connected', False)

        if not pi_available:
            # Do not block; just provide gentle visual cue and continue
            logger.info("Pi not detected by decorator; delegating to function-level handling")
            blink_led("yellow")

        return func(*args, **kwargs)

    return wrapper

def auto_connect_to_raspberry_pi():
    """Automatically connect to a discovered Raspberry Pi device."""
    try:
        primary_ip = get_primary_raspberry_pi_ip()
        
        if primary_ip:
            # Save the discovered IP to configuration for future use
            config = load_config()
            if not config:
                config = {}
                
            if 'raspberry_pi' not in config:
                config['raspberry_pi'] = {}
                
            config['raspberry_pi']['auto_discovered_ip'] = primary_ip
            config['raspberry_pi']['last_discovery'] = datetime.now().isoformat()
            
            save_config(config)
            
            logger.info(f"🔗 Auto-connected to Raspberry Pi: {primary_ip}")
            return {
                'success': True,
                'ip': primary_ip,
                'message': f'Successfully connected to Raspberry Pi at {primary_ip}'
            }
        else:
            return {
                'success': False,
                'ip': None,
                'message': 'No Raspberry Pi devices found on the network'
            }
            
    except Exception as e:
        logger.error(f"Error auto-connecting to Raspberry Pi: {e}")
        return {
            'success': False,
            'ip': None,
            'message': f'Error during auto-connection: {str(e)}'
        }



# UI wrapper for processing unsent messages with progress
def get_unsent_messages_status():
    """Get current status of unsent messages - for display only, processing is automatic."""
    try:
        # Get connection manager status
        global connection_manager
        if not connection_manager:
            connection_manager = initialize_connection_manager()
        
        # Get unsent message count
        unsent_messages = local_db.get_unsent_scans()
        unsent_count = len(unsent_messages) if unsent_messages else 0
        
        # Get connection status
        pi_available = connection_manager.check_raspberry_pi_availability()
        internet_connected = connection_manager.is_connected_to_internet
        iot_hub_connected = connection_manager.is_connected_to_iot_hub
        
        # Get Pi IP for display
        pi_ip = get_primary_raspberry_pi_ip()
        
        if unsent_count == 0:
            return f"""✅ **No Unsent Messages**

📊 **Message Queue:** Empty
🔄 **Auto-Processing:** Active

**Connection Status:**
• 📍 **Pi IP:** {pi_ip or 'Not found'}
• 🍓 **Pi Status:** {'✅ Connected' if pi_available else '❌ Offline'}
• 🌐 **Internet:** {'✅ Connected' if internet_connected else '❌ Offline'}
• ☁️ **IoT Hub:** {'✅ Connected' if iot_hub_connected else '❌ Offline'}

{'🟢 **All systems ready** - Messages will be sent immediately' if (pi_available and internet_connected and iot_hub_connected) else '🔄 **Automatic retry active** - Messages will be sent when connection is restored'}"""
        else:
            status_emoji = "🔄" if (pi_available and internet_connected) else "⏳"
            processing_status = "Being processed automatically" if (pi_available and internet_connected) else "Waiting for connection"
            
            return f"""📱 **Unsent Messages Status**

📊 **Queue Count:** {unsent_count} messages
{status_emoji} **Status:** {processing_status}
🔄 **Auto-Processing:** Active (checks every 60 seconds)

**Connection Status:**
• 📍 **Pi IP:** {pi_ip or 'Not found'}
• 🍓 **Pi Status:** {'✅ Connected' if pi_available else '❌ Offline'}
• 🌐 **Internet:** {'✅ Connected' if internet_connected else '❌ Offline'}
• ☁️ **IoT Hub:** {'✅ Connected' if iot_hub_connected else '❌ Offline'}

{'🔄 **Messages will be sent automatically** when all connections are restored' if not (pi_available and internet_connected and iot_hub_connected) else '🟢 **Messages are being processed** - check back in a moment'}

💡 **No manual action needed** - the system handles message retry automatically"""
            
    except Exception as e:
        logger.error(f"Error getting unsent messages status: {e}")
        return f"""❌ **Error Getting Message Status**

⚠️ **Error:** {str(e)}
🔄 **Auto-Processing:** Still active in background

💡 **System continues to work** despite display error"""

def auto_register_new_device(device_id: str, pi_ip: str) -> dict:
    """Automatically register a new device when first detected."""
    try:
        logger.info(f"🆕 Auto-registering new device: {device_id}")
        
        # Save device registration to local database
        registration_data = {
            'device_id': device_id,
            'registration_date': datetime.now().isoformat(),
            'pi_ip': pi_ip,
            'auto_registered': True
        }
        
        local_db.save_device_registration(device_id, registration_data)
        
        # Send registration message via connection manager (handles offline automatically)
        global connection_manager
        if not connection_manager:
            connection_manager = initialize_connection_manager()
            
        success, message = connection_manager.send_message_with_retry(
            device_id=device_id,
            barcode="DEVICE_REGISTRATION",
            quantity=0,
            message_type="device_registration"
        )
        
        logger.info(f"✅ Device {device_id} auto-registered successfully")
        return {
            'success': True,
            'message': f'Device {device_id} registered successfully',
            'iot_hub_status': message
        }
        
    except Exception as e:
        logger.error(f"❌ Error auto-registering device {device_id}: {e}")
        return {
            'success': False,
            'message': f'Registration failed: {str(e)}'
        }

# Offline simulation logic removed

# Setup message retry system
retry_queue = queue.Queue()
retry_thread = None
retry_interval = 300  # seconds
retry_running = False
retry_lock = threading.Lock()
last_queue_check = datetime.now()
retry_enabled = False

def blink_led(color):
    """Control real Raspberry Pi GPIO LEDs for status indication.
    
    This function controls actual hardware LEDs connected to GPIO pins.
    Different colors indicate different system states:
    - Green: Success/OK
    - Red: Error/Failure  
    - Yellow: Warning/Offline
    - Orange: Partial success
    
    Args:
        color (str): LED color - 'green', 'red', 'yellow', or 'orange'
    """
    try:
        # Only attempt GPIO control if we're actually on a Raspberry Pi
        if not IS_RASPBERRY_PI:
            logger.debug(f"💡 LED simulation (not on Pi): {color.upper()} light")
            return
        
        # Import GPIO library only when needed and on Raspberry Pi
        try:
            import RPi.GPIO as GPIO
        except ImportError:
            logger.warning("⚠️ RPi.GPIO not available - install with: sudo apt install python3-rpi.gpio")
            logger.info(f"💡 LED status (no GPIO): {color.upper()}")
            return
        
        # LED pin configuration (BCM numbering) - Update these pins based on your wiring
        LED_PINS = {
            'red': 18,      # GPIO 18 (Physical Pin 12) - Error/Failure
            'green': 23,    # GPIO 23 (Physical Pin 16) - Success/OK
            'yellow': 24,   # GPIO 24 (Physical Pin 18) - Warning/Offline
            'orange': 25    # GPIO 25 (Physical Pin 22) - Partial success
        }
        
        # Get the pin for the requested color
        pin = LED_PINS.get(color.lower())
        if not pin:
            logger.warning(f"⚠️ Unknown LED color: {color}. Available: {list(LED_PINS.keys())}")
            return
        
        logger.info(f"💡 Activating {color.upper()} LED on GPIO pin {pin}...")
        
        # Setup GPIO with proper error handling
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)  # Suppress warnings for cleaner output
        
        # Configure pin as output with initial state LOW
        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        
        # Enhanced blink pattern based on status type
        import time
        
        if color.lower() == 'red':  # Error - rapid blinking
            for _ in range(5):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.2)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.2)
        elif color.lower() == 'green':  # Success - steady on then off
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(2.0)  # Stay on for 2 seconds
            GPIO.output(pin, GPIO.LOW)
        elif color.lower() == 'yellow':  # Warning - slow blink
            for _ in range(3):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.8)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.5)
        else:  # Orange or other - standard blink
            for _ in range(3):
                GPIO.output(pin, GPIO.HIGH)
                time.sleep(0.5)
                GPIO.output(pin, GPIO.LOW)
                time.sleep(0.3)
        
        # Ensure LED is off after blinking
        GPIO.output(pin, GPIO.LOW)
        
        # Clean up specific pin (not all GPIO)
        GPIO.cleanup(pin)
        
        logger.info(f"✅ {color.upper()} LED sequence completed on GPIO {pin}")
        
    except Exception as e:
        logger.error(f"❌ Error controlling GPIO LED: {e}")
        logger.error(f"   • Make sure you're running as root/sudo for GPIO access")
        logger.error(f"   • Check LED wiring to GPIO pins: {LED_PINS}")
        logger.error(f"   • Install GPIO library: sudo apt install python3-rpi.gpio")
        # Fallback to log message if GPIO fails
        logger.info(f"💡 LED status (GPIO failed): {color.upper()}")
        logger.error(f"LED blink error: {str(e)}")
        # Fallback visual indication
        print(f"⚠️ LED ERROR: Could not blink {color} LED - {str(e)}")

def generate_registration_token():
    """Prepare for device registration (no token required)"""
    
    # Check Raspberry Pi connection first using connection manager
    from utils.connection_manager import get_connection_manager
    connection_manager = get_connection_manager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("Device registration blocked: Raspberry Pi not connected")
        blink_led("red")
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
        
        blink_led("green")
        return response_msg
        
    except Exception as e:
        logger.error(f"Error preparing registration: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

def confirm_registration(registration_token, device_id):
    """Confirm device registration with Pi connection check and no token validation
    
    CRITICAL: This function performs DEVICE REGISTRATION ONLY - NO INVENTORY UPDATES!
    """
    global REGISTRATION_IN_PROGRESS
    
    # Set registration flag to prevent any quantity updates
    with registration_lock:
        REGISTRATION_IN_PROGRESS = True
    
    logger.info("🔒 STARTING DEVICE REGISTRATION - NO INVENTORY/QUANTITY UPDATES WILL BE SENT")
    logger.info("🔒 This is REGISTRATION ONLY operation - no barcode scans or inventory changes")
    logger.info("🔒 REGISTRATION_IN_PROGRESS flag set to TRUE - blocking all quantity updates")
    
    # Check Raspberry Pi connection first
    from utils.connection_manager import get_connection_manager
    connection_manager = get_connection_manager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("Device registration blocked: Raspberry Pi not connected")
        # Clear registration flag on error
        with registration_lock:
            REGISTRATION_IN_PROGRESS = False
        blink_led("red")
        return f"""❌ **Operation Failed: Raspberry Pi Not Connected**

**Device ID:** {device_id}
**Status:** Registration cancelled - Pi not reachable

Please ensure the Raspberry Pi device is connected and reachable on the network before registration.

🔴 Red LED indicates Pi connection failure"""
    # On live server, we don't want to check actual Pi connectivity
    
    # 1. First check Raspberry Pi connection before proceeding
    # connection_manager = get_connection_manager()
    # 
    # # Get Pi IP and connection status
    # pi_ip = get_primary_raspberry_pi_ip()
    # pi_connected = connection_manager.check_raspberry_pi_availability()
    # 
    # if not pi_connected:
    #     error_msg = "❌ **Operation Failed: Raspberry Pi Not Connected**\n\n"
    #     error_msg += f"**Pi Status:** {pi_ip if pi_ip else 'Not found'} - Offline\n\n"
    #     error_msg += "**Action:** Please ensure the Raspberry Pi device is connected and reachable on the network before registration."
    #     logger.warning("Registration blocked: Raspberry Pi not connected")
    
    logger.info("📍 Raspberry Pi connection verified for registration")
    pi_ip = get_primary_raspberry_pi_ip() or "Unknown"
    
    # 2. Check if barcode scanner is connected (if needed)
    # Note: Removed scanner check as it may not be required for all setups
    
    try:
        global processed_device_ids

        if not device_id or device_id.strip() == "":
            blink_led("red")
            return "❌ Please enter a device ID."
        
        # Strip device_id safely (no token needed)
        device_id = device_id.strip()
        
        # Check if device is already registered in our system
        if device_manager.is_device_registered(device_id):
            blink_led("red")
            return f"❌ Device ID '{device_id}' is already registered. Please use a different Device ID."
        
        # Check if device is already registered in local DB (legacy check)
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            # Find the registration date for display
            existing_device = next((dev for dev in registered_devices if dev['device_id'] == device_id), None)
            reg_date = existing_device.get('registration_date', 'Unknown') if existing_device else 'Unknown'
            blink_led("red")
            return f"❌ Device already registered with ID: {device_id} (Registered: {reg_date}). Please use a different device ID."
        
        # Gather device info for registration
        device_info = {
            "registration_method": "direct_registration",
            "online_at_registration": True,
            "user_agent": "Barcode Scanner App v2.0",
            "pi_ip": pi_ip
        }
        
        # Register device directly (no token validation)
        success, reg_message = device_manager.register_device_without_token(device_id, device_info)

        if not success:
            blink_led("red")
            return f"❌ Registration failed: {reg_message}"
        
        # Save device registration locally
        local_db.save_device_registration(device_id, {
            'registration_date': datetime.now(timezone.utc).isoformat(),
            'pi_ip': pi_ip,
            'registration_method': 'direct_registration'
        })
        
        # Create registration confirmation message for IoT Hub
        # IMPORTANT: This is REGISTRATION ONLY - NO INVENTORY UPDATES!
        confirmation_message_data = {
            "deviceId": device_id,
            "messageType": "device_registration",
            "operation_type": "device_registration",  # Explicit operation type
            "status": "registered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Device registration confirmed - NO INVENTORY IMPACT",
            "pi_ip": pi_ip,
            "registration_method": "direct_registration",
            
        }
        confirmation_message_json = json.dumps(confirmation_message_data)
        
        # TEMPORARILY DISABLE IoT Hub registration confirmation to prevent quantity updates
        # This prevents any potential barcode-related messages during registration
        iot_success = True  # Mark as successful to avoid error states
        iot_status = "ℹ️ IoT Hub registration confirmation disabled to prevent inventory updates"
        
        logger.info("🔒 BLOCKING IoT Hub registration confirmation to prevent 'EAN undefined' inventory issues")
        logger.info("🔒 Device registration completed locally and via API only")
        
        # Note: IoT Hub registration confirmation is disabled until the 'EAN undefined' issue is resolved
        # The device will still be registered locally and with the API, but no IoT Hub message will be sent
        # during registration to prevent any potential inventory/quantity update confusion
        
        # Confirm device registration with API using new endpoint
        api_confirmation_status = "ℹ️ API confirmation not attempted"
        
        try:
            # Confirm registration with API using new confirmRegistration endpoint
            logger.info(f"Confirming device registration {device_id} with API...")
            api_result = api_client.confirm_registration(device_id, pi_ip)
            
            if api_result.get('success', False):
                api_confirmation_status = "✅ Device registration confirmed with API successfully"
                logger.info(f"Device {device_id} registration confirmed with API")
            else:
                api_confirmation_status = f"⚠️ API confirmation failed: {api_result.get('message', 'Unknown error')}"
                logger.warning(f"API confirmation failed: {api_result}")
                
        except Exception as e:
            logger.error(f"Error with API confirmation: {str(e)}")
            api_confirmation_status = f"⚠️ API confirmation error: {str(e)}"
        
        # Determine LED color based on overall success
        if iot_success:
            blink_led("green")
        else:
            blink_led("orange")
        
        # Clear registration flag before returning success
        with registration_lock:
            REGISTRATION_IN_PROGRESS = False
        logger.info("🔒 REGISTRATION_IN_PROGRESS flag cleared - quantity updates now allowed")
        
        return f"""🎉 Device Registration Completed!

**Device Details:**
• Device ID: {device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
• Pi IP Address: {pi_ip}
• Registration Method: Direct (no token required)

**Actions Completed:**
• ✅ Device registered with device manager
• ✅ Device ID saved locally
• {iot_status}
• {api_confirmation_status}

**Status:** Device is now ready for barcode scanning operations!

**Next Steps:**
• Use 'Send Barcode' feature with valid EAN barcodes
• Device will appear in frontend when actual barcode scans are processed
• Registration data is available via IoT Hub and API

**You can now scan real product barcodes for inventory management.**"""
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        # Clear registration flag on error too
        with registration_lock:
            REGISTRATION_IN_PROGRESS = False
        logger.info("🔒 REGISTRATION_IN_PROGRESS flag cleared due to error")
        blink_led("red")
        return f"❌ Error: {str(e)}"


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

def send_pi_status_to_servers(pi_connected, pi_ip=None):
    """Send Pi connection status to IoT Hub and external API"""
    try:
        # Create status message
        status_message = {
            "messageType": "pi_connection_status",
            "pi_connected": pi_connected,
            "pi_ip": pi_ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_ip": "192.168.1.8",
            "source": "barcode_scanner_app"
        }
        
        results = {
            "iot_hub_success": False,
            "api_success": False,
            "errors": []
        }
        
        # Send to IoT Hub
        try:
            connection_manager = get_connection_manager()
            if connection_manager:
                # Use system device for status reporting
                system_device_id = "live-server-pi-status"
                
                # Create a simple status message that won't trigger barcode validation
                simple_message = f"PI_STATUS:{json.dumps(status_message)}"
                
                # Try to send via connection manager
                success = connection_manager.send_message_with_retry(
                    system_device_id, 
                    simple_message
                )
                results["iot_hub_success"] = success
                
                if success:
                    logger.info(f"📡 Pi status sent to IoT Hub: Connected={pi_connected}")
                else:
                    results["errors"].append("Failed to send Pi status to IoT Hub")
        except Exception as e:
            results["errors"].append(f"IoT Hub error: {str(e)}")
            logger.error(f"IoT Hub Pi status error: {e}")
        
        # Send to external API
        try:
            # Send directly to Pi status endpoint
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/piStatus"
            
            response = requests.post(
                api_url,
                json=status_message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            results["api_success"] = response.status_code == 200
            
            if results["api_success"]:
                logger.info(f"📡 Pi status sent to external API: Connected={pi_connected}")
            else:
                results["errors"].append(f"API returned status {response.status_code}")
                
        except Exception as e:
            results["errors"].append(f"External API error: {str(e)}")
            logger.error(f"External API Pi status error: {e}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error sending Pi status: {e}")
        return {"iot_hub_success": False, "api_success": False, "errors": [str(e)]}

def pi_status_monitor():
    """Background thread to monitor and report Pi connection status"""
    global last_pi_status
    
    while True:
        try:
            connection_manager = get_connection_manager()
            if connection_manager:
                # Check Pi availability
                pi_available = connection_manager.check_raspberry_pi_availability()
                
                # Get Pi IP from config
                config = load_config()
                pi_config = config.get('raspberry_pi', {}) if config else {}
                configured_ip = pi_config.get('auto_detected_ip')
                
                # Only send if status changed or every 5 minutes
                current_time = time.time()
                status_changed = (last_pi_status is None or last_pi_status != pi_available)
                time_to_send = (not hasattr(pi_status_monitor, 'last_send_time') or 
                              (current_time - pi_status_monitor.last_send_time) > 300)  # 5 minutes
                
                if status_changed or time_to_send:
                    # Send status to servers
                    results = send_pi_status_to_servers(pi_available, configured_ip)
                    
                    # Update tracking variables
                    last_pi_status = pi_available
                    pi_status_monitor.last_send_time = current_time
                    
                    # Add to status queue for UI updates
                    status_info = {
                        "pi_connected": pi_available,
                        "pi_ip": configured_ip,
                        "timestamp": datetime.now().isoformat(),
                        "iot_hub_sent": results["iot_hub_success"],
                        "api_sent": results["api_success"],
                        "errors": results["errors"]
                    }
                    
                    try:
                        pi_status_queue.put_nowait(status_info)
                    except queue.Full:
                        pass  # Queue full, skip this update
                    
                    if status_changed:
                        logger.info(f"📡 Pi connection status changed: {pi_available} (IP: {configured_ip})")
            
        except Exception as e:
            logger.error(f"Pi status monitor error: {e}")
        
        # Check every 30 seconds
        time.sleep(30)

def get_pi_status_info():
    """Get current Pi status information for UI display"""
    try:
        # Get latest status from queue
        latest_status = None
        while not pi_status_queue.empty():
            try:
                latest_status = pi_status_queue.get_nowait()
            except queue.Empty:
                break
        
        if latest_status:
            status_text = f"""
## 📡 Raspberry Pi Connection Status

**Connection Status:** {'✅ Connected' if latest_status['pi_connected'] else '❌ Disconnected'}
**Pi IP Address:** {latest_status['pi_ip'] or 'Not configured'}
**Last Check:** {latest_status['timestamp']}

### Message Delivery Status:
- **IoT Hub:** {'✅ Sent' if latest_status['iot_hub_sent'] else '❌ Failed'}
- **External API:** {'✅ Sent' if latest_status['api_sent'] else '❌ Failed'}

{f"**Errors:** {', '.join(latest_status['errors'])}" if latest_status['errors'] else ""}
"""
            return status_text
        else:
            # Get current status without sending
            connection_manager = get_connection_manager()
            if connection_manager:
                pi_available = connection_manager.check_raspberry_pi_availability()
                config = load_config()
                pi_config = config.get('raspberry_pi', {}) if config else {}
                configured_ip = pi_config.get('auto_detected_ip')
                
                return f"""
## 📡 Raspberry Pi Connection Status

**Connection Status:** {'✅ Connected' if pi_available else '❌ Disconnected'}
**Pi IP Address:** {configured_ip or 'Not configured'}
**Last Check:** {datetime.now().isoformat()}

*Status reporting active in background*
"""
            else:
                return "## 📡 Pi Status: Connection manager not available"
                
    except Exception as e:
        logger.error(f"Error getting Pi status info: {e}")
        return f"## 📡 Pi Status: Error - {str(e)}"

def process_barcode_scan(barcode, device_id=None):
    """Simplified barcode scanning with automatic device registration"""
    # Input validation
    if not barcode or not barcode.strip():
        blink_led("red")
        return "❌ Please enter a barcode."
    
    barcode = barcode.strip()
    
    # Auto-generate device ID if not provided
    if not device_id or not device_id.strip():
        mac_address = get_local_mac_address()
        if mac_address:
            device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
            logger.info(f"🔧 Auto-generated device ID: {device_id}")
        else:
            device_id = f"auto-{int(time.time())}"
            logger.warning(f"⚠️ Using fallback device ID: {device_id}")
    else:
        device_id = device_id.strip()

    logger.info(f"📱 Processing barcode scan: {barcode} from device: {device_id}")

    # Check Raspberry Pi connection first
    from utils.connection_manager import get_connection_manager
    connection_manager = get_connection_manager()
    pi_available = connection_manager.check_raspberry_pi_availability()
    
    if not pi_available:
        logger.warning("❌ Raspberry Pi not connected - saving message locally")
        try:
            # Save scan to local database for retry when Pi is available
            timestamp = datetime.now(timezone.utc)
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            
            # Save as unsent message for retry
            message_data = {
                "deviceId": device_id,
                "barcode": barcode,
                "timestamp": timestamp.isoformat(),
                "quantity": 1,
                "messageType": "barcode_scan"
            }
            local_db.save_unsent_message(device_id, json.dumps(message_data), timestamp)
            
            blink_led("red")
            return f"""❌ **Operation Failed: Raspberry Pi Not Connected**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** Saved locally - will send when Pi reconnects
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

Please ensure the Raspberry Pi device is connected and reachable on the network.

🔴 Red LED indicates Pi connection failure"""
        except Exception as e:
            logger.error(f"❌ Error saving barcode locally: {e}")
            blink_led("red")
            return f"❌ Error: Could not save barcode. {str(e)[:100]}"

    try:
        # Save scan to local database
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"💾 Saved barcode scan locally: {barcode}")
        
        # Use connection manager for consistent Pi checking and message handling
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        
        # Use connection manager's send_message_with_retry which handles Pi checks automatically
        success, status_message = connection_manager.send_message_with_retry(
            device_id=device_id,
            barcode=barcode,
            quantity=1,
            message_type="barcode_scan"
        )
        
        if success:
            blink_led("green")
            return f"""✅ **Barcode Scan Successful**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** {status_message}
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🟢 Green LED indicates successful operation"""
        else:
            # Message was saved locally due to Pi/connectivity issues
            blink_led("red")
            return f"""⚠️ **Warning: Message Saved Locally**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** {status_message}
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🔴 Red LED indicates offline operation"""
                
    except Exception as e:
        logger.error(f"❌ Barcode scan error: {e}")
        blink_led("red")
        return f"""❌ **Barcode Scan Failed**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Error:** {str(e)[:100]}

🔴 Red LED indicates error"""

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

@require_pi_connection
def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them to IoT Hub
    OPTIMIZED VERSION: Uses batch processing, connection caching, and reduced database calls
    
    Args:
        auto_retry (bool): If True, runs in background mode without returning status messages
        
    Returns:
        str: Status message if not in auto_retry mode, None otherwise
    """
    try:
        # Check if Raspberry Pi is connected first (highest priority)
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        if not connection_manager.check_raspberry_pi_availability():
            status_msg = "⚠️ **Warning: Raspberry Pi is not connected**\n\nCannot process unsent messages when the Raspberry Pi device is offline. Please ensure the Pi is connected and reachable on the network."
            logger.warning("Cannot process unsent messages - Raspberry Pi not connected")
            return None if auto_retry else status_msg
            
        # Check if we're online
        if not api_client.is_online():
            status_msg = "Device is offline. Cannot process unsent messages."
            logger.info(status_msg)
            return None if auto_retry else status_msg
            
        # Get unsent messages from local database
        unsent_messages = local_db.get_unsent_scans()
        if not unsent_messages:
            status_msg = "No unsent messages to process."
            logger.info(status_msg)
            return None if auto_retry else status_msg
            
        # Load configuration once
        config = load_config()
        if not config:
            return "Error: Failed to load configuration"
            
        iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
        if not iot_hub_connection_string:
            return "Error: No IoT Hub connection string found in configuration"

        registration_service = get_dynamic_registration_service(iot_hub_connection_string)
        if not registration_service:
            return "Error: Failed to initialize dynamic registration service"
        
        # OPTIMIZATION 1: Group messages by device_id to reduce registration calls
        messages_by_device = {}
        test_message_ids = []
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["barcode"]
            
            # Check if this is a test barcode - collect IDs for batch marking
            if api_client.is_test_barcode(barcode):
                logger.info(f"Skipping test barcode in unsent messages: {barcode} - BLOCKED from IoT Hub")
                test_message_ids.append(message.get("id"))
                continue
            
            if device_id not in messages_by_device:
                messages_by_device[device_id] = []
            messages_by_device[device_id].append(message)
        
        # OPTIMIZATION 2: Batch mark test barcodes as sent
        if test_message_ids:
            local_db.mark_multiple_sent_by_ids(test_message_ids)
            logger.info(f"Batch marked {len(test_message_ids)} test barcodes as sent")
        
        # OPTIMIZATION 3: Cache connection strings and HubClients per device
        device_clients = {}
        success_count = len(test_message_ids)  # Count test barcodes as successful
        fail_count = 0
        successful_message_ids = []
        
        # Process messages grouped by device
        for device_id, device_messages in messages_by_device.items():
            try:
                # Generate device connection string once per device
                if device_id not in device_clients:
                    device_connection_string = registration_service.register_device_with_azure(device_id)
                    if not device_connection_string:
                        logger.error(f"Failed to get connection string for device {device_id}")
                        fail_count += len(device_messages)
                        continue
                    
                    # Create and cache HubClient for this device
                    device_clients[device_id] = HubClient(device_connection_string)
                
                message_client = device_clients[device_id]
                
                # OPTIMIZATION 4: Process messages in smaller batches to avoid timeouts
                batch_size = 10  # Process 10 messages at a time per device
                for i in range(0, len(device_messages), batch_size):
                    batch = device_messages[i:i + batch_size]
                    batch_successful_ids = []
                    
                    for message in batch:
                        barcode = message["barcode"]
                        quantity = message.get("quantity", 1)
                        
                        # Send message to IoT Hub
                        success = message_client.send_message(barcode, device_id)
                        
                        if success:
                            batch_successful_ids.append(message.get("id"))
                            success_count += 1
                        else:
                            fail_count += 1
                    
                    # OPTIMIZATION 5: Batch mark successful messages as sent
                    if batch_successful_ids:
                        local_db.mark_multiple_sent_by_ids(batch_successful_ids)
                        successful_message_ids.extend(batch_successful_ids)
                        logger.debug(f"Batch marked {len(batch_successful_ids)} messages as sent for device {device_id}")
                
            except Exception as device_error:
                logger.error(f"Error processing messages for device {device_id}: {device_error}")
                fail_count += len(device_messages)
                continue
        
        # Clean up HubClient connections
        for client in device_clients.values():
            try:
                if hasattr(client, 'disconnect'):
                    client.disconnect()
            except Exception as cleanup_error:
                logger.debug(f"Error cleaning up client connection: {cleanup_error}")
        
        total_processed = len(unsent_messages)
        result_msg = f"Processed {total_processed} unsent messages. Success: {success_count}, Failed: {fail_count}"
        logger.info(result_msg)
        
        if not auto_retry:
            return result_msg
        return None
        
    except Exception as e:
        error_msg = f"Error processing unsent messages: {str(e)}"
        logger.error(error_msg)
        if not auto_retry:
            return error_msg
        return None

def refresh_pi_connection():
    """Refresh Raspberry Pi connection status and return updated display."""
    logger.info("🔄 Refreshing Raspberry Pi connection...")
    
    # Check connection
    connected = check_raspberry_pi_connection()
    
    # Get updated status display
    status_display = get_pi_connection_status_display()
    
    if connected:
        blink_led("green")
        logger.info("✅ Connection refresh successful")
    else:
        blink_led("red")
        logger.warning("❌ Connection refresh failed")
    
    return status_display

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
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        
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
            
            gr.Markdown("### Two-Step Registration Process")
            with gr.Row():
                scan_test_barcode_button = gr.Button("1. Scan Any Test Barcode (Dynamic)", variant="primary")
                confirm_registration_button = gr.Button("2. Confirm Registration", variant="primary")
                
            # Automatic status displays - no manual buttons needed
            gr.Markdown("### Automatic Message Processing Status")
            unsent_status_display = gr.Markdown("🔄 **Loading automatic status...**")
            
            gr.Markdown("### Pi Connection Status")
            pi_status_display = gr.Markdown("🔄 **Checking Pi status...**")
            
            status_text = gr.Markdown("")
            
            
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
    

    
    # Auto-refresh status displays every 10 seconds
    def refresh_status_displays():
        """Refresh all status displays automatically"""
        unsent_status = get_unsent_messages_status()
        pi_status = get_pi_status_info()
        return unsent_status, pi_status
    
    # Initial load of status displays
    app.load(
        fn=refresh_status_displays,
        inputs=[],
        outputs=[unsent_status_display, pi_status_display]
    )
    
    # Manual refresh button for immediate status check
    refresh_button = gr.Button("🔄 Refresh Status", variant="secondary")
    refresh_button.click(
        fn=refresh_status_displays,
        inputs=[],
        outputs=[unsent_status_display, pi_status_display]
    )
    
# Initialize device and auto-register on startup
logger.info("🚀 Initializing automatic device registration...")
check_raspberry_pi_connection()
auto_register_device_to_server()
logger.info(f"✅ Device ready for barcode scanning")

# Start Pi status monitoring thread
logger.info("🚀 Starting Pi status monitoring...")
pi_status_thread = threading.Thread(target=pi_status_monitor, daemon=True)
pi_status_thread.start()
logger.info("✅ Pi status monitoring active - will report to IoT Hub and API")

if __name__ == "__main__":
    # Initialize connection manager without Pi detection
    logger.info("🚀 Starting Barcode Scanner API in local mode...")
    connection_manager = get_connection_manager()
    logger.info("✅ Connection manager initialized for local operation")
    
    # Auto IP detection disabled - using local MAC address mode
    logger.info("✅ Local MAC address mode active - no network discovery needed")
    
    app.launch(server_name="0.0.0.0", server_port=7861)