import gradio as gr
import json
import os
import sys
from pathlib import Path
import logging
import time
import threading
import queue
from datetime import datetime, timezone, timedelta
try:
    from barcode_validator import validate_ean, BarcodeValidationError
except ImportError:
    # Fallback if barcode_validator is not available
    def validate_ean(barcode):
        class ValidationResult:
            def __init__(self, is_valid=True, error_message=None):
                self.is_valid = is_valid
                self.error_message = error_message
        return ValidationResult(is_valid=True)
    
    class BarcodeValidationError(Exception):
        pass
import subprocess
import select

# OpenCV and barcode detection imports
try:
    import cv2
    import numpy as np
    from pyzbar import pyzbar
    CAMERA_AVAILABLE = True
except ImportError as e:
    CAMERA_AVAILABLE = False

# USB Scanner support
try:
    import evdev
    USB_SCANNER_AVAILABLE = True
except ImportError:
    USB_SCANNER_AVAILABLE = False

logger = logging.getLogger(__name__)

# Log camera availability after logger is initialized
if CAMERA_AVAILABLE:
    logger.info("✅ OpenCV and pyzbar imported successfully")
else:
    logger.warning("⚠️ Camera libraries not available. Install with: pip install opencv-python pyzbar")

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config, save_config
from iot.hub_client import HubClient
from iot.connection_manager import connection_manager
from database.local_storage import LocalStorage
from api.api_client import ApiClient
from utils.dynamic_device_manager import device_manager

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

# Camera barcode detection globals
camera_active = False
camera_thread = None
detected_barcodes_queue = queue.Queue()

# USB Scanner globals
usb_scanner_active = False
usb_scanner_thread = None
usb_scanner_queue = queue.Queue()
usb_device_path = None
auto_scan_enabled = False

def detect_barcodes_from_camera():
    """Detect barcodes from camera feed using OpenCV and pyzbar"""
    if not CAMERA_AVAILABLE:
        return "❌ Camera libraries not available. Install with: pip install opencv-python pyzbar"
    
    try:
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "❌ Failed to open camera. Check camera connection."
        
        logger.info("📷 Camera opened successfully")
        detected_barcodes = []
        scan_start_time = time.time()
        
        while time.time() - scan_start_time < 10:  # Scan for 10 seconds
            ret, frame = cap.read()
            if not ret:
                continue
            
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect barcodes
            barcodes = pyzbar.decode(gray)
            
            for barcode in barcodes:
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                # Avoid duplicates
                if barcode_data not in detected_barcodes:
                    detected_barcodes.append(barcode_data)
                    logger.info(f"📱 Detected barcode: {barcode_data} (Type: {barcode_type})")
                    
                    # Add to queue for processing
                    detected_barcodes_queue.put({
                        'barcode': barcode_data,
                        'type': barcode_type,
                        'timestamp': datetime.now()
                    })
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)
        
        cap.release()
        
        if detected_barcodes:
            return f"✅ Detected {len(detected_barcodes)} barcode(s): {', '.join(detected_barcodes)}"
        else:
            return "⚠️ No barcodes detected. Ensure good lighting and clear barcode visibility."
            
    except Exception as e:
        logger.error(f"❌ Camera detection error: {str(e)}")
        return f"❌ Camera error: {str(e)}"

def scan_barcode_from_camera():
    """Scan a single barcode from camera and return it"""
    if not CAMERA_AVAILABLE:
        return "", "❌ Camera libraries not available"
    
    try:
        # Clear previous detections
        while not detected_barcodes_queue.empty():
            detected_barcodes_queue.get()
        
        # Start detection
        result = detect_barcodes_from_camera()
        
        # Get the first detected barcode
        if not detected_barcodes_queue.empty():
            barcode_info = detected_barcodes_queue.get()
            return barcode_info['barcode'], f"✅ Camera detected: {barcode_info['barcode']} ({barcode_info['type']})"
        else:
            return "", result
            
    except Exception as e:
        logger.error(f"❌ Camera scan error: {str(e)}")
        return "", f"❌ Camera scan error: {str(e)}"

def start_continuous_camera_scanning():
    """Start continuous camera scanning in background"""
    global camera_active, camera_thread
    
    if not CAMERA_AVAILABLE:
        return "❌ Camera libraries not available"
    
    if camera_active:
        return "⚠️ Camera scanning already active"
    
    try:
        camera_active = True
        camera_thread = threading.Thread(target=continuous_camera_scan_loop, daemon=True)
        camera_thread.start()
        return "✅ Continuous camera scanning started"
    except Exception as e:
        camera_active = False
        return f"❌ Failed to start camera scanning: {str(e)}"

def stop_continuous_camera_scanning():
    """Stop continuous camera scanning"""
    global camera_active
    camera_active = False
    return "⚠️ Continuous camera scanning stopped"

