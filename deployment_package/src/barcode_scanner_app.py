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
from utils.barcode_validator import validate_ean, BarcodeValidationError

logger = logging.getLogger(__name__)

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config, save_config
from iot.hub_client import HubClient
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

def process_barcode_scan(barcode, device_id):
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
            validated_barcode = validate_ean(barcode)
            logger.info(f"Barcode validation successful: {validated_barcode}")
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
                # Device exists, no need to create it again
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
            
            # Update config file only if device is not already configured
            if "devices" not in config["iot_hub"]:
                config["iot_hub"]["devices"] = {}
            
            # Check if device already exists in config before updating
            device_already_in_config = device_id in config["iot_hub"].get("devices", {})
            
            if not device_already_in_config:
                config["iot_hub"]["devices"][device_id] = {
                    "connection_string": connection_string,
                    "deviceId": device_id
                }
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

def register_device_id(barcode, device_id=None):
    """Step 1: Scan test barcode on registered device, use correct API payload format"""
    try:
        # Only allow the test barcode for registration
        if barcode != "817994ccfe14":
            blink_led("red")
            return "❌ Only the test barcode (817994ccfe14) can be used for registration."
        
        is_online = api_client.is_online()
        if not is_online:
            blink_led("red")
            return "❌ Device is offline. Cannot register device."
        
        # Use provided device_id or get from pending registration
        if not device_id:
            # Check if there's a pending device ID from keyboard scanner
            pending_device = getattr(register_device_id, '_pending_device_id', None)
            if pending_device:
                device_id = pending_device
            else:
                # Generate a device ID as fallback
                import uuid
                device_id = str(uuid.uuid4())[:12]
        
        # If device_id is the same as test barcode, generate a different device ID
        if device_id == barcode:
            import uuid
            device_id = str(uuid.uuid4())[:12]
            logger.info(f"Device ID was same as test barcode, generated new device ID: {device_id}")
        
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        # Use the correct payload format with both scannedBarcode and testBarcode
        payload = {
            "scannedBarcode": device_id,
            "testBarcode": barcode
        }
        
        logger.info(f"Making API call to {api_url} with payload: {payload}")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        if not api_result.get("success", False):
            blink_led("red")
            return f"❌ API call failed: {api_result.get('message', 'Unknown error')}"
        
        # Check for isTestBarcodeVerified in the response
        response_text = api_result.get("response", "{}")
        try:
            response_data = json.loads(response_text)
        except:
            response_data = {}
        
        is_test_verified = response_data.get("data", {}).get("isTestBarcodeVerified", False)
        
        # If isTestBarcodeVerified is not found, check if the response indicates success
        if not is_test_verified:
            # Check if the API response indicates success
            response_code = response_data.get("responseCode", 0)
            if response_code == 200 and "successful" in api_result.get("message", "").lower():
                is_test_verified = True
            else:
                blink_led("red")
                return f"❌ Test barcode verification failed. Response: {api_result.get('message', 'Unknown error')}"
        
        # Save test barcode scan locally with the device ID
        local_db.save_test_barcode_scan(barcode)
        local_db.save_device_id(device_id)  # Save the device ID for later use
        
        # Clear pending device ID
        if hasattr(register_device_id, '_pending_device_id'):
            delattr(register_device_id, '_pending_device_id')
        
        # IoT Hub registration is handled by register_device_with_iot_hub() above
        # No need to send additional messages during registration
        logger.info(f"Device {device_id} registration completed - IoT Hub messaging handled by registration process")
        
        # Send response to frontend
        response_msg = f"""✅ Device registered successfully!

**Device Details:**
• Device ID: {device_id}
• Test Barcode: {barcode}
• Test Barcode Verified: ✅ {is_test_verified}

**API Response:**
• Status: {api_result.get('message', 'Success')}
• Customer ID: {response_data.get('data', {}).get('customerId', 'N/A')}

**Next Step:** Device is ready for barcode scanning operations."""
        
        blink_led("green")
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
            
            # Initialize status tracking
            iot_status = "❌ Not sent"
            api_status = "❌ Not sent"
            pos_status = "❌ Not sent"
            
            # 1. Send quantity update to Frontend API (for client-side updates)
            try:
                logger.info(f"Sending quantity update to API for barcode: {barcode}")
                api_result = api_client.send_barcode_scan(current_device_id, barcode, 1)
                if api_result.get("success"):
                    api_status = "✅ Sent to API"
                    logger.info(f"Successfully sent quantity update to API: {barcode}")
                else:
                    api_status = "⚠️ API failed"
                    logger.warning(f"Failed to send quantity update to API: {api_result.get('message', 'Unknown error')}")
            except Exception as e:
                api_status = f"⚠️ API error: {str(e)}"
                logger.error(f"Error sending quantity update to API: {e}")
            
            # 2. Send quantity update to IoT Hub (for cloud processing)
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
                            iot_status = f"⚠️ Registration failed"
                        
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                        success = hub_client.send_message(barcode, current_device_id)
                        if success:
                            iot_status = "✅ Sent to IoT Hub"
                            logger.info(f"Successfully sent quantity update to IoT Hub: {barcode}")
                        else:
                            iot_status = "⚠️ IoT Hub failed"
                            logger.warning(f"Failed to send quantity update to IoT Hub: {barcode}")
                    else:
                        iot_status = "⚠️ No connection string"
                        logger.warning(f"No device connection string available for IoT Hub")
                else:
                    iot_status = "⚠️ Config not loaded"
                    logger.warning(f"Configuration not loaded for IoT Hub")
            except Exception as e:
                iot_status = f"⚠️ IoT Hub error: {str(e)}"
                logger.error(f"Error sending to IoT Hub: {e}")
            
            # 3. POS forwarding enabled with smart filtering to prevent feedback loops
            try:
                from utils.usb_hid_forwarder import get_hid_forwarder
                hid_forwarder = get_hid_forwarder()
                
                # Only forward actual product barcodes, not test/device barcodes
                if len(barcode) >= 8 and barcode not in ["817994ccfe14", "36928f67f397"]:
                    pos_forwarded = hid_forwarder.forward_barcode(barcode)
                    pos_status = "✅ Sent to POS" if pos_forwarded else "⚠️ POS forward failed"
                    logger.info(f"POS forwarding result for {barcode}: {pos_status}")
                else:
                    pos_status = "⚠️ POS forwarding skipped (test/device barcode)"
                    logger.info(f"POS forwarding skipped for {barcode}: {pos_status}")
            except Exception as e:
                pos_status = f"⚠️ POS error: {str(e)}"
                logger.error(f"Error forwarding to POS: {e}")
            
            # Return comprehensive status
            return f"""📦 QUANTITY UPDATE - BARCODE: {barcode}

**Actions Completed:**
• ✅ Saved to local database
• {api_status}
• {iot_status}  
• {pos_status}

**Device ID:** {current_device_id}
**Timestamp:** {timestamp}

**Status:** Barcode scan processed through all channels!"""
        
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

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7861)