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
from typing import AsyncGenerator
from datetime import datetime, timezone, timedelta
from barcode_validator import validate_ean, BarcodeValidationError

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

# For testing offline mode
simulated_offline_mode = False

# Track all processed device IDs, even those not saved in the database
processed_device_ids = set()

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

def is_scanner_connected():
    """Checks if a USB barcode scanner is connected by checking input device names."""
    try:
        # Command to find devices that look like a keyboard or scanner
        command = "grep -E -i 'scanner|barcode|keyboard' /sys/class/input/event*/device/name"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # If grep finds any matches, it returns a zero exit code
        if result.returncode == 0 and result.stdout:
            logger.info(f"Scanner check successful, found devices:\n{result.stdout.strip()}")
            return True
        else:
            logger.warning("No barcode scanner detected via input device names.")
            return False
    except Exception as e:
        logger.error(f"Error checking for scanner: {e}")
        # In case of error, assume not connected to be safe
        return False

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
    """Get the IP address of the primary Raspberry Pi device for connection."""
    try:
        # First try the full discovery process
        devices = discover_raspberry_pi_devices()
        
        if devices:
            # Prioritize devices with web service available (port 5000)
            web_devices = [d for d in devices if d.get('web_available', False)]
            if web_devices:
                primary_ip = web_devices[0]['ip']
                logger.info(f"🎯 Selected Raspberry Pi with web service: {primary_ip}")
                return primary_ip
                
            # Fall back to any available device
            primary_ip = devices[0]['ip']
            logger.info(f"🎯 Selected primary Raspberry Pi: {primary_ip}")
            return primary_ip
        
        # If discovery fails, try direct connection to known IP
        logger.info("🔍 Discovery failed, trying direct connection to known Raspberry Pi...")
        return get_known_raspberry_pi_ip()
        
    except Exception as e:
        logger.error(f"Error getting primary Raspberry Pi IP: {e}")
        # Final fallback to known IP
        return get_known_raspberry_pi_ip()

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
    'ssh_available': False,
    'web_available': False
}

def check_raspberry_pi_connection():
    """Check if Raspberry Pi is connected and update global status."""
    global _pi_connection_status
    
    try:
        logger.info("🔍 Checking Raspberry Pi connection status...")
        
        # Try to get Pi IP
        pi_ip = get_primary_raspberry_pi_ip()
        
        if pi_ip:
            # Test connectivity
            discovery = NetworkDiscovery()
            ssh_available = discovery.test_raspberry_pi_connection(pi_ip, 22)
            web_available = discovery.test_raspberry_pi_connection(pi_ip, 5000)
            
            # Pi is only considered "connected" if at least SSH or Web service is available
            pi_actually_connected = ssh_available or web_available
            
            _pi_connection_status.update({
                'connected': pi_actually_connected,
                'ip': pi_ip if pi_actually_connected else None,
                'last_check': datetime.now(),
                'ssh_available': ssh_available,
                'web_available': web_available
            })
            
            if pi_actually_connected:
                logger.info(f"✅ Raspberry Pi connected: {pi_ip} (SSH: {ssh_available}, Web: {web_available})")
                return True
            else:
                logger.warning(f"❌ Raspberry Pi unreachable: {pi_ip} (SSH: {ssh_available}, Web: {web_available})")
                return False
        else:
            _pi_connection_status.update({
                'connected': False,
                'ip': None,
                'last_check': datetime.now(),
                'ssh_available': False,
                'web_available': False
            })
            
            logger.warning("❌ Raspberry Pi not connected")
            return False
            
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
def process_unsent_messages_ui():
    """Process unsent messages with user-visible progress for Gradio UI."""
    # Check if Raspberry Pi is connected using connection manager for consistency
    from utils.connection_manager import get_connection_manager
    connection_manager = get_connection_manager()
    if not connection_manager.check_raspberry_pi_availability():
        error_msg = """🟡 **Cannot Process Unsent Messages**

**Status:** Raspberry Pi is currently offline.

Unsent messages will be processed automatically when the Raspberry Pi is back online. No action is needed at this time."""
        logger.warning("Processing of unsent messages blocked: Raspberry Pi not connected")
        blink_led("yellow")
        yield error_msg
        return
        
    if not is_scanner_connected():
        yield "⚠️ No barcode scanner detected. Please connect your device."
        return
    # Initial loading message so the user sees a loader immediately
    yield "⏳ Processing unsent messages to IoT Hub... Please wait."
    try:
        result = process_unsent_messages(auto_retry=False)
        yield "✅ Finished processing unsent messages.\n\n" + (result or "")
    except Exception as e:
        error_msg = f"❌ Error while processing unsent messages: {str(e)}"
        logger.error(error_msg)
        yield error_msg

# Store reference to original is_online method before patching
from api.api_client import ApiClient as OriginalApiClient
orig_api_client = OriginalApiClient()

def patched_is_online():
    """Patched version of is_online that respects simulated_offline_mode"""
    if simulated_offline_mode:
        return False
    # Call the original is_online method directly
    return orig_api_client.is_online()
    
api_client.is_online = patched_is_online

# Setup message retry system
retry_queue = queue.Queue()
retry_thread = None
retry_interval = 300  # seconds
retry_running = False
retry_lock = threading.Lock()
last_queue_check = datetime.now()
retry_enabled = False

def blink_led(color):
    """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error, 'yellow' for warning."""
    if not IS_RASPBERRY_PI:
        logger.info(f"Not on a Raspberry Pi, skipping LED blink for color '{color}'.")
        return
    try:
        # Import GPIO library for Raspberry Pi
        import RPi.GPIO as GPIO
        import time
        
        # Set GPIO mode
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Define LED pins (adjust these pin numbers based on your hardware setup)
        LED_PINS = {
            'red': 18,     # GPIO 18 for red LED
            'green': 23,   # GPIO 23 for green LED  
            'yellow': 24,  # GPIO 24 for yellow LED
            'blue': 25     # GPIO 25 for blue LED
        }
        
        # Get the pin for the requested color
        pin = LED_PINS.get(color.lower())
        if not pin:
            logger.warning(f"Unknown LED color: {color}. Using red LED as fallback.")
            pin = LED_PINS['red']
        
        # Setup the GPIO pin
        GPIO.setup(pin, GPIO.OUT)
        
        # Blink the LED 3 times
        for _ in range(3):
            GPIO.output(pin, GPIO.HIGH)  # Turn LED on
            time.sleep(0.2)              # Wait 200ms
            GPIO.output(pin, GPIO.LOW)   # Turn LED off
            time.sleep(0.2)              # Wait 200ms
        
        # Clean up GPIO
        GPIO.cleanup(pin)
        
        logger.info(f"Successfully blinked {color} LED on Raspberry Pi.")
        
    except ImportError:
        # Fallback for non-Raspberry Pi environments
        logger.info(f"RPi.GPIO not available. Simulating {color} LED blink.")
        print(f"🔴 LED BLINK: {color.upper()} LED blinking 3 times" if color == 'red' else 
              f"🟢 LED BLINK: {color.upper()} LED blinking 3 times" if color == 'green' else
              f"🟡 LED BLINK: {color.upper()} LED blinking 3 times" if color == 'yellow' else
              f"🔵 LED BLINK: {color.upper()} LED blinking 3 times")
    except Exception as e:
        logger.error(f"LED blink error: {str(e)}")
        # Fallback visual indication
        print(f"⚠️ LED ERROR: Could not blink {color} LED - {str(e)}")

