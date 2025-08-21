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

# Offline simulation removed

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
        return response_msg
        
    except Exception as e:
        logger.error(f"Error generating registration token: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

@require_pi_connection
def confirm_registration(registration_token, device_id):
    """Step 2: Confirm device registration using token and device ID"""
    if not is_scanner_connected():
        return "⚠️ No barcode scanner detected. Please connect your device."
    try:
        global processed_device_ids
        
        # Registration token optional - bypass token requirement
        
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
    
# Initialize Raspberry Pi connection status on app startup
logger.info("🍓 Initializing Raspberry Pi connection status...")
check_raspberry_pi_connection()
logger.info(f"🍓 Pi connection status: {_pi_connection_status}")

if __name__ == "__main__":
    # Initialize connection manager with auto-refresh for automatic Pi detection
    logger.info("🚀 Starting Barcode Scanner API with automatic Pi detection...")
    connection_manager = get_connection_manager()
    logger.info("✅ Auto-refresh connection monitoring initialized")
    logger.info("🔄 Pi connectivity will be automatically detected every 10 seconds")
    logger.info("📡 No need to restart API - connection changes detected automatically!")
    
    app.launch(server_name="0.0.0.0", server_port=7861)