def continuous_camera_scan_loop():
    """Continuous camera scanning loop running in background thread"""
    if not CAMERA_AVAILABLE:
        return
    
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            logger.error("Failed to open camera for continuous scanning")
            return
        
        logger.info("📷 Continuous camera scanning started")
        last_detected = {}
        
        while camera_active:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect barcodes
            barcodes = pyzbar.decode(gray)
            
            for barcode in barcodes:
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                current_time = time.time()
                
                # Avoid duplicate detections within 2 seconds
                if barcode_data not in last_detected or (current_time - last_detected[barcode_data]) > 2:
                    last_detected[barcode_data] = current_time
                    logger.info(f"📱 Continuous scan detected: {barcode_data} ({barcode_type})")
                    
                    # Add to queue for processing
                    detected_barcodes_queue.put({
                        'barcode': barcode_data,
                        'type': barcode_type,
                        'timestamp': datetime.now()
                    })
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.2)
        
        cap.release()
        logger.info("📷 Continuous camera scanning stopped")
        
    except Exception as e:
        logger.error(f"❌ Continuous camera scanning error: {str(e)}")

def process_camera_barcode_scan():
    """Process barcode from camera queue automatically"""
    try:
        if not detected_barcodes_queue.empty():
            barcode_info = detected_barcodes_queue.get_nowait()
            barcode_data = barcode_info['barcode']
            
            # Process the barcode using existing logic
            result = process_barcode_scan(barcode_data)
            
            return f"📱 Camera Auto-Scan: {barcode_data}\n{result}"
        else:
            return "⚠️ No barcodes detected from camera"
            
    except queue.Empty:
        return "⚠️ No barcodes in camera queue"
    except Exception as e:
        logger.error(f"❌ Camera barcode processing error: {str(e)}")
        return f"❌ Camera processing error: {str(e)}"

def detect_usb_scanner():
    """Detect USB barcode scanner device"""
    global usb_device_path
    
    if not USB_SCANNER_AVAILABLE:
        return "❌ USB scanner support not available. Install with: pip install evdev"
    
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        scanner_devices = []
        
        for device in devices:
            # Look for devices that might be barcode scanners
            if ('barcode' in device.name.lower() or 
                'scanner' in device.name.lower() or
                'honeywell' in device.name.lower() or
                'symbol' in device.name.lower() or
                'datalogic' in device.name.lower()):
                scanner_devices.append(device)
                logger.info(f"Found potential scanner: {device.name} at {device.path}")
        
        if scanner_devices:
            usb_device_path = scanner_devices[0].path
            return f"✅ USB Scanner detected: {scanner_devices[0].name} at {usb_device_path}"
        else:
            # Fallback: try keyboard-like devices (many scanners act as keyboards)
            for device in devices:
                caps = device.capabilities()
                if evdev.ecodes.EV_KEY in caps:
                    # Check if it has alphanumeric keys (typical for barcode scanners)
                    keys = caps[evdev.ecodes.EV_KEY]
                    if evdev.ecodes.KEY_A in keys and evdev.ecodes.KEY_ENTER in keys:
                        scanner_devices.append(device)
                        logger.info(f"Found keyboard-like device (potential scanner): {device.name}")
            
            if scanner_devices:
                usb_device_path = scanner_devices[0].path
                return f"✅ Potential USB Scanner detected: {scanner_devices[0].name} at {usb_device_path}"
            else:
                return "⚠️ No USB barcode scanner detected"
                
    except Exception as e:
        logger.error(f"Error detecting USB scanner: {str(e)}")
        return f"❌ Error detecting USB scanner: {str(e)}"

def start_usb_scanner():
    """Start USB barcode scanner monitoring"""
    global usb_scanner_active, usb_scanner_thread
    
    if not USB_SCANNER_AVAILABLE:
        return "❌ USB scanner support not available"
    
    if not usb_device_path:
        detect_result = detect_usb_scanner()
        if "❌" in detect_result or "⚠️" in detect_result:
            return detect_result
    
    if usb_scanner_active:
        return "⚠️ USB scanner already active"
    
    try:
        usb_scanner_active = True
        usb_scanner_thread = threading.Thread(target=usb_scanner_loop, daemon=True)
        usb_scanner_thread.start()
        return f"✅ USB scanner started monitoring {usb_device_path}"
    except Exception as e:
        usb_scanner_active = False
        return f"❌ Failed to start USB scanner: {str(e)}"

def stop_usb_scanner():
    """Stop USB barcode scanner monitoring"""
    global usb_scanner_active
    usb_scanner_active = False
    return "⚠️ USB scanner monitoring stopped"

def usb_scanner_loop():
    """USB scanner monitoring loop"""
    if not USB_SCANNER_AVAILABLE or not usb_device_path:
        return
    
    try:
        device = evdev.InputDevice(usb_device_path)
        logger.info(f"USB scanner monitoring started for {device.name}")
        
        barcode_buffer = ""
        
        for event in device.read_loop():
            if not usb_scanner_active:
                break
                
            if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # Key press
                key_code = event.code
                
                # Handle alphanumeric keys
                if key_code >= evdev.ecodes.KEY_A and key_code <= evdev.ecodes.KEY_Z:
                    barcode_buffer += chr(ord('a') + key_code - evdev.ecodes.KEY_A)
                elif key_code >= evdev.ecodes.KEY_0 and key_code <= evdev.ecodes.KEY_9:
                    barcode_buffer += chr(ord('0') + key_code - evdev.ecodes.KEY_0)
                elif key_code == evdev.ecodes.KEY_ENTER:
                    # Barcode scan complete
                    if barcode_buffer.strip():
                        logger.info(f"USB Scanner detected barcode: {barcode_buffer}")
                        usb_scanner_queue.put({
                            'barcode': barcode_buffer.strip(),
                            'timestamp': datetime.now(),
                            'source': 'usb_scanner'
                        })
                        barcode_buffer = ""
                elif key_code == evdev.ecodes.KEY_SPACE:
                    barcode_buffer += " "
                # Add more key mappings as needed
                
    except Exception as e:
        logger.error(f"USB scanner error: {str(e)}")
        usb_scanner_active = False

