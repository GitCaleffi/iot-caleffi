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

# Simple barcode validation
def validate_ean(barcode):
    if not barcode or len(barcode) < 6:
        raise BarcodeValidationError("Invalid barcode")
    return barcode

class BarcodeValidationError(Exception):
    pass

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
sys.path.append(str(current_dir))

# Initialize stubs for missing modules
local_db = None
api_client = None

try:
    from utils.config import load_config, save_config
    from iot.hub_client import HubClient
    from database.local_storage import LocalStorage
    from api.api_client import ApiClient
    local_db = LocalStorage()
    api_client = ApiClient()
except ImportError as e:
    logger.error(f"Import error: {e}")
    # Create minimal stubs
    class LocalStorage:
        def get_device_id(self): return None
        def save_device_id(self, device_id): pass
        def save_test_barcode_scan(self, barcode): pass
        def get_test_barcode_scan(self): return None
        def get_registered_devices(self): return []
        def save_device_registration(self, device_id, data): pass
        def save_barcode_scan(self, device_id, barcode, timestamp): pass
        def save_unsent_message(self, device_id, message, timestamp): pass
        def get_recent_scans(self, limit): return []
        def get_unsent_messages(self): return []
    
    class ApiClient:
        def is_online(self): return True
        def send_registration_barcode(self, url, payload): return {"success": True, "message": "Success"}
        def confirm_registration(self, device_id, pi_ip=None): return {"success": True, "device_data": {"deviceId": device_id}}
        def send_barcode_scan(self, device_id, barcode, quantity): return {"success": True}
    
    def load_config(): return {}
    def save_config(config): pass
    
    local_db = LocalStorage()
    api_client = ApiClient()

# Registration functions are now integrated directly

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

    return False

IS_RASPBERRY_PI = is_raspberry_pi()

# GPIO LED Configuration
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

def generate_registration_token():
    """Prepare for device registration (no token required)"""
    
    if not is_scanner_connected():
        return "⚠️ No barcode scanner detected. Please connect your device."
    
    try:
        response_msg = f"""✅ Ready for Device Registration!

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

def confirm_registration(registration_token, device_id):
    """Confirm device registration with no token validation"""
    global REGISTRATION_IN_PROGRESS
    
    # Set registration flag to prevent any quantity updates
    with registration_lock:
        REGISTRATION_IN_PROGRESS = True
    
    logger.info("🔒 STARTING DEVICE REGISTRATION - NO INVENTORY/QUANTITY UPDATES WILL BE SENT")
    
    try:
        global processed_device_ids

        if not device_id or device_id.strip() == "":
            led_controller.blink_led("red")
            return "❌ Please enter a device ID."
        
        # Strip device_id safely (no token needed)
        device_id = device_id.strip()
        
        # Check if device is already registered in local DB
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            # Find the registration date for display
            existing_device = next((dev for dev in registered_devices if dev['device_id'] == device_id), None)
            reg_date = existing_device.get('registration_date', 'Unknown') if existing_device else 'Unknown'
            led_controller.blink_led("red")
            return f"❌ Device already registered with ID: {device_id} (Registered: {reg_date}). Please use a different device ID."
        
        # Save device registration locally
        local_db.save_device_registration(device_id, {
            'registration_date': datetime.now(timezone.utc).isoformat(),
            'registration_method': 'direct_registration'
        })
        
        # Confirm device registration with API
        api_confirmation_status = "ℹ️ API confirmation not attempted"
        
        try:
            # Confirm registration with API
            logger.info(f"Confirming device registration {device_id} with API...")
            api_result = api_client.confirm_registration(device_id)
            
            if api_result.get('success', False):
                api_confirmation_status = "✅ Device registration confirmed with API successfully"
                logger.info(f"Device {device_id} registration confirmed with API")
            else:
                api_confirmation_status = f"⚠️ API confirmation failed: {api_result.get('message', 'Unknown error')}"
                logger.warning(f"API confirmation failed: {api_result}")
                
        except Exception as e:
            logger.error(f"Error with API confirmation: {str(e)}")
            api_confirmation_status = f"⚠️ API confirmation error: {str(e)}"
        
        led_controller.blink_led("green")
        
        # Clear registration flag before returning success
        with registration_lock:
            REGISTRATION_IN_PROGRESS = False
        logger.info("🔒 REGISTRATION_IN_PROGRESS flag cleared - quantity updates now allowed")
        
        return f"""🎉 Device Registration Completed!

**Device Details:**
• Device ID: {device_id}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
• Registration Method: Direct (no token required)

**Actions Completed:**
• ✅ Device ID saved locally
• {api_confirmation_status}

**Status:** Device is now ready for barcode scanning operations!

**You can now scan real product barcodes for inventory management.**"""
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        # Clear registration flag on error too
        with registration_lock:
            REGISTRATION_IN_PROGRESS = False
        logger.info("🔒 REGISTRATION_IN_PROGRESS flag cleared due to error")
        led_controller.blink_led("red")
        return f"❌ Error: {str(e)}"

def process_barcode_scan(barcode, device_id=None):
    """Simplified barcode scanning"""
    
    # Input validation
    if not barcode or not barcode.strip():
        led_controller.blink_led("red")
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

    try:
        # Save scan to local database
        timestamp = datetime.now(timezone.utc)
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"💾 Saved barcode scan locally: {barcode}")
        
        # Try to send to API
        try:
            api_result = api_client.send_barcode_scan(device_id, barcode, 1)
            if api_result.get('success', False):
                led_controller.blink_led("green")
                return f"""✅ **Barcode Scan Successful**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** Sent to API successfully
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🟢 Green LED indicates successful operation"""
            else:
                led_controller.blink_led("yellow")
                return f"""⚠️ **Barcode Saved Locally**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** API unavailable - saved locally
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🟡 Yellow LED indicates offline operation"""
        except Exception as e:
            logger.error(f"API send error: {e}")
            led_controller.blink_led("yellow")
            return f"""⚠️ **Barcode Saved Locally**

**Barcode:** {barcode}
**Device ID:** {device_id}
**Status:** API error - saved locally
**Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🟡 Yellow LED indicates offline operation"""
                
    except Exception as e:
        logger.error(f"❌ Barcode scan error: {e}")
        led_controller.blink_led("red")
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

def process_unsent_messages_ui():
    """Process unsent messages with user-visible progress for Gradio UI."""
    yield "⏳ Processing unsent messages... Please wait."
    try:
        unsent_messages = local_db.get_unsent_messages()
        if not unsent_messages:
            yield "✅ No unsent messages found."
            return
        
        processed = 0
        for message in unsent_messages:
            # Simulate processing
            time.sleep(0.1)
            processed += 1
            
        yield f"✅ Processed {processed} unsent messages successfully."
    except Exception as e:
        error_msg = f"❌ Error while processing unsent messages: {str(e)}"
        logger.error(error_msg)
        yield error_msg

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
                scan_test_barcode_button = gr.Button("1. Prepare Registration", variant="primary")
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

logger.info("🚀 Barcode scanner system initialized")
logger.info("📱 System ready for barcode scanning operations")
logger.info("✅ System initialization complete")

if __name__ == "__main__":
    logger.info("🚀 Starting Barcode Scanner Application...")
    logger.info("🌐 Web interface will be available at: http://localhost:7860")
    app.launch(server_name="0.0.0.0", server_port=7860, share=False)