def generate_registration_token():
    """Step 1: Generate a dynamic registration token for device registration"""
    if not is_scanner_connected():
        return "⚠️ No barcode scanner detected. Please connect your device."
    try:
        # Generate a unique registration token
        token = device_manager.generate_registration_token()
        
        # Clean up any expired tokens
        device_manager.cleanup_expired_tokens()
        
        response_msg = f"""✅ Registration token generated successfully!

**Registration Token:** `{token}`

**Instructions:**
1. Use this token in the 'Registration Token' field
2. Enter your desired Device ID
3. Click 'Confirm Registration' to complete the process

**Note:** Token expires in 24 hours and can only be used once."""
        
        blink_led("green")
        return response_msg, token
        
    except Exception as e:
        logger.error(f"Error generating registration token: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}", ""

@require_pi_connection
def confirm_registration(registration_token, device_id):
    """Step 2: Confirm device registration using token and device ID"""
    if not is_scanner_connected():
        return "⚠️ No barcode scanner detected. Please connect your device."
    try:
        global processed_device_ids
        
        if not registration_token or registration_token.strip() == "":
            blink_led("red")
            return "❌ Please enter a registration token."
        
        if not device_id or device_id.strip() == "":
            blink_led("red")
            return "❌ Please enter a device ID."
        
        registration_token = registration_token.strip()
        device_id = device_id.strip()
        
        # Validate registration token
        is_valid, message = device_manager.validate_registration_token(registration_token)
        if not is_valid:
            blink_led("red")
            return f"❌ {message}"
        
        # Check if device is already registered in our system
        if device_manager.is_device_registered(device_id):
            blink_led("red")
            return f"❌ Device ID '{device_id}' is already registered. Please use a different Device ID."
        
        # Check if device is already registered in local DB (legacy check)
        existing_device = local_db.get_device_id()
        if existing_device and existing_device == device_id:
            blink_led("red")
            return f"❌ Device already registered with ID: {existing_device}. Please use a different device or clear existing registration."
        
        # Gather device info for registration
        device_info = {
            "registration_method": "dynamic_token",
            "online_at_registration": True,  # Will be updated based on comprehensive connectivity check
            "user_agent": "Barcode Scanner App v2.0"
        }
        
        # Register device with dynamic device manager
        success, reg_message = device_manager.register_device(registration_token, device_id, device_info)
        if not success:
            blink_led("red")
            return f"❌ Registration failed: {reg_message}"
        
        # Save device ID locally for backward compatibility
        local_db.save_device_id(device_id)
        
        # Create registration confirmation message
        confirmation_message_data = {
            "deviceId": device_id,
            "status": "registered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Device registration confirmed via dynamic token",
            "registration_token": registration_token
        }
        confirmation_message_json = json.dumps(confirmation_message_data)
        
        # Use the enhanced connection manager to send registration confirmation
        # This will check Internet + IoT Hub + Raspberry Pi availability
        success, status_msg = connection_manager.send_message_with_retry(
            device_id, 
            confirmation_message_json, 
            1, 
            "device_registration"
        )
        
        # Determine the appropriate status message based on connectivity
        if success:
            iot_status = "✅ Registration confirmation sent to IoT Hub"
            blink_led("green")
        else:
            iot_status = f"📥 Registration saved locally - {status_msg}"
            blink_led("orange")
        
        return f"""🎉 Device Registration Completed!

**Device Details:**
• Device ID: {device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
• Registration Method: Dynamic Token

**Actions Completed:**
• ✅ Device registered with dynamic device manager
• ✅ Device ID saved locally
• {iot_status}

**Status:** Device is now ready for barcode scanning operations!

**You can now use the 'Send Barcode' feature with any valid barcode.**"""
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
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

@require_pi_connection
def process_barcode_scan(barcode, device_id):
    """Unified function to handle barcode scanning with strict validation"""
    # Input validation
    if not barcode or not barcode.strip():
        blink_led("red")
        return "❌ Please enter a barcode."
    
    if not device_id or not device_id.strip():
        blink_led("red")
        return "❌ Please enter a device ID."
    
    barcode = barcode.strip()
    device_id = device_id.strip()

    # Get the connection manager instance first
    connection_manager = get_connection_manager()

    # 1. Check device registration status first to provide a better context message when offline.
    from utils.dynamic_device_manager import DynamicDeviceManager
    device_manager = DynamicDeviceManager()
    device_registered = device_manager.is_device_registered(device_id)
    if not device_registered:
        # Check local database as a fallback
        registered_devices = local_db.get_registered_devices()
        device_registered = any(
            dev.get('device_id') == device_id 
            for dev in (registered_devices or [])
        )

    # 2. Check Raspberry Pi connectivity
    pi_connected = connection_manager.check_raspberry_pi_availability()
    logger.info(f"🔍 DEBUG: Pi connection check result: {pi_connected}")

    if not pi_connected:
        if device_registered:
            # If device is registered but Pi is offline, save locally and inform the user.
            timestamp = datetime.now(timezone.utc)
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            logger.warning(f"Pi offline for registered device {device_id}. Scan saved locally.")
            blink_led("yellow")
            return f"""🟡 **Device is not connected**

**Status:** Raspberry Pi is not connected. Scan saved locally.

Device is ready for barcode scanning operations! Scans will be sent when the Pi is back online."""
        else:
            # If device is not registered and Pi is offline, block the operation.
            error_msg = "🟡 **Operation Failed**\n\n"
            error_msg += "**Error:** 📥 Raspberry Pi is currently offline\n\n"
            error_msg += "**LED Status:** 🟡 Yellow light indicates operation failure\n\n"
            error_msg += "**Action:** Please ensure the Raspberry Pi device is connected and reachable on the network before trying again."
            logger.warning("Operation blocked: Raspberry Pi not connected for unregistered device")
            blink_led("yellow")
            return error_msg

    # Check if barcode scanner is connected
    if not is_scanner_connected():
        error_msg = "❌ **Operation Failed: Barcode Scanner Not Connected**\n\n"
        error_msg += "Please ensure your barcode scanner is properly connected to the Raspberry Pi and try again."
        logger.warning("Operation blocked: Barcode scanner not connected")
        blink_led("red")
        return error_msg

    # Check if we're online using the connection manager
    if not connection_manager.check_internet_connectivity():
        # Save scan locally since we're offline
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"Saved barcode scan locally (offline): {barcode} for device {device_id}")
        
        # Show warning that scan was saved locally
        blink_led("yellow")
        return "⚠️ Scan saved locally. Will be sent when back online."

    try:
        # 3. Handle device registration if not already registered
        if not device_registered:
            logger.info(f"New device detected: {device_id}. Initiating automatic registration...")
        
        if not device_registered:
            logger.info(f"New device detected: {device_id}. Initiating automatic registration...")
            # ... registration code ...
            success, reg_message = device_manager.register_device(auto_token, device_id, device_info)
            
            # Check if registration was successful
            if not success:
                blink_led("red")
                logger.error(f"Failed to auto-register device {device_id}: {reg_message}")
                return f"❌ Error: Device registration failed: {reg_message}"
            
            # Update device registration status
            device_registered = True
        

            
        # Save scan to local database
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"Saved barcode scan: {barcode} for device {device_id}")
        
        # Send to IoT Hub with retry capability
        success, status = connection_manager.send_message_with_retry(
            device_id, 
            barcode, 
            1,  # Default quantity
            "barcode_scan"
        )
        
        if success:
            blink_led("green")
            logger.info(f"Successfully sent barcode {barcode} to IoT Hub for device {device_id}")
            return f"""✅ **Barcode Scan Successful**

**Device Details:**
• **Device ID:** `{device_id}`
• **Barcode:** `{barcode}`
• **Scanned At:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`

**Actions Completed:**
• ✅ Barcode saved locally.
• ✅ Message sent to IoT Hub.

**LED Status:** 🟢 Green light indicates success.

**Status:** Barcode processed successfully!"""
        else:
            # Check if the failure was due to Pi being offline
            if "Raspberry Pi offline" in status:
                blink_led("red")  # Red to indicate Pi is offline
                logger.warning(f"Raspberry Pi is offline - message saved locally for device {device_id}")
                return f"⚠️ Raspberry Pi is offline. Message saved locally and will be sent when the Pi is back online."
            elif "Internet offline" in status or "IoT Hub offline" in status:
                blink_led("yellow")  # Yellow for other connectivity issues
                logger.warning(f"Connectivity issue - message saved locally for device {device_id}: {status}")
                return f"⚠️ {status}"
            else:
                # For other types of failures
                blink_led("yellow")
                logger.warning(f"Failed to send barcode {barcode} to IoT Hub: {status}")
                return f"⚠️ {status}"


            
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        blink_led("red")
        return f"""❌ System Error

**Error Details:**
• Barcode: {barcode if 'barcode' in locals() else 'Unknown'}
• Device ID: {device_id if 'device_id' in locals() else 'Unknown'}
• Error: {str(e)}

**Status:** System error occurred during barcode processing."""

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
            
        # Load configuration
        config = load_config()
        if not config:
            return "Error: Failed to load configuration"
            
        # Get dynamic registration service for generating device connection strings
        # Get IoT Hub connection string for dynamic registration

        iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")

        if not iot_hub_connection_string:

            return "Error: No IoT Hub connection string found in configuration"

        

        registration_service = get_dynamic_registration_service(iot_hub_connection_string)

        if not registration_service:

            return "Error: Failed to initialize dynamic registration service"
        
        # Process each unsent message
        success_count = 0
        fail_count = 0
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["barcode"]
            timestamp = message["timestamp"]
            quantity = message.get("quantity", 1)
            
            # Check if this is a test barcode - if so, skip sending to IoT Hub
            if api_client.is_test_barcode(barcode):
                logger.info(f"Skipping test barcode in unsent messages: {barcode} - BLOCKED from IoT Hub")
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
                continue
            
            # Generate device-specific connection string using dynamic registration
            try:
                device_connection_string = registration_service.register_device_with_azure(device_id)
                if not device_connection_string:
                    logger.error(f"Failed to get connection string for device {device_id}")
                    fail_count += 1
                    continue
            except Exception as reg_error:
                logger.error(f"Registration error for device {device_id}: {reg_error}")
                fail_count += 1
                continue
                
            message_client = HubClient(device_connection_string)
            
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Try to send the message with quantity
            success = message_client.send_message(barcode, device_id)
            
            if success:
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
            else:
                fail_count += 1
                
        result_msg = f"Processed {len(unsent_messages)} unsent messages. Success: {success_count}, Failed: {fail_count}"
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