def get_usb_scanner_barcode():
    """Get barcode from USB scanner queue"""
    try:
        if not usb_scanner_queue.empty():
            barcode_info = usb_scanner_queue.get_nowait()
            return barcode_info['barcode'], f"✅ USB Scanner: {barcode_info['barcode']}"
        else:
            return "", "⚠️ No barcodes from USB scanner"
    except queue.Empty:
        return "", "⚠️ USB scanner queue empty"
    except Exception as e:
        return "", f"❌ USB scanner error: {str(e)}"

def toggle_auto_scan():
    """Toggle automatic scanning mode"""
    global auto_scan_enabled
    auto_scan_enabled = not auto_scan_enabled
    
    if auto_scan_enabled:
        # Start USB scanner if available
        usb_result = start_usb_scanner()
        return f"✅ Auto-scan enabled\n{usb_result}"
    else:
        # Stop scanners
        stop_usb_scanner()
        stop_continuous_camera_scanning()
        return "⚠️ Auto-scan disabled"

def auto_process_scanned_barcodes():
    """Automatically process EAN barcodes from USB scanner with quantity 1"""
    if not auto_scan_enabled:
        return "Auto-scan is disabled"
    
    results = []
    
    # Get registered device ID
    device_id = local_db.get_device_id()
    if not device_id:
        return "❌ No device registered. Please register device first."
    
    # Check USB scanner for EAN barcodes
    if not usb_scanner_queue.empty():
        try:
            barcode_info = usb_scanner_queue.get_nowait()
            ean_barcode = barcode_info['barcode']
            
            # Send EAN with quantity 1 to IoT Hub
            result = usb_scan_and_send_ean(ean_barcode, device_id)
            results.append(f"🔌 USB Scanner EAN: {ean_barcode}\n{result}")
            
        except queue.Empty:
            pass
    
    # Check camera scanner for EAN barcodes
    if not detected_barcodes_queue.empty():
        try:
            barcode_info = detected_barcodes_queue.get_nowait()
            ean_barcode = barcode_info['barcode']
            
            # Send EAN with quantity 1 to IoT Hub
            result = usb_scan_and_send_ean(ean_barcode, device_id)
            results.append(f"📱 Camera EAN: {ean_barcode}\n{result}")
            
        except queue.Empty:
            pass
    
    if results:
        return "\n\n".join(results)
    else:
        return "No new EAN barcodes detected"

def plug_and_play_register_device(device_id):
    """Plug-and-play device registration - only registration, no quantity updates"""
    try:
        # Step 1: Check if device already registered locally
        existing_device = local_db.get_device_id()
        if existing_device == device_id:
            return f"⚠️ Device {device_id} already registered locally. No need to register again."
        
        # Step 2: Check if device exists in IoT Hub config
        config = load_config()
        devices = config.get("iot_hub", {}).get("devices", {})
        if device_id in devices:
            # Save to local DB if not already saved
            local_db.save_device_id(device_id)
            return f"✅ Device {device_id} already registered in IoT Hub. Saved to local database."
        
        test_barcode = "817994ccfe14"
        
        # Step 3: Save test barcode
        local_db.save_test_barcode_scan(test_barcode)
        
        # Step 4: Check if online
        if not api_client.is_online():
            return f"❌ Device is offline. Cannot register {device_id}."
        
        # Step 5: Call confirmRegistration API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": test_barcode}
        
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        if not api_result.get("success", False):
            error_msg = api_result.get('message', 'Unknown error')
            if "Device not found" in error_msg:
                # Try direct registration
                save_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                save_payload = {"scannedBarcode": device_id}
                
                save_result = api_client.send_registration_barcode(save_url, save_payload)
                
                if save_result.get("success", False) and "response" in save_result:
                    try:
                        save_response = json.loads(save_result["response"])
                        if save_response.get("deviceId") and save_response.get("responseCode") == 200:
                            registered_device_id = save_response.get("deviceId")
                            local_db.save_device_id(registered_device_id)
                        else:
                            return f"❌ API registration failed for {device_id}"
                    except json.JSONDecodeError:
                        return f"❌ Invalid API response for {device_id}"
                else:
                    return f"❌ Direct registration failed for {device_id}"
            else:
                return f"❌ Confirmation failed: {error_msg}"
        else:
            local_db.save_device_id(device_id)
        
        # Step 4: Register with IoT Hub
        registration_result = register_device_with_iot_hub(device_id)
        if not registration_result.get("success"):
            return f"⚠️ Device {device_id} registered with API but IoT Hub failed: {registration_result.get('error')}"
        
        # Step 5: Send ONLY registration message to IoT Hub (no quantity updates)
        try:
            config = load_config()
            devices = config.get("iot_hub", {}).get("devices", {})
            
            if device_id in devices:
                connection_string = devices[device_id]["connection_string"]
                
                # Send registration confirmation only using persistent connection
                import hashlib
                registration_code = str(int(hashlib.md5(device_id.encode()).hexdigest()[:12], 16))[:13].zfill(13)
                success = connection_manager.send_message(device_id, connection_string, registration_code)
                
                if success:
                    return f"✅ Device {device_id} registered successfully!\n✅ Registration message sent to IoT Hub\n✅ Device saved in local database\n✅ Ready for USB barcode scanning"
                else:
                    return f"⚠️ Device {device_id} registered but failed to send confirmation to IoT Hub"
            else:
                return f"⚠️ Device {device_id} registered but not found in IoT Hub config"
                
        except Exception as e:
            return f"⚠️ Device {device_id} registered but IoT Hub confirmation failed: {str(e)}"
        
    except Exception as e:
        logger.error(f"Error in plug_and_play_register_device: {str(e)}")
        return f"❌ Registration error: {str(e)}"

def usb_scan_and_send_ean(ean_barcode, device_id=None):
    """USB barcode scan - send EAN number with quantity 1 to IoT Hub"""
    try:
        # Get device ID from local storage if not provided
        if not device_id:
            device_id = local_db.get_device_id()
            if not device_id:
                return "❌ No device registered. Please register device first."
        
        # Always use quantity 1 for EAN barcode scans
        quantity = 1
        
        # Save EAN scan to local database with quantity 1
        timestamp = local_db.save_scan(device_id, ean_barcode, quantity)
        
        # Send EAN to IoT Hub
        config = load_config()
        devices = config.get("iot_hub", {}).get("devices", {})
        
        if device_id in devices:
            connection_string = devices[device_id]["connection_string"]
            
            # Use persistent connection manager
            success = connection_manager.send_message(device_id, connection_string, ean_barcode)
            
            if success:
                local_db.mark_sent_to_hub(device_id, ean_barcode, timestamp)
                return f"✅ EAN {ean_barcode} sent to IoT Hub!\n✅ Device: {device_id}\n✅ Quantity: {quantity} (always 1 for EAN scans)\n✅ Saved in local database\n🔗 Connection: Persistent"
            else:
                return f"⚠️ EAN {ean_barcode} saved locally, IoT Hub send failed"
        else:
            return f"❌ Device {device_id} not found in IoT Hub config"
            
    except Exception as e:
        logger.error(f"Error in usb_scan_and_send_ean: {str(e)}")
        return f"❌ Error: {str(e)}"

def send_barcode_to_iot(barcode, device_id):
    """Send barcode directly to IoT Hub with proper error handling"""
    try:
        # Save to local database first
        timestamp = local_db.save_scan(device_id, barcode, 1)
        
        # Check if online
        if not api_client.is_online():
            return f"⚠️ Offline: Barcode {barcode} saved locally, will send when online"
        
        # Load config and get connection string
        config = load_config()
        if not config:
            return f"❌ Config error: Barcode {barcode} saved locally"
        
        # Get device connection string
        devices_config = config.get("iot_hub", {}).get("devices", {})
        if device_id in devices_config:
            connection_string = devices_config[device_id]["connection_string"]
        else:
            # Register device with IoT Hub if not found
            registration_result = register_device_with_iot_hub(device_id)
            if registration_result.get("success"):
                config = load_config()  # Reload config
                connection_string = config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string")
            else:
                connection_string = config.get("iot_hub", {}).get("connection_string")
        
        if not connection_string:
            return f"❌ No IoT connection: Barcode {barcode} saved locally"
        
        # Send to IoT Hub
        hub_client = HubClient(connection_string)
        success = hub_client.send_message(barcode, device_id)
        
        if success:
            local_db.mark_sent_to_hub(device_id, barcode, timestamp)
            return f"✅ Barcode {barcode} sent to IoT Hub successfully!"
        else:
            return f"⚠️ IoT send failed: Barcode {barcode} saved locally for retry"
            
    except Exception as e:
        logger.error(f"Error sending barcode to IoT: {str(e)}")
        return f"❌ Error: {str(e)}. Barcode saved locally."

def quick_scan_barcode(barcode, device_id):
    """Quick barcode scan function for real-time scanning"""
    if not barcode or not device_id:
        return "❌ Please provide both barcode and device ID"
    
    # Ensure device is registered
    local_db.save_device_id(device_id)
    
    # Send to IoT Hub with quantity 1
    result = send_barcode_to_iot(barcode, device_id)
    
    return f"📱 Quick Scan Result:\n{result}\n✅ Quantity: 1 (always)"

def simulate_offline_mode():
    """Simulate being offline by overriding the is_online method"""
    global simulated_offline_mode
    simulated_offline_mode = True
    logger.info("⚠️ Simulated OFFLINE mode activated")
    return "⚠️ OFFLINE mode simulated. Barcodes will be stored locally and sent when 'online'."