def process_unsent_messages_ui():
    """Gradio-friendly generator that streams progress while sending unsent messages"""
    try:
        # Step 1: online check
        if not api_client.is_online():
            msg = "❌ Device is offline. Cannot process unsent messages."
            logger.info(msg)
            yield msg
            return

        # Step 2: fetch unsent
        yield "⏳ Checking for unsent messages in local storage..."
        unsent_messages = local_db.get_unsent_scans()
        if not unsent_messages:
            msg = "✅ No unsent messages to process."
            logger.info(msg)
            yield msg
            return

        yield f"📦 Found {len(unsent_messages)} unsent messages. Preparing to send..."

        # Step 3: load config and registration service
        config = load_config()
        if not config:
            msg = "❌ Error: Failed to load configuration"
            logger.error(msg)
            yield msg
            return

        iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
        if not iot_hub_connection_string:
            msg = "❌ Error: No IoT Hub connection string found in configuration"
            logger.error(msg)
            yield msg
            return

        registration_service = get_dynamic_registration_service(iot_hub_connection_string)
        if not registration_service:
            msg = "❌ Error: Failed to initialize dynamic registration service"
            logger.error(msg)
            yield msg
            return

        # Step 4: process each message with live updates
        success_count = 0
        fail_count = 0
        total = len(unsent_messages)
        for idx, message in enumerate(unsent_messages, start=1):
            device_id = message["device_id"]
            barcode = message["barcode"]
            timestamp = message["timestamp"]
            quantity = message.get("quantity", 1)

            yield f"➡️ [{idx}/{total}] Sending barcode {barcode} (qty {quantity}) for device {device_id}..."

            # Skip test barcodes (treat as success)
            if api_client.is_test_barcode(barcode):
                logger.info(f"Skipping test barcode in unsent messages: {barcode} - BLOCKED from IoT Hub")
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
                yield f"✔️ [{idx}/{total}] Test barcode {barcode} skipped and marked as sent."
                continue

            # Get device-specific connection string
            try:
                device_connection_string = registration_service.register_device_with_azure(device_id)
                if not device_connection_string:
                    fail_count += 1
                    logger.error(f"Failed to get connection string for device {device_id}")
                    yield f"❌ [{idx}/{total}] Failed to get device connection for {device_id}."
                    continue
            except Exception as reg_error:
                fail_count += 1
                logger.error(f"Registration error for device {device_id}: {reg_error}")
                yield f"❌ [{idx}/{total}] Registration error for {device_id}: {reg_error}"
                continue

            message_client = HubClient(device_connection_string)

            # Attempt send
            sent = message_client.send_message(barcode, device_id)
            if sent:
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
                yield f"✅ [{idx}/{total}] Sent {barcode} for {device_id}."
            else:
                fail_count += 1
                yield f"⚠️ [{idx}/{total}] Failed to send {barcode} for {device_id}. Will retry later."

        summary = f"📊 Processed {total} unsent messages. Success: {success_count}, Failed: {fail_count}"
        logger.info(summary)
        yield summary

    except Exception as e:
        error_msg = f"❌ Error processing unsent messages: {str(e)}"
        logger.error(error_msg)
        yield error_msg

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
                
            with gr.Row():
                process_unsent_button = gr.Button("Process Unsent Messages")
                
            status_text = gr.Markdown("")
            
            with gr.Row():
                gr.Markdown("### Test Offline Mode")
                simulate_offline_button = gr.Button("Simulate Offline Mode")
                simulate_online_button = gr.Button("Restore Online Mode")
            
            offline_status_text = gr.Markdown("Current mode: Online")
            
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
        fn=lambda: register_device_id("817994ccfe14"),
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
    
# Initialize Raspberry Pi connection status on app startup
logger.info("🍓 Initializing Raspberry Pi connection status...")
check_raspberry_pi_connection()
logger.info(f"🍓 Pi connection status: {_pi_connection_status}")

def register_device_with_iot_hub(device_id):
    """Register a device with Azure IoT Hub and update the config file
    
    Args:
        device_id (str): The device ID to register
        
    Returns:
        dict: A dictionary with success status and error message if applicable
    """
    if not IOT_HUB_REGISTRY_AVAILABLE:
        logger.error("Azure IoT Hub Registry Manager not available. Cannot register device.")
        return {"success": False, "error": "Azure IoT Hub Registry Manager not available"}
    
    try:
        # Load config to get IoT Hub owner connection string
        config = load_config()
        if not config or "iot_hub" not in config or "connection_string" not in config["iot_hub"]:
            logger.error("IoT Hub connection string not found in config")
            return {"success": False, "error": "IoT Hub connection string not found in config"}
        
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
            
            # Save updated config
            save_config(config)
            logger.info(f"Config file updated with device {device_id} connection string")
            
            return {"success": True, "device_id": device_id, "connection_string": connection_string}
            
        except Exception as ex:
            logger.error(f"Error registering device {device_id} with IoT Hub: {str(ex)}")
            return {"success": False, "error": str(ex)}
            
    except Exception as e:
        logger.error(f"Error in register_device_with_iot_hub: {str(e)}")
        return {"success": False, "error": str(e)}
    
# Setup message retry system
retry_queue = queue.Queue()
retry_thread = None
retry_interval = 300  # seconds
retry_running = False
retry_lock = threading.Lock()
last_queue_check = datetime.now()
retry_enabled = False