def simulate_online_mode():
    """Restore normal online mode checking"""
    global simulated_offline_mode
    simulated_offline_mode = False
    logger.info("✅ Simulated OFFLINE mode deactivated - normal operation restored")
    result = process_unsent_messages(auto_retry=False)
    return "✅ Online mode restored. Any pending messages will now be sent.\n\n" + (result or "")

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
    """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error."""
    try:
        logger.info(f"Blinking {color} LED on Raspberry Pi.")
    except Exception as e:
        logger.error(f"LED blink error: {str(e)}")

def generate_registration_token():
    """Step 1: Generate a dynamic registration token for device registration"""
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

def confirm_registration(registration_token, device_id):
    """Step 2: Confirm device registration using token and device ID"""
    try:
        if not registration_token or registration_token.strip() == "":
            blink_led("red")
            return "❌ Please enter a valid registration token."
        
        if not device_id or device_id.strip() == "":
            blink_led("red")
            return "❌ Please enter a valid Device ID."
        
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
        
        is_online = api_client.is_online()
        
        # Gather device info for registration
        device_info = {
            "registration_method": "dynamic_token",
            "online_at_registration": is_online,
            "user_agent": "Barcode Scanner App v2.0"
        }
        
        # Register device with dynamic device manager
        success, reg_message = device_manager.register_device(registration_token, device_id, device_info)
        if not success:
            blink_led("red")
            return f"❌ Registration failed: {reg_message}"
        
        # Save device ID locally for backward compatibility
        local_db.save_device_id(device_id)
        
        if not is_online:
            blink_led("orange")
            return f"⚠️ Device is offline. Device ID '{device_id}' registered locally. Will sync with IoT Hub when online."
        
        # Register device with IoT Hub if available and online
        if IOT_HUB_REGISTRY_AVAILABLE:
            iot_result = register_device_with_iot_hub(device_id)
            if not iot_result.get("success", False):
                logger.warning(f"IoT Hub registration failed: {iot_result.get('message', 'Unknown error')}")
                # Continue with local registration even if IoT Hub fails
        
        # Send confirmation message to IoT Hub
        try:
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                hub_client = HubClient(config["iot_hub"]["connection_string"], device_id)
                confirmation_message = {
                    "deviceId": device_id,
                    "status": "registered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Device registration confirmed via dynamic token",
                    "registration_token": registration_token
                }
                
                # Try to send confirmation to IoT Hub
                hub_success = hub_client.send_message(json.dumps(confirmation_message), device_id)
            else:
                logger.warning("IoT Hub configuration not available")
                hub_success = False
            if hub_success:
                logger.info(f"Registration confirmation sent to IoT Hub for device {device_id}")
            else:
                logger.warning(f"Failed to send registration confirmation to IoT Hub for device {device_id}")
                # Store message for retry later
                local_db.save_unsent_message(device_id, json.dumps(confirmation_message), datetime.now())
                
        except Exception as hub_error:
            logger.error(f"Error sending confirmation to IoT Hub: {str(hub_error)}")
            # Store message for retry later
            confirmation_message = {
                "deviceId": device_id,
                "status": "registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Device registration confirmed via dynamic token",
                "registration_token": registration_token
            }
            local_db.save_unsent_message(device_id, json.dumps(confirmation_message), datetime.now())
        
        blink_led("green")
        return f"""✅ Device registration completed successfully!

**Device ID:** {device_id}
**Status:** Registered and ready to scan barcodes
**IoT Hub:** {'Connected' if is_online else 'Will sync when online'}
**Registration Method:** Dynamic Token

**You can now use the 'Send Barcode' feature with any valid barcode.**"""
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

def process_barcode_scan(barcode, device_id=None):
    """Unified function to handle barcode scanning with dynamic device validation"""
    try:
        if not barcode or barcode.strip() == "":
            blink_led("red")
            return "❌ Please enter a barcode."
        
        barcode = barcode.strip()
        
        # For normal barcode processing, we need a device ID
        if not device_id or device_id.strip() == "":
            # Try to get device ID from local storage
            stored_device_id = local_db.get_device_id()
            if stored_device_id:
                device_id = stored_device_id
                logger.info(f"Using stored device ID: {device_id}")
            else:
                blink_led("red")
                return "❌ No device ID provided and no registered device found. Please register your device first."
        
        device_id = device_id.strip()
        
        # Dynamic device validation
        can_send, permission_msg = device_manager.can_device_send_barcode(device_id)
        if not can_send:
            blink_led("red")
            return f"❌ {permission_msg}"
        
        # Dynamic barcode validation for this device
        is_valid_barcode, barcode_msg = device_manager.validate_barcode_for_device(barcode, device_id)
        if not is_valid_barcode:
            blink_led("red")
            return f"❌ {barcode_msg}"
        
        # Validate the barcode format (optional - can be disabled for more flexibility)
        try:
            validation_result = validate_ean(barcode)
            if not validation_result.is_valid:
                logger.warning(f"Barcode format validation failed: {validation_result.error_message}")
                # Continue processing - dynamic system allows non-EAN barcodes
        except BarcodeValidationError as e:
            logger.warning(f"Barcode validation error: {str(e)}")
            # Continue processing - dynamic system is more flexible
        
        # Check if we're online
        is_online = api_client.is_online()
        
        if not is_online:
            # Store barcode locally for later processing
            timestamp = datetime.now()
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            blink_led("orange")
            return f"⚠️ Device is offline. Barcode '{barcode}' saved locally for device '{device_id}'. Will be sent when online."
        
        # Process barcode online
        try:
            # Send to API
            api_success = api_client.send_barcode(barcode, device_id)
            if not api_success:
                # Store locally if API fails
                timestamp = datetime.now()
                local_db.save_barcode_scan(device_id, barcode, timestamp)
                blink_led("orange")
                return f"⚠️ API call failed. Barcode '{barcode}' saved locally for device '{device_id}'. Will retry when connection is restored."
            
            # Send to IoT Hub
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                hub_client = HubClient(config["iot_hub"]["connection_string"], device_id)
                hub_success = hub_client.send_message(barcode, device_id)
            else:
                logger.warning("IoT Hub configuration not available")
                hub_success = False
            
            if hub_success:
                blink_led("green")
                return f"✅ Barcode '{barcode}' sent successfully from device '{device_id}' to both API and IoT Hub."
            else:
                # Store for IoT Hub retry
                timestamp = datetime.now()
                local_db.save_unsent_message(device_id, barcode, timestamp)
                blink_led("orange")
                return f"⚠️ Barcode '{barcode}' sent to API but failed to send to IoT Hub from device '{device_id}'. Stored for retry."
                
        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            # Store locally as fallback
            timestamp = datetime.now()
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            blink_led("red")
            return f"❌ Error processing barcode '{barcode}': {str(e)}. Stored locally for retry."
        
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

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
    """Process any unsent messages in the local database and try to send them to IoT Hub"""
    try:
        # Check if we're online
        if not api_client.is_online():
            return "Device is offline. Cannot process unsent messages."
            
        # Get unsent messages from local database
        unsent_messages = local_db.get_unsent_scans()
        if not unsent_messages:
            return "No unsent messages to process."
            
        # Load configuration
        config = load_config()
        if not config:
            return "Error: Failed to load configuration"
            
        # Get default connection string
        default_connection_string = config.get("iot_hub", {}).get("connection_string", None)
        if not default_connection_string:
            return "Error: No default connection string provided."
            
        # Create IoT Hub client
        hub_client = HubClient(default_connection_string)
        
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
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                success_count += 1
                continue
            
            # Determine connection string for the device
            devices_config = config.get("iot_hub", {}).get("devices", {})
            if device_id in devices_config:
                connection_string = devices_config[device_id]["connection_string"]
            else:
                connection_string = default_connection_string
                
            # Create a new client for each message
            message_client = HubClient(connection_string)
            
            # Create payload with quantity
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Try to send the message with quantity
            success = message_client.send_message(barcode, device_id)
            
            if success:
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
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
                scan_test_barcode_button = gr.Button("1. Scan Test Barcode (817994ccfe14)", variant="primary")
                confirm_registration_button = gr.Button("2. Confirm Registration", variant="primary")
                
            with gr.Row():
                registration_status_button = gr.Button("Check Registration Status")
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
    
    registration_status_button.click(
        fn=get_registration_status,
        inputs=[],
        outputs=[status_text]
    )
    
    process_unsent_button.click(
        fn=lambda: process_unsent_messages(auto_retry=False),
        inputs=[],
        outputs=[status_text]
    )
    
    # Offline simulation handlers
    simulate_offline_button.click(
        fn=simulate_offline_mode,
        inputs=[],
        outputs=[offline_status_text]
    )

    simulate_online_button.click(
        fn=simulate_online_mode,
        inputs=[],
        outputs=[offline_status_text]
    )

# For testing offline mode
simulated_offline_mode = False

def simulate_offline_mode():
    """Simulate being offline by overriding the is_online method"""
    global simulated_offline_mode
    simulated_offline_mode = True
    logger.info("⚠️ Simulated OFFLINE mode activated")
    return "⚠️ OFFLINE mode simulated. Barcodes will be stored locally and sent when 'online'."  

def simulate_online_mode():
    """Restore normal online mode checking"""
    global simulated_offline_mode
    simulated_offline_mode = False
    logger.info("✅ Simulated OFFLINE mode deactivated - normal operation restored")
    result = process_unsent_messages(auto_retry=False)
    return "✅ Online mode restored. Any pending messages will now be sent.\n\n" + (result or "")