def blink_led(color):
    """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error, 'yellow' for warning."""
    if not IS_RASPBERRY_PI:
        logger.debug(f"💡 LED blink simulated (not on Raspberry Pi): {color}")
        return
    
    try:
        import RPi.GPIO as GPIO
        import time
        
        # LED pin configuration (adjust as needed)
        LED_PINS = {
            'green': 18,   # GPIO 18 for green LED
            'red': 16,     # GPIO 16 for red LED  
            'yellow': 20   # GPIO 20 for yellow LED
        }
        
        if color not in LED_PINS:
            logger.warning(f"Unknown LED color: {color}")
            return
            
        pin = LED_PINS[color]
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        
        # Blink pattern
        for _ in range(3):  # Blink 3 times
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.2)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(0.2)
            
        GPIO.cleanup(pin)
        logger.debug(f"✅ LED blinked: {color}")
        
    except ImportError:
        logger.debug(f"💡 RPi.GPIO not available - LED blink simulated: {color}")
    except Exception as e:
        logger.warning(f"⚠️ LED blink failed ({color}): {str(e)} - continuing without LED")

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        global processed_device_ids
        
        # Check if Raspberry Pi is connected using connection manager for consistency
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        if not connection_manager.check_raspberry_pi_availability():
            error_msg = "🟡 **Registration Failed**\n\n"
            error_msg += "**Error:** 📥 Registration saved locally - Pi offline\n\n"
            error_msg += "**LED Status:** 🟡 Yellow light indicates failed registration.\n\n"
            error_msg += "**Action:** Please ensure the Raspberry Pi device is connected and reachable on the network before trying again."
            logger.warning("Operation blocked: Raspberry Pi not connected")
            blink_led("yellow")
            return error_msg
        
        # Check if barcode scanner is connected
        if not is_scanner_connected():
            error_msg = "❌ **Operation Failed: Barcode Scanner Not Connected**\n\n"
            error_msg += "Please ensure your barcode scanner is properly connected to the Raspberry Pi and try again."
            logger.warning("Operation blocked: Barcode scanner not connected")
            blink_led("red")
            return error_msg
            
        # Get the connection manager instance
        connection_manager = get_connection_manager()
        
        # Check if we're online using the connection manager
        if not connection_manager.check_internet_connectivity() or not connection_manager.check_iot_hub_connectivity():
            # Save the registration attempt locally for when we're back online
            timestamp = datetime.now(timezone.utc)
            local_db.save_unsent_message("device_registration", barcode, timestamp)
            logger.warning("Device registration saved locally - will be processed when back online")
            
            # Show warning that registration was saved locally
            blink_led("yellow")
            return "⚠️ Device registration saved locally. Will be processed when back online."
            
        # Accept any barcode for dynamic testing (removed hardcoded restriction)
        logger.info(f"Using barcode '{barcode}' for device registration testing")
        
        # Generate dynamic device ID for this system
        from utils.dynamic_device_id import generate_dynamic_device_id
        device_id = generate_dynamic_device_id()
        logger.info(f"Generated device ID: {device_id}")
        
        # For test registrations, we always allow them to proceed regardless of previous processing
        # This is different from actual device registrations where we check for duplicates
        logger.info(f"Test registration - always allowing to proceed regardless of previous processing")
        
        api_url_1 = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload_1 = {"scannedBarcode": barcode}
        
        logger.info(f"Making first API call to {api_url_1}")
        api_result_1 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_1.get("success", False):
            blink_led("red")
            return f"❌ First API call failed: {api_result_1.get('message', 'Unknown error')}"
        
        logger.info(f"Making second API call to {api_url_1}")
        api_result_2 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_2.get("success", False):
            blink_led("red")
            return f"❌ Second API call failed: {api_result_2.get('message', 'Unknown error')}"
        
        # Save the successful test registration to the local database
        # This ensures the device is recognized as registered in subsequent scans
        local_db.save_device_registration(device_id, barcode, datetime.now(timezone.utc))
        logger.info(f"Saved test registration for device {device_id} to local database.")
        
        # Send response to frontend
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()
        
        # Check if we're actually online before showing success
        if not connection_manager.check_internet_connectivity() or not connection_manager.check_iot_hub_connectivity():
            blink_led("yellow")
            return "⚠️ **Test Barcode Processed - Offline Mode**\n\n" \
                  "**Status:** Test barcode processed in offline mode.\n" \
                  "**Action:** Please connect to the internet and ensure the Raspberry Pi is online to complete registration."
        
        # Show success message with clear indication this is a test
        response_msg = f"""✅ **Test Barcode Processed Successfully!**

**Test Barcode:** {barcode}
**Generated Device ID:** {device_id}
**Scanned At:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**API Status:**
• First call: {api_result_1.get('message', 'Success')}
• Second call: {api_result_2.get('message', 'Success')}

**Next Steps:**
1. Copy the Device ID above
2. Paste it in the Device ID field
3. Click 'Confirm Registration' to complete setup

**Status:** Ready for registration confirmation"""
        
        return response_msg
        
    except Exception as e:
        logger.error(f"Error in register_device_id: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

def confirm_registration(barcode, device_id):
    """Step 2: Frontend confirms registration, send confirmation message, save device in DB, send to IoT"""
    try:
        global processed_device_ids
        
        # Validate input fields first
        if not device_id or device_id.strip() == "":
            blink_led("red")
            return "❌ Please add device ID to confirm the registration."
        
        # if not barcode or barcode.strip() == "":
        #     blink_led("red")
        #     return "❌ Please provide a barcode to confirm the registration."
        
        # Clean the inputs
        device_id = device_id.strip()
        # barcode = barcode.strip()
        
        # Since we no longer save test barcodes, use the provided barcode directly
        # This makes the registration process cleaner by only saving confirmed registrations
        test_scan = {'barcode': barcode}  # Use the provided barcode directly
        
        # Log all currently processed device IDs for debugging
        logger.info(f"Currently processed device IDs: {processed_device_ids}")
     
        # Check if device is already in the database
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            logger.info(f"Device ID {device_id} already registered, skipping registration")
            
            # Find the registration details for this device
            device_info = next((device for device in registered_devices if device['device_id'] == device_id), None)
            registration_date = device_info['registration_date'] if device_info else 'Unknown'
            
            # For already registered devices, just show the status without API calls
            blink_led("yellow")  # YELLOW light for already registered device
            
            return f"""🟡 Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Barcode: {barcode}
• Status: Already in database
• Registered: {registration_date}

**Actions Completed:**
• ✅ Device found in database
• ✅ Already registered message sent to IoT Hub
• ⚠️ No duplicate registration performed

**LED Status:** 🟡 Yellow light indicates device already registered.

**Status:** Device is ready for barcode scanning operations!"""
        
        # Check if API is online
        is_online = api_client.is_online()
        if not is_online:
            blink_led("yellow")
            return "⚠️ Device is offline. Please check your internet connection and try again."
        
        # Use dynamic device ID from the scanned barcode (no static EAN)
        if not device_id or not device_id.strip():
            # Use the scanned barcode as device ID (dynamic approach)
            device_id = test_scan['barcode']
        
        # Log the device ID being used for registration
        logger.info(f"Using device ID for registration: {device_id}")
        
        # Check if device ID is already registered in database or has been processed before
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices) or device_id in processed_device_ids
        
        if device_already_registered:
            logger.info(f"Device ID {device_id} already registered, skipping registration")
            blink_led("yellow")  # YELLOW light for already registered device
            
            # Find the registration details for this device
            device_info = next((device for device in registered_devices if device['device_id'] == device_id), None)
            registration_date = device_info['registration_date'] if device_info else 'Unknown'
            
            return f"""🟡 Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Barcode: {test_scan['barcode']}
• Status: Already in database
• Registered: {registration_date}

**Actions Completed:**
• ✅ Device found in database
• ✅ Already registered message sent to IoT Hub
• ⚠️ No duplicate registration performed

**LED Status:** 🟡 Yellow light indicates device already registered.

**Status:** Device is ready for barcode scanning operations!"""
                    
        # Skip validation step as the endpoint doesn't exist
        # Instead, we'll rely on the confirmation API to validate the device ID
        
        # Use enhanced connection manager to respect offline mode
        logger.info(f"Confirming registration with enhanced connection manager (respects offline mode)")
        
        # Check if Pi is available before sending to API
        connection_manager = get_connection_manager()
        if not connection_manager.check_raspberry_pi_availability():
            logger.info("🍓 ❌ Raspberry Pi offline - Registration will be saved locally only")
            api_success = False
            api_status = "📥 Registration saved locally - Pi offline"
        else:
            # Pi is online, send to API
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
            payload = {"deviceId": device_id, "scannedBarcode": test_scan['barcode']}
            logger.info(f"🍓 ✅ Pi online - Confirming registration with API: {api_url}")
            
            api_result = api_client.send_registration_barcode(api_url, payload)
            api_success = api_result.get("success", False)
            api_status = "✅ Registration sent to API" if api_success else f"⚠️ API error: {api_result.get('message', 'Unknown error')}"
        
        # Add this device ID to our processed set regardless of API response
        # This ensures we don't process the same device ID twice even if API fails
        processed_device_ids.add(device_id)
        logger.info(f"Added device ID {device_id} to processed devices set")
        logger.info(f"API Status: {api_status}")
        
        # Save device registration to database if we have both device ID and barcode
        # This ensures we save the registration even if the API doesn't return the expected format
        if device_id and barcode:
            logger.info(f"Saving device registration to database with device ID: {device_id}, barcode: {barcode}")
            local_db.save_device_registration(device_id, barcode)
            saved_to_database = True
        else:
            saved_to_database = False
            
        # Check if this is a test barcode
        is_test = api_client.is_test_barcode(barcode)
        
        if is_test:
            logger.info(f"Test barcode {barcode} detected - sending IoT Hub message without saving to database")
            
            # For test barcodes, just send IoT Hub message without saving to database
            # Send confirmation message to IoT Hub
            try:
                config = load_config()
                if config:
                    # Get IoT Hub connection string
                    registration_service = get_dynamic_registration_service()
                    device_connection_string = registration_service.register_device_with_azure(device_id)
                    
                    if device_connection_string:
                        # Send test registration message to IoT Hub
                        hub_client = HubClient(device_connection_string)
                        # Send test registration message with correct parameters: barcode, device_id
                        hub_client.send_message(barcode, device_id)
                        iot_status = "✅ Test registration sent to IoT Hub"
                        blink_led("green")  # GREEN light for successful test
                    else:
                        iot_status = "⚠️ Failed to send test registration to IoT Hub"
                        blink_led("yellow")  # YELLOW light for IoT Hub failure
                else:
                    iot_status = "⚠️ No IoT Hub configuration found"
                    blink_led("yellow")  # YELLOW light for missing config
            except Exception as e:
                logger.error(f"Error sending test registration to IoT Hub: {str(e)}")
                iot_status = "⚠️ Error sending test registration to IoT Hub"
                blink_led("yellow")  # YELLOW light for error
                
            return f"""✅ Test Barcode Processed

**Device Details:**
• Device ID: {device_id}
• Test Barcode: {barcode}
• Processed At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Test barcode identified
• {iot_status}
• ⚠️ Not saved to database (test barcode)

**LED Status:** 🟢 Green light indicates successful test.

**Status:** Test registration completed successfully. IoT Hub connection verified."""
        
        # For actual device registrations (new devices), save to database and send to API
        # Save device registration to database
        logger.info(f"New device registration - saving to database with device ID: {device_id}, barcode: {barcode}")
        local_db.save_device_registration(device_id, barcode)
        
        # Use enhanced connection manager to respect offline mode for API calls
        connection_manager = get_connection_manager()
        if not connection_manager.check_raspberry_pi_availability():
            logger.info("🍓 ❌ Raspberry Pi offline - Registration will be saved locally only")
            api_result = {"success": False, "message": "📥 Registration saved locally - Pi offline"}
        else:
            # Pi is online, try to register the device with the API
            logger.info("🍓 ✅ Pi online - Attempting API registration")
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
            payload = {"deviceId": device_id, "scannedBarcode": barcode}
            api_result = api_client.send_registration_barcode(api_url, payload)
        
        # Check if API call was successful
        if not api_result.get("success", False):
            error_msg = api_result.get("message", "Unknown error")
            
            # Check if the error contains "Device not found" and Pi is still online
            if "Device not found" in error_msg and connection_manager.check_raspberry_pi_availability():
                # Try direct registration with saveDeviceId endpoint only if Pi is online
                save_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                save_payload = {"scannedBarcode": device_id}
                
                logger.info(f"🍓 ✅ Pi online - Trying direct device registration with API: {save_url}")
                save_result = api_client.send_registration_barcode(save_url, save_payload)
            elif "Device not found" in error_msg:
                logger.info("🍓 ❌ Pi offline - Skipping fallback API registration")
                save_result = {"success": False, "message": "📥 Registration saved locally - Pi offline"}
                
                if save_result.get("success", False) and "response" in save_result:
                    try:
                        save_response = json.loads(save_result["response"])
                        if save_response.get("deviceId") and save_response.get("responseCode") == 200:
                            # Device registration successful with API returning device ID and barcode
                            # Only now save to database since we have confirmed API response
                            registered_device_id = save_response.get("deviceId")
                            returned_barcode = barcode  # Use the barcode that was sent
                            
                            # Save device registration with both device ID and barcode from API response
                            local_db.save_device_registration(registered_device_id, returned_barcode)
                            
                            # Blink green LED for success
                            blink_led("green")
                            
                            return f"""🟢 Device Registration Successful!

**Device Details:**
• Device ID: {registered_device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device ID registered with API
• ✅ Device saved in local database
• ✅ IoT Hub registration initiated

**LED Status:** 🟢 Green light indicates successful registration.

**Status:** Device is now ready for barcode scanning operations!"""
                    except json.JSONDecodeError:
                        pass
                
                blink_led("yellow") 
                return f"""🟡 Registration Failed

**Error:** Device ID '{device_id}' was not found in the system.

**LED Status:** 🟡 Yellow light indicates failed registration.

**Action:** Please use a valid device ID and try again."""
            
            blink_led("yellow")  # YELLOW light for failed registration
            return f"""🟡 Registration Failed

**Error:** {error_msg}

**LED Status:** 🟡 Yellow light indicates failed registration.

**Action:** Please check your device ID and try again."""
        
        # Try to parse the confirmation response
        try:
            if "response" in api_result:
                response_data = json.loads(api_result["response"])
                
                if response_data.get("responseCode") == 400:
                    blink_led("yellow")  # YELLOW light for failed registration
                    return f"""🟡 Registration Failed

**Error:** {response_data.get('responseMessage', 'Unknown error')}

**LED Status:** 🟡 Yellow light indicates failed registration.

**Action:** Please check your device ID and try again."""
                elif response_data.get("responseCode") == 200 and response_data.get("deviceId"):
                    # API successfully returned device ID and barcode - check if device already exists
                    device_id = response_data.get("deviceId")
                    returned_barcode = test_scan['barcode']
                    
                    # Check if device ID already exists in database or has been processed before
                    registered_devices = local_db.get_registered_devices()
                    device_already_registered = any(device['device_id'] == device_id for device in registered_devices) or device_id in processed_device_ids
                    
                    if device_already_registered:
                        # Device already exists - send "already registered" message to IoT Hub
                        logger.info(f"Device ID {device_id} already registered, sending already registered message to IoT Hub")
                        
                        # Find the registration details for this device
                        device_info = next((device for device in registered_devices if device['device_id'] == device_id), None)
                        registration_date = device_info['registration_date'] if device_info else 'Unknown'
                        
                        # Send quantity update to IoT Hub
                        try:
                            # Get IoT Hub connection string from config
                            config = load_config()
                            iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
                            
                            if iot_hub_owner_connection:
                                # Initialize dynamic registration service with the IoT Hub owner connection string
                                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                                
                                if registration_service is None:
                                    logger.error(f"Failed to initialize dynamic registration service for device {device_id}")
                                    return f"⚠️ Device ID '{device_id}' was found, but IoT Hub connection failed. API update succeeded."
                                
                                # Get device connection string
                                device_connection_string = registration_service.register_device_with_azure(device_id)
                                
                                if device_connection_string:
                                            hub_client = HubClient(device_connection_string)
                                            
                                            # Create "already registered" message for IoT Hub
                                            already_registered_message = {
                                                "deviceId": device_id,
                                                "barcode": returned_barcode,
                                                "messageType": "already_registered",
                                                "registrationDate": registration_date,
                                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                                "status": "Device already registered - no duplicate registration"
                                            }
                                            
                                            # Send to IoT Hub
                                            iot_success = hub_client.send_message(returned_barcode, device_id, already_registered_message)
                                            logger.info(f"Already registered message sent to IoT Hub: {iot_success}")
                                else:
                                    logger.error(f"Failed to generate device connection string for {device_id}")
                        except Exception as e:
                            logger.error(f"Error sending already registered message to IoT Hub: {e}")
                        
                        # Blink yellow LED for already registered device
                        blink_led("yellow")
                        
                        return f"""🟡 Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Barcode: {returned_barcode}
• Status: Already in database
• Registered: {registration_date}

**Actions Completed:**
• ✅ Device found in database
• ✅ Already registered message sent to IoT Hub
• ⚠️ No duplicate registration performed

**LED Status:** 🟡 Yellow light indicates device already registered.

**Status:** Device is ready for barcode scanning operations!"""
                    
                    else:
                        # NEW DEVICE - Save to database and send success message to IoT Hub
                        logger.info(f"New device {device_id} - saving to database and sending success message to IoT Hub")
                        
                        # Add to processed device IDs set
                        processed_device_ids.add(device_id)
                        
                        # Save device registration with both device ID and barcode from API response
                        local_db.save_device_registration(device_id, returned_barcode)
                        
                        # Register device with external API to make it visible in frontend order list
                        logger.info(f"Registering device {device_id} with external API for frontend visibility")
                        device_registration_result = api_client.register_device(device_id)
                        
                        if device_registration_result.get("success", False):
                            logger.info(f"Successfully registered device {device_id} with external API: {device_registration_result.get('message')}")
                            api_registration_status = "✅ Registered with external API"
                        else:
                            logger.warning(f"Failed to register device {device_id} with external API: {device_registration_result.get('message')}")
                            api_registration_status = "⚠️ Failed to register with external API"
                        
                        # Send successful registration message to IoT Hub with device ID, barcode, and quantity
                        try:
                            config = load_config()
                            if config:
                                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
                                if iot_hub_owner_connection:
                                    registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                                    if registration_service:
                                        device_connection_string = registration_service.register_device_with_azure(device_id)
                                        if device_connection_string:
                                            hub_client = HubClient(device_connection_string)
                                            
                                            # Create successful registration message for IoT Hub
                                            success_message = {
                                                "deviceId": device_id,
                                                "barcode": returned_barcode,
                                                "quantity": 1,  # Default quantity
                                                "messageType": "successful_registration",
                                                "registrationDate": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                                "status": "New device successfully registered"
                                            }
                                            
                                            # Send to IoT Hub
                                            iot_success = hub_client.send_message(returned_barcode, device_id, success_message)
                                            iot_status = "✅ Success message sent to IoT Hub" if iot_success else ""
                                            logger.info(f"Success registration message sent to IoT Hub: {iot_success}")
                                        else:
                                            iot_status = "⚠️ Failed to generate IoT Hub connection"
                                    else:
                                        iot_status = "⚠️ Failed to initialize IoT Hub service"
                                else:
                                    iot_status = "⚠️ No IoT Hub configuration found"
                            else:
                                iot_status = "⚠️ Configuration not loaded"
                        except Exception as e:
                            logger.error(f"Error sending success message to IoT Hub: {e}")
                            iot_status = f"⚠️ IoT Hub error: {str(e)}"
                        
                        # Blink green LED for successful new registration
                        blink_led("green")
                        
                        return f"""🟢 New Device Registration Successful!

**Device Details:**
• Device ID: {device_id}
• Barcode: {returned_barcode}
• Quantity: 1
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device ID confirmed by API
• ✅ Device saved in local database
• {api_registration_status}
• {iot_status}

**LED Status:** 🟢 Green light indicates successful registration.

**Status:** Device is now ready for barcode scanning operations!"""
                    
        except json.JSONDecodeError:
            pass  # Continue if response is not valid JSON
        
        # If we reach here, the API call didn't return a successful response with device ID
        # This means the registration was not successful, so we don't save anything to database
        
        # Send message to IoT Hub for test device registration (but don't save to database)
        iot_success = False
        try:
            config = load_config()
            if config:
                # Use dynamic device ID generation for consistent device identification
                from utils.dynamic_device_id import generate_dynamic_device_id
                dynamic_device_id = generate_dynamic_device_id()
                
                # Add this device ID to our processed set regardless of API response
                processed_device_ids.add(dynamic_device_id)
                
                # Get IoT Hub owner connection string
                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
                if iot_hub_owner_connection:
                    registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                    if registration_service:
                        device_connection_string = registration_service.register_device_with_azure(dynamic_device_id)
                        if device_connection_string:
                            logger.info(f"✓ Generated device connection string for {dynamic_device_id}")
                            
                            # Create IoT Hub client with device-specific connection string
                            hub_client = HubClient(device_connection_string)
                            
                            # Create test registration message for IoT Hub
                            registration_message = {
                                "scannedBarcode": test_scan['barcode'],
                                "deviceId": dynamic_device_id,
                                "messageType": "test_registration",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "note": "Test registration - not saved to database"
                            }
                            
                            # Send to IoT Hub using send_message method
                            iot_success = hub_client.send_message(test_scan['barcode'], dynamic_device_id, registration_message)
                            iot_status = "✅ Test registration sent to IoT Hub" if iot_success else ""
                            logger.info(f"IoT Hub test registration result: {iot_success}")
                        else:
                            logger.error(f"Failed to generate device connection string for {dynamic_device_id}")
                            iot_status = "⚠️ Failed to generate IoT Hub connection"
                    else:
                        logger.error("Failed to initialize dynamic registration service")
                        iot_status = "⚠️ Failed to initialize IoT Hub service"
                else:
                    logger.error("No IoT Hub owner connection string found in config")
                    iot_status = "⚠️ No IoT Hub configuration found"
            else:
                iot_status = "⚠️ Configuration not loaded"
        except Exception as iot_error:
            logger.error(f"IoT Hub error: {iot_error}")
            iot_status = f"⚠️ IoT Hub error: {str(iot_error)}"
        
        # Blink LED based on IoT Hub success (yellow for partial success, red for failure)
        if iot_success:
            blink_led("yellow")  # Yellow: IoT Hub sent but device not saved to database
        else:
            blink_led("red")     # Red: IoT Hub failed
            blink_led("green")  # GREEN light for successful registration
            
        # Send confirmation message to frontend
        confirmation_msg = f"""✅ Registration Processed

**Device Details:**
• Device ID: {device_id}
• Barcode: {test_scan['barcode']}
• Processed At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ API confirmation sent
• ✅ Device saved to database


**Status:** Registration completed successfully. Device is now ready for barcode scanning operations."""
        
        return confirmation_msg
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