def register_device_with_iot_hub(device_id):
    """Fast device registration with Azure IoT Hub - optimized for speed
    
    Args:
        device_id (str): The device ID to register
        
    Returns:
        dict: A dictionary with success status and error message if applicable
    """
    if not IOT_HUB_REGISTRY_AVAILABLE:
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
            
            # Save updated config only if new device was created
            if "devices" not in config["iot_hub"] or device_id not in config["iot_hub"]["devices"]:
                save_config(config)
                logger.info(f"Config file updated with device {device_id} connection string")
            else:
                logger.info(f"Device {device_id} already in config, skipping save")
            
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
    """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error."""
    try:
        logger.info(f"Blinking {color} LED on Raspberry Pi.")
    except Exception as e:
        logger.error(f"LED blink error: {str(e)}")

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        # Only allow the test barcode for registration
        if barcode != "817994ccfe14":
            blink_led("red")
            return "❌ Only the test barcode (817994ccfe14) can be used for registration."
        
        is_online = api_client.is_online()
        if not is_online:
            blink_led("red")
            return "❌ Device is offline. Cannot register device."
        
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
        
        # Save test barcode scan locally (but not device ID yet - that happens in confirmation)
        local_db.save_test_barcode_scan(barcode)
        
        # Send response to frontend
        response_msg = f"""✅ Test barcode {barcode} processed successfully!

**API Calls Completed:**
• First call: {api_result_1.get('message', 'Success')}
• Second call: {api_result_2.get('message', 'Success')}

**Next Step:** Click 'Confirm Registration' to complete the process."""
        
        return response_msg
        
    except Exception as e:
        logger.error(f"Error in register_device_id: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

def confirm_registration(barcode, device_id):
    """Step 2: Frontend confirms registration, send confirmation message, save device in DB, send to IoT"""
    try:
        # Check if test barcode has been scanned
        test_scan = local_db.get_test_barcode_scan()
        if not test_scan:
            blink_led("red")
            return "❌ No test barcode scanned. Please scan the test barcode (817994ccfe14) first."
        
        is_online = api_client.is_online()
        if not is_online:
            blink_led("red")
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
            blink_led("yellow")  # Use yellow to indicate already registered
            
            return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}

**Status:** This device is already registered and ready for barcode scanning operations.
No need to register again."""
        
        # Skip validation step as the endpoint doesn't exist
        # Instead, we'll rely on the confirmation API to validate the device ID
        
        # Call confirmRegistration API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": test_scan['barcode']}
        
        logger.info(f"Confirming registration with API: {api_url}")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        # Check for API errors in the response
        if not api_result.get("success", False):
            blink_led("red")
            error_msg = api_result.get('message', 'Unknown error')
            
            # Check if the error contains "Device not found"
            if "Device not found" in error_msg:
                # Try direct registration with saveDeviceId endpoint
                save_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                save_payload = {"scannedBarcode": device_id}
                
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
                            blink_led("green")
                            
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
                    blink_led("red")
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
            blink_led("yellow")  # Use yellow to indicate already registered
            
            return f"""⚠️ Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Test Barcode: {test_scan['barcode']}

**Status:** This device is already registered and ready for barcode scanning operations.
No need to register again."""
        
        # Save device ID to database if not already registered
        local_db.save_device_id(device_id)
        
        # Register device with IoT Hub (fast registration without quantity messages)
        try:
            config = load_config()
            if config:
                # Get IoT Hub owner connection string for device registration
                owner_connection_string = config.get("iot_hub", {}).get("connection_string", None)
                if not owner_connection_string:
                    iot_status = "⚠️ No IoT Hub connection string configured"
                else:
                    # Fast device registration - only register, don't send messages
                    registration_result = register_device_with_iot_hub(device_id)
                    if registration_result.get("success"):
                        logger.info(f"Device {device_id} registered successfully with IoT Hub")
                        iot_status = "✅ Device registered with IoT Hub (no quantity messages sent)"
                    else:
                        logger.error(f"Failed to register device {device_id}: {registration_result.get('error')}")
                        iot_status = f"⚠️ Failed to register device: {registration_result.get('error')}"
            else:
                iot_status = "⚠️ Configuration not loaded"
        except Exception as iot_error:
            logger.error(f"IoT Hub error: {iot_error}")
            iot_status = f"⚠️ IoT Hub error: {str(iot_error)}"
        
        # Blink green LED for success
        blink_led("green")
        
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
        blink_led("red")
        return f"❌ Error: {str(e)}"

def process_barcode_scan(barcode, device_id=None):
    """Process a barcode scan and determine if it's a valid product or device ID"""
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
                            return f"⚠️ Barcode {barcode} scanned and saved locally, but failed to register device with IoT Hub."
                        
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                        success = hub_client.send_message(barcode, current_device_id)
                        if success:
                            return f"✅ Barcode {barcode} scanned and sent to IoT Hub successfully!"
                        else:
                            return f"⚠️ Barcode {barcode} scanned and saved locally, but failed to send to IoT Hub."
                    else:
                        return f"⚠️ Barcode {barcode} scanned and saved locally, but no device connection string available."
                else:
                    return f"⚠️ Barcode {barcode} scanned and saved locally, but configuration not loaded."
            except Exception as e:
                logger.error(f"Error sending to IoT Hub: {e}")
                return f"⚠️ Barcode {barcode} scanned and saved locally, but error sending to IoT Hub: {str(e)}"
        
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
                                    # Don't use owner connection string as fallback - it will cause DeviceId error
                                    device_connection_string = None
                                    logger.error(f"Cannot proceed without device-specific connection string")
                            
                            if device_connection_string:
                                hub_client = HubClient(device_connection_string)
                                registration_message = {
                                    "scannedBarcode": barcode,
                                    "deviceId": device_id,
                                    "messageType": "registration",
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                                
                                iot_success = hub_client.send_message(barcode, device_id)
                                iot_status = "✅ Sent to IoT Hub" if iot_success else "⚠️ Failed to send to IoT Hub"
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
            
            # Check if we're online
            is_online = api_client.is_online()
            if not is_online:
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
                    return f"❌ Error: Device ID '{device_id}' not found in configuration and no default connection string provided."
            
            # Create IoT Hub client
            hub_client = HubClient(connection_string)
            
            # Send message (connection is handled internally)
            success = hub_client.send_message(validated_barcode, device_id, 1)
            
            if success:
                # Mark as sent in local database
                local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
                return f"✅ Barcode {validated_barcode} scanned and sent to IoT Hub successfully!"
            else:
                return f"⚠️ Barcode {validated_barcode} scanned and saved locally, but failed to send to IoT Hub."
    
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
        # Check if we're online
        if not api_client.is_online():
            return "Device is offline. Cannot process unsent messages."
            
        # Get unsent messages from local database
        unsent_messages = local_db.get_unsent_scans()
        if not unsent_messages:
            return "No unsent messages to process."
            
        # Load configuration
        config = load_config()
        if not config:
            return "Error: Failed to load configuration"
            
        # Get default connection string
        default_connection_string = config.get("iot_hub", {}).get("connection_string", None)
        if not default_connection_string:
            return "Error: No default connection string provided."
            
        # Create IoT Hub client
        hub_client = HubClient(default_connection_string)
        
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
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                success_count += 1
                continue
            
            # Determine connection string for the device
            devices_config = config.get("iot_hub", {}).get("devices", {})
            if device_id in devices_config:
                connection_string = devices_config[device_id]["connection_string"]
            else:
                connection_string = default_connection_string
                
            # Create a new client for each message
            message_client = HubClient(connection_string)
            
            # Create payload with quantity
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Try to send the message with quantity
            success = message_client.send_message(barcode, device_id)
            
            if success:
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
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
                scan_test_barcode_button = gr.Button("1. Scan Test Barcode (817994ccfe14)", variant="primary")
                confirm_registration_button = gr.Button("2. Confirm Registration", variant="primary")
                
            with gr.Row():
                registration_status_button = gr.Button("Check Registration Status")
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
    
    registration_status_button.click(
        fn=get_registration_status,
        inputs=[],
        outputs=[status_text]
    )
    
    process_unsent_button.click(
        fn=lambda: process_unsent_messages(auto_retry=False),
        inputs=[],
        outputs=[status_text]
    )
    
    # Offline simulation handlers
    simulate_offline_button.click(
        fn=simulate_offline_mode,
        inputs=[],
        outputs=[offline_status_text]
    )

    simulate_online_button.click(
        fn=simulate_online_mode,
        inputs=[],
        outputs=[offline_status_text]
    )
    
    # USB Scanner Controls
    gr.Markdown("### USB Scanner Controls")
    with gr.Row():
        detect_usb_button = gr.Button("Detect USB Scanner")
        toggle_auto_scan_button = gr.Button("Toggle Auto-Scan", variant="secondary")
        
    with gr.Row():
        get_usb_barcode_button = gr.Button("Get USB Barcode")
        auto_process_button = gr.Button("Auto-Process Scanned Barcodes", variant="secondary")
    
    # Plug-and-Play Registration
    gr.Markdown("### Plug-and-Play Registration")
    plug_device_input = gr.Textbox(label="Device ID", placeholder="Enter device ID for plug-and-play registration")
    with gr.Row():
        plug_register_button = gr.Button("Plug-and-Play Register", variant="primary")
    
    # USB EAN Scan
    gr.Markdown("### USB EAN Scan (Quantity 1)")
    with gr.Row():
        ean_input = gr.Textbox(label="EAN Barcode", placeholder="Enter EAN number")
        ean_device_input = gr.Textbox(label="Device ID", placeholder="Device ID (optional)")
    ean_scan_button = gr.Button("Send EAN to IoT Hub", variant="primary")
    
    # USB Scanner event handlers
    detect_usb_button.click(
        fn=detect_usb_scanner,
        inputs=[],
        outputs=[output_text]
    )
    
    toggle_auto_scan_button.click(
        fn=toggle_auto_scan,
        inputs=[],
        outputs=[output_text]
    )
    
    get_usb_barcode_button.click(
        fn=get_usb_scanner_barcode,
        inputs=[],
        outputs=[barcode_input, output_text]
    )
    
    auto_process_button.click(
        fn=auto_process_scanned_barcodes,
        inputs=[],
        outputs=[output_text]
    )
    
    # Plug-and-Play Registration event handler
    plug_register_button.click(
        fn=plug_and_play_register_device,
        inputs=[plug_device_input],
        outputs=[status_text]
    )
    
    # USB EAN Scan event handler
    ean_scan_button.click(
        fn=usb_scan_and_send_ean,
        inputs=[ean_input, ean_device_input],
        outputs=[output_text]
    )

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=78610)