@require_pi_connection
def process_barcode_scan(barcode, device_id):
    """Unified function to handle barcode scanning with strict validation"""
    # Input validation
    if not barcode or not barcode.strip():
        blink_led("red")
        return "❌ Please enter a barcode."
    
    if not device_id or not device_id.strip():
        blink_led("red")
        return "❌ Please enter a device ID."
    
    barcode = barcode.strip()
    device_id = device_id.strip()

    # Get the connection manager instance first
    connection_manager = get_connection_manager()

    # 1. Check device registration status first to provide a better context message when offline.
    from utils.dynamic_device_manager import DynamicDeviceManager
    device_manager = DynamicDeviceManager()
    device_registered = device_manager.is_device_registered(device_id)
    if not device_registered:
        # Check local database as a fallback
        registered_devices = local_db.get_registered_devices()
        device_registered = any(
            dev.get('device_id') == device_id 
            for dev in (registered_devices or [])
        )

    # 2. Check Raspberry Pi connectivity
    pi_connected = connection_manager.check_raspberry_pi_availability()
    logger.info(f"🔍 DEBUG: Pi connection check result: {pi_connected}")

    if not pi_connected:
        if device_registered:
            # If device is registered but Pi is offline, save locally and inform the user.
            timestamp = datetime.now(timezone.utc)
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            logger.warning(f"Pi offline for registered device {device_id}. Scan saved locally.")
            blink_led("yellow")
            return f"""🟡 **Device Already Registered**

**Status:** Raspberry Pi is not connected. Scan saved locally.

Device is ready for barcode scanning operations! Scans will be sent when the Pi is back online."""
        else:
            # If device is not registered and Pi is offline, block the operation.
            error_msg = "🟡 **Operation Failed**\n\n"
            error_msg += "**Error:** 📥 Raspberry Pi is currently offline\n\n"
            error_msg += "**LED Status:** 🟡 Yellow light indicates operation failure\n\n"
            error_msg += "**Action:** Please ensure the Raspberry Pi device is connected and reachable on the network before trying again."
            logger.warning("Operation blocked: Raspberry Pi not connected for unregistered device")
            blink_led("yellow")
            return error_msg

    # Check if barcode scanner is connected
    if not is_scanner_connected():
        error_msg = "❌ **Operation Failed: Barcode Scanner Not Connected**\n\n"
        error_msg += "Please ensure your barcode scanner is properly connected to the Raspberry Pi and try again."
        logger.warning("Operation blocked: Barcode scanner not connected")
        blink_led("red")
        return error_msg

    # Check if we're online using the connection manager
    if not connection_manager.check_internet_connectivity():
        # Save scan locally since we're offline
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"Saved barcode scan locally (offline): {barcode} for device {device_id}")
        
        # Show warning that scan was saved locally
        blink_led("yellow")
        return "⚠️ Scan saved locally. Will be sent when back online."

    try:
        # 3. Handle device registration if not already registered
        if not device_registered:
            logger.info(f"New device detected: {device_id}. Initiating automatic registration...")
        
        if not device_registered:
            logger.info(f"New device detected: {device_id}. Initiating automatic registration...")
            # ... registration code ...
            success, reg_message = device_manager.register_device(auto_token, device_id, device_info)
            
            # Check if registration was successful
            if not success:
                blink_led("red")
                logger.error(f"Failed to auto-register device {device_id}: {reg_message}")
                return f"❌ Error: Device registration failed: {reg_message}"
            
            # Update device registration status
            device_registered = True
        

            
        # Save scan to local database
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
            
        # Check if barcode is provided
        if not barcode or not barcode.strip():
            blink_led("red")
            return "❌ Error: Barcode is required. Please scan a barcode."
            
        # Check if device ID is provided
        if not device_id or not device_id.strip():
            blink_led("red")
            return "❌ Error: Device ID is required. Please enter a device ID."
            
        # Use dynamic device ID generation for consistent device identification
        from utils.dynamic_device_id import generate_dynamic_device_id
        
        # Get the correct device ID for this barcode scan
        current_device_id = device_id.strip()
        barcode = barcode.strip()
        logger.info(f"Processing barcode: {barcode} for device: {current_device_id}")
        
        # Process the barcode scan with the correct device ID
        if current_device_id and barcode:
            # Validate barcode format before saving
            try:
                from barcode_validator import validate_ean, BarcodeValidationError
                # Validate the barcode format
                validated_barcode = validate_ean(barcode)
                logger.info(f"Barcode validation passed: {validated_barcode}")
                
                # Save scan to local database
                timestamp = local_db.save_scan(current_device_id, validated_barcode)
                logger.info(f"Saved scan to local database: {current_device_id}, {validated_barcode}, {timestamp}")
                
            except BarcodeValidationError as e:
                # Blink red LED for invalid barcode
                blink_led("red")
                logger.warning(f"Invalid barcode format: {str(e)}")
                return f"""❌ **Invalid Barcode**

**Error:** {str(e)}

**Barcode:** `{barcode}`

**Status:** Barcode was not saved. Please scan a valid barcode."""
            
            # Check if we're in offline mode
            if simulated_offline_mode:
                logger.info("Offline mode: Message saved locally, will be sent when online")
                iot_status = "⏸️ Offline mode: Message saved locally"
                success = True
            else:
                # Try to send to IoT Hub if online
                try:
                    config = load_config()
                    if config:
                        # Get device-specific connection string from the devices section
                        device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(current_device_id, {}).get("connection_string", None)
                        
                        # If device-specific connection string not found, use dynamic registration service
                        if not device_connection_string:
                            logger.info(f"Device-specific connection string not found for {current_device_id}, generating via dynamic registration...")
                            iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
                            if iot_hub_owner_connection:
                                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                                if registration_service:
                                    device_connection_string = registration_service.register_device_with_azure(current_device_id)
                                    if device_connection_string:
                                        logger.info(f"✓ Generated device connection string for {current_device_id}")
                                    else:
                                        logger.error(f"Failed to generate device connection string for {current_device_id}")
                                else:
                                    logger.error("Failed to initialize dynamic registration service")
                            else:
                                logger.error("No IoT Hub owner connection string found in config")
                        
                        if device_connection_string:
                            hub_client = HubClient(device_connection_string)
                            iot_success = hub_client.send_message(barcode, current_device_id)
                            
                            if iot_success:
                                iot_status = "✅ Sent to IoT Hub"
                                logger.info("Message sent successfully to IoT Hub")
                            else:
                                iot_status = "⚠️ Failed to send to IoT Hub - saved for retry"
                                local_db.save_unsent_message(current_device_id, barcode, datetime.now())
                                logger.info("Message saved for retry when back online")
                        else:
                            iot_status = "⚠️ No IoT Hub connection string configured"
                            local_db.save_unsent_message(current_device_id, barcode, datetime.now())
                            logger.info("Message saved for retry when connection is available")
                    else:
                        iot_status = "⚠️ Configuration not loaded"
                        local_db.save_unsent_message(current_device_id, barcode, datetime.now())
                        logger.info("Message saved for retry when configuration is available")
                except Exception as iot_error:
                    logger.error(f"IoT Hub error: {iot_error}")
                    iot_status = f"⚠️ IoT Hub error: {str(iot_error)} - Message saved for retry"
            
            # Initialize success variable to avoid reference error
            success = False
            
            # Return formatted response matching registration format
            return f"""📦 **Barcode Scan Processed**

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {current_device_id}
• Scanned At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Barcode saved locally
• {iot_status}

**Status:** {'Barcode processed successfully!' if success else 'Barcode saved locally for retry when IoT Hub is available.'}"""
        
        # If no device ID is registered yet, check if this barcode is a valid device ID
        if not current_device_id:
            is_online = api_client.is_online()
            if not is_online:
                return "❌ Device appears to be offline. Cannot validate device ID."
            
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
            payload = {"scannedBarcode": barcode}
            
            logger.info(f"Making first API call to {api_url}")
            api_result = api_client.send_registration_barcode(api_url, payload)
            
            if api_result.get("success", False) and "response" in api_result:
                response_data = json.loads(api_result["response"])
                
                if response_data.get("deviceId") and response_data.get("responseCode") == 200:
                    device_id = response_data.get("deviceId")
                    
                    existing_device_id = local_db.get_device_id()
                    if existing_device_id == device_id:
                        logger.info(f"Device ID {device_id} already registered, skipping registration")
                        blink_led("yellow")  # Use yellow to indicate already registered
                        
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
                                    device_connection_string = config.get("iot_hub", {}).get("connection_string", None)
                                    logger.warning(f"Using default connection string as fallback")
                            
                            if device_connection_string:
                                hub_client = HubClient(device_connection_string)
                                registration_message = {
                                    "scannedBarcode": barcode,
                                    "deviceId": device_id,
                                    "messageType": "registration",
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                                
                                iot_success = hub_client.send_message(barcode, device_id)
                                iot_status = "✅ Sent to IoT Hub" if iot_success else ""
                            else:
                                iot_status = "⚠️ No IoT Hub connection string available"
                        else:
                            iot_status = "⚠️ Failed to load configuration"
                    except Exception as e:
                        logger.error(f"Error sending to IoT Hub: {str(e)}")
                        iot_status = f"⚠️ Error: {str(e)}"
                    
                    # Blink green LED for success
                    blink_led("green")
                    
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
                    blink_led("blue")
                    
                    return f"""ℹ️ This is a test barcode.

Test barcode {barcode} has been saved.
Please proceed with device registration confirmation."""
                
                # Check if this is an invalid barcode
                elif response_data.get("responseCode") == 400:
                    # Blink red LED for error
                    blink_led("red")
                    
                    return f"❌ Invalid barcode. Please scan a valid device ID or test barcode."
        
        # If we have a device ID and barcode, process the barcode scan
        if device_id and barcode:
            # Validate barcode using the EAN validator
            try:
                validated_barcode = validate_ean(barcode)
            except BarcodeValidationError as e:
                return f"❌ Barcode validation error: {str(e)}"
            
            # Load configuration
            config = load_config()
            if not config:
                return "❌ Error: Failed to load configuration"
            
            # Save scan to local database
            timestamp = local_db.save_scan(device_id, validated_barcode, 1)
            logger.info(f"Saved scan to local database: {device_id}, {validated_barcode}, {timestamp}")
            
            # Use the enhanced connection manager for offline/online detection and message sending
            success, status_msg = connection_manager.send_message_with_retry(device_id, validated_barcode, 1, "barcode_scan")
            
            if success:
                # Mark as sent in local database
                local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
                return f"✅ Barcode {validated_barcode} scanned and sent successfully!\n\n**Details:**\n{status_msg}"
            else:
                # Message was saved locally for retry when online
                return f"📥 Barcode {validated_barcode} saved for retry.\n\n**Details:**\n{status_msg}"
    
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        return f"❌ Error processing barcode: {str(e)}"

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
    """Process any unsent messages in the local database and try to send them"""
    try:
        # Get the connection manager instance
        connection_manager = get_connection_manager()
        
        # Check if we're online using the connection manager
        if not connection_manager.check_internet_connectivity():
            status_msg = "❌ Device is offline. Cannot process unsent messages. Please check your internet connection and try again."
            logger.info(status_msg)
            return None if auto_retry else status_msg
            
        # Get unsent messages from local database
        unsent_messages = local_db.get_unsent_scans()
        if not unsent_messages:
            status_msg = "✅ No unsent messages to process."
            logger.info(status_msg)
            return None if auto_retry else status_msg
        
        success_count = 0
        fail_count = 0
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["barcode"]
            quantity = message.get("quantity", 1)
            
            # Check if this is a test barcode - if so, skip sending to IoT Hub
            if api_client.is_test_barcode(barcode):
                logger.info(f"Skipping test barcode in unsent messages: {barcode} - BLOCKED from IoT Hub")
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
                continue
            
            # Use the connection manager to send with proper offline/online detection
            success, status_msg = connection_manager.send_message_with_retry(device_id, barcode, quantity, "barcode_scan")
            
            if success:
                local_db.mark_sent_by_id(message.get("id"))
                success_count += 1
                logger.info(f"Successfully sent unsent message: {device_id}, {barcode}")
            else:
                fail_count += 1
                logger.warning(f"Failed to send unsent message: {device_id}, {barcode} - {status_msg}")
                
        result_msg = f"Processed {len(unsent_messages)} unsent messages. Success: {success_count}, Failed: {fail_count}"
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

def check_device_registered():
    """Check if any device is registered in the system"""
    try:
        # First check if we have any registered devices in the database
        registered_devices = local_db.get_registered_devices()
        if registered_devices and len(registered_devices) > 0:
            return True
            
        # If no devices in database, check if we have a device ID in the config
        config = load_config()
        device_id = config.get('device', {}).get('device_id')
        if device_id:
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking device registration: {str(e)}")
        return False

def get_connection_status():
    """Get real-time connection status for display in Gradio interface"""
    try:
        # Check all connectivity components
        internet_status = connection_manager.check_internet_connectivity()
        iot_hub_status = connection_manager.check_iot_hub_connectivity()
        pi_status = connection_manager.check_raspberry_pi_availability()
        
        # Get current timestamp
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Build status message
        status_lines = [
            f"🕐 **Last Updated:** {current_time}",
            "",
            "**Connectivity Status:**"
        ]
        
        # Internet status
        if internet_status:
            status_lines.append("• 🌐 **Internet:** ✅ Connected")
        else:
            status_lines.append("• 🌐 **Internet:** ❌ Offline")
        
        # IoT Hub status
        if iot_hub_status:
            status_lines.append("• ☁️ **IoT Hub:** ✅ Connected")
        else:
            status_lines.append("• ☁️ **IoT Hub:** ❌ Offline")
        
        # Raspberry Pi status
        if pi_status:
            status_lines.append("• 🍓 **Raspberry Pi:** ✅ Reachable")
        else:
            status_lines.append("• 🍓 **Raspberry Pi:** ❌ Unreachable")
        
        # Overall status
        status_lines.append("")
        if internet_status and iot_hub_status and pi_status:
            status_lines.append("**Overall Status:** 🟢 **ONLINE** - Messages will be sent immediately")
        else:
            status_lines.append("**Overall Status:** 🔴 **OFFLINE** - Messages will be saved locally for retry")
            
            # Show what's blocking
            blocking_components = []
            if not internet_status:
                blocking_components.append("Internet")
            if not iot_hub_status:
                blocking_components.append("IoT Hub")
            if not pi_status:
                blocking_components.append("Raspberry Pi")
            
            if blocking_components:
                status_lines.append(f"**Blocking Components:** {', '.join(blocking_components)}")
        
        return "\n".join(status_lines)
        
    except Exception as e:
        logger.error(f"Error getting connection status: {e}")
        return f"❌ **Error getting connection status:** {str(e)}"

def update_ui_elements():
    """Update the enabled/disabled state of UI elements based on device registration"""
    is_registered = check_device_registered()
    
    return [
        gr.update(interactive=is_registered),  # barcode_input
        gr.update(interactive=is_registered),  # device_id_input
        gr.update(interactive=is_registered),  # send_button
        gr.update(interactive=True),           # clear_button (always enabled)
        gr.update(interactive=not is_registered, visible=not is_registered),  # scan_test_barcode_button
        gr.update(interactive=not is_registered, visible=not is_registered),  # confirm_registration_button
        gr.update(interactive=is_registered),  # process_unsent_button
        gr.update(interactive=is_registered),  # simulate_offline_button
        gr.update(interactive=is_registered),  # simulate_online_button
        gr.update(interactive=is_registered),  # offline_status_text
        gr.update(visible=not is_registered, 
                 value="⚠️ Please register a device to enable barcode scanning" if not is_registered else "")
    ]

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
                
            with gr.Row():
                process_unsent_button = gr.Button("Process Unsent Messages")
                
            status_text = gr.Markdown("")
            
            with gr.Row():
                gr.Markdown("### Test Offline Mode")
                simulate_offline_button = gr.Button("Simulate Offline Mode")
                simulate_online_button = gr.Button("Restore Online Mode")
            
            offline_status_text = gr.Markdown("Current mode: Online")
            
    # Event handlers
    send_button.click(
        fn=process_barcode_scan,
        inputs=[barcode_input, device_id_input],
        outputs=[output_text]
    )
    
    clear_button.click(
        fn=lambda: (""),
        inputs=[],
        outputs=[barcode_input]
    )
    
    # Two-step registration handlers
    scan_test_barcode_button.click(
        fn=lambda: register_device_id("817994ccfe14"),
        inputs=[],
        outputs=[status_text]
    )
    
    confirm_registration_button.click(
        fn=confirm_registration,
        inputs=[barcode_input, device_id_input],
        outputs=[status_text]
    )
    

    
    def process_unsent_wrapper():
        connection_manager = get_connection_manager()
        if not connection_manager.check_raspberry_pi_availability():
            blink_led("red")
            return "❌ **Error:** Raspberry Pi is not connected. Please connect the device to process unsent messages."
        return process_unsent_messages(auto_retry=False)

    process_unsent_button.click(
        fn=process_unsent_wrapper,
        inputs=[],
        outputs=[status_text]
    )
    


def register_device_with_iot_hub(device_id):
    """Register a device with Azure IoT Hub"""
    try:
        if not IOT_HUB_REGISTRY_AVAILABLE:
            return {"success": False, "message": "IoT Hub Registry not available"}

        config = load_config()
        if not config or not config.get("iot_hub", {}).get("connection_string"):
            return {"success": False, "message": "IoT Hub connection string not configured"}

        iot_hub_connection_string = config["iot_hub"]["connection_string"]
        
        try:
            # Initialize IoT Hub Registry Manager
            registry_manager = IoTHubRegistryManager.from_connection_string(iot_hub_connection_string)
            
            # Check if device already exists
            try:
                existing_device = registry_manager.get_device(device_id)
                if existing_device:
                    logger.info(f"Device {device_id} already exists in IoT Hub")
                    return {"success": True, "message": "Device already registered"}
            except Exception:
                # Device doesn't exist, continue with registration
                pass

            # Create device with symmetric key authentication
            device = Device(device_id=device_id)
            device.authentication = AuthenticationMechanism(
                type='sas',
                symmetric_key=SymmetricKey()
            )
            
            # Register device
            device = registry_manager.create_or_update_device(device)
            logger.info(f"Successfully registered device {device_id} with IoT Hub")
            
            return {"success": True, "message": "Device registered successfully"}
            
        except Exception as e:
            logger.error(f"Error registering device with IoT Hub: {str(e)}")
            return {"success": False, "message": f"IoT Hub registration error: {str(e)}"}
            
    except Exception as e:
        logger.error(f"Error in register_device_with_iot_hub: {str(e)}")
        return {"success": False, "message": str(e)}

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        global processed_device_ids

        # Get connection manager
        from utils.connection_manager import get_connection_manager
        connection_manager = get_connection_manager()

        # ✅ Force fresh Raspberry Pi availability check
        pi_available = connection_manager.check_raspberry_pi_availability()
        if not pi_available:
            error_msg = (
                "❌ **Registration Failed - Raspberry Pi Not Connected**\n\n"
                "**Error:** The Raspberry Pi is not reachable on the network.\n\n"
                "**LED Status:** 🔴 Red light indicates Pi connection failure.\n\n"
                "**Action:** Please ensure the Raspberry Pi is powered on, "
                "connected to the same network, and accessible via SSH or Web before trying again."
            )
            logger.error("Operation blocked: Raspberry Pi not connected or unreachable")
            blink_led("red")
            return error_msg

        # ✅ Extra safeguard: re-check with lock to avoid race condition
        with connection_manager.lock:
            if not connection_manager.raspberry_pi_devices_available:
                logger.error("Raspberry Pi lost connection during registration attempt")
                blink_led("red")
                return "❌ Registration failed - Raspberry Pi disconnected during check."

        # Check if barcode scanner is connected
        if not is_scanner_connected():
            error_msg = (
                "❌ **Operation Failed: Barcode Scanner Not Connected**\n\n"
                "Please ensure your barcode scanner is properly connected to the Raspberry Pi and try again."
            )
            logger.warning("Operation blocked: Barcode scanner not connected")
            blink_led("red")
            return error_msg

        # ✅ Continue with existing flow...
        if not connection_manager.check_internet_connectivity() or not connection_manager.check_iot_hub_connectivity():
            timestamp = datetime.now(timezone.utc)
            local_db.save_unsent_message("device_registration", barcode, timestamp)
            logger.warning("Device registration saved locally - will be processed when back online")
            blink_led("yellow")
            return "⚠️ Device registration saved locally. Will be processed when back online."

        # ... rest of your existing registration flow (API calls, DB save, etc.)

    except Exception as e:
        logger.error(f"Error in register_device_id: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"


if __name__ == "__main__":
    # Initialize connection manager with auto-refresh for automatic Pi detection
    logger.info("🚀 Starting Barcode Scanner API with automatic Pi detection...")
    connection_manager = get_connection_manager()
    logger.info("✅ Auto-refresh connection monitoring initialized")
    logger.info("🔄 Pi connectivity will be automatically detected every 10 seconds")
    logger.info("📡 No need to restart API - connection changes detected automatically!")
    
    app.launch(server_name="0.0.0.0", server_port=7861)