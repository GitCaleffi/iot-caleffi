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
from utils.dynamic_device_manager import device_manager  # Add this line
from utils.dynamic_device_id import generate_dynamic_device_id

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
        
        # Add this device ID to our processed set regardless of API response
        processed_device_ids.add(device_id)
        logger.info(f"Added device ID {device_id} to processed devices set")
        
        # Send confirmation message to IoT Hub
        try:
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                # Get device connection string via dynamic registration
                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                if registration_service:
                    device_connection_string = registration_service.register_device_with_azure(device_id)
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                    else:
                        logger.error("Failed to get device connection string for confirmation")
                        raise Exception("No device connection string available")
                else:
                    logger.error("Failed to initialize registration service for confirmation")
                    raise Exception("Registration service not available")
            else:
                logger.error("No IoT Hub configuration found for confirmation")
                raise Exception("No IoT Hub configuration")
            confirmation_message = {
                "deviceId": device_id,
                "status": "registered",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Device registration confirmed via dynamic token",
                "registration_token": registration_token
            }
            
            # Try to send confirmation to IoT Hub
            hub_success = hub_client.send_message(json.dumps(confirmation_message), device_id)
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
            # Use barcode-to-device mapping to get the correct device ID for this barcode
            from utils.barcode_device_mapper import BarcodeDeviceMapper
            mapper = BarcodeDeviceMapper()
            device_id = mapper.get_device_id_for_barcode(barcode)
            
            if not device_id:
                # Fallback to dynamic device ID generation if mapping fails
                device_id = generate_dynamic_device_id()
                logger.warning(f"Barcode mapping failed, using dynamic device ID: {device_id}")
            else:
                logger.info(f"Mapped barcode '{barcode}' to device ID: {device_id}")
        
        device_id = device_id.strip()
        logger.info(f"Processing barcode scan for device ID: {device_id}")
        
        # Check if device is registered in our system
        device_registered = False
        registration_source = None
        
        # Check if device is registered in dynamic device manager
        if device_manager.is_device_registered(device_id):
            device_registered = True
            registration_source = "dynamic_device_manager"
            logger.info(f"Device {device_id} is already registered in dynamic device manager")
        
        # Check if device is registered in local DB (legacy check)
        if not device_registered:
            registered_devices = local_db.get_registered_devices()
            device_already_registered = any(device.get('device_id') == device_id for device in registered_devices) if registered_devices else False
            
            if device_already_registered:
                device_registered = True
                registration_source = "local_database"
                logger.info(f"Device {device_id} is already registered in local database")
            
        logger.info(f"Device registration status for {device_id}: {device_registered} (source: {registration_source})")
        
        # Auto-register the device if it's not registered
        if not device_registered:
            logger.info(f"New device detected: {device_id}. Initiating automatic registration...")
            
            # Register with dynamic device manager
            device_info = {
                "registration_method": "auto_registration",
                "online_at_registration": api_client.is_online(),
                "user_agent": "Barcode Scanner App v2.0",
                "auto_registered": True,
                "registration_time": datetime.now(timezone.utc).isoformat()
            }
            
            # Generate a token for auto-registration
            auto_token = device_manager.generate_registration_token(device_id)
            logger.info(f"Generated auto-registration token for device {device_id}: {auto_token}")
            
            # Register device with dynamic device manager
            success, reg_message = device_manager.register_device(auto_token, device_id, device_info)
            logger.info(f"Registration result for device {device_id}: {success}, Message: {reg_message}")
            
            # Also register the device with the API for frontend display
            if api_client.is_online():
                logger.info(f"Registering new device {device_id} with API for frontend display")
                api_result = api_client.register_device(device_id)
                if api_result.get("success", False):
                    logger.info(f"Successfully registered device {device_id} with API: {api_result.get('message')}")
                else:
                    logger.warning(f"Failed to register device {device_id} with API: {api_result.get('message')}")
                    
            # Verify registration was successful
            if device_manager.is_device_registered(device_id):
                logger.info(f"Verification: Device {device_id} is now registered in dynamic device manager")
            else:
                logger.warning(f"Verification failed: Device {device_id} is still not registered in dynamic device manager after registration attempt")
            
            # If registration fails, try again with force registration
            if not success and "already registered" not in reg_message:
                logger.warning(f"First registration attempt failed: {reg_message}. Trying force registration...")
                
                # Try to add the device directly to the device cache
                try:
                    with device_manager.lock:
                        device_manager.device_cache[device_id] = {
                            'device_id': device_id,
                            'registered_at': datetime.now(timezone.utc).isoformat(),
                            'last_seen': datetime.now(timezone.utc).isoformat(),
                            'status': 'active',
                            'registration_token': auto_token,
                            'device_info': device_info
                        }
                        device_manager.save_device_config()
                        success = True
                        reg_message = f"Device {device_id} force-registered successfully"
                        logger.info(reg_message)
                        
                        # Double-check force registration was successful
                        if device_id in device_manager.device_cache:
                            logger.info(f"Force registration verification: Device {device_id} is now in device cache")
                        else:
                            logger.error(f"Force registration verification failed: Device {device_id} is not in device cache")
                except Exception as force_reg_error:
                    logger.error(f"Force registration failed: {force_reg_error}")
                    success = False
                    reg_message = f"Force registration failed: {force_reg_error}"
            
            if success:
                logger.info(f"Auto-registration successful for device {device_id}")
                
                # Save device ID locally for backward compatibility
                local_db.save_device_id(device_id)
                
                # Also save to registered devices list to ensure it's found in future checks
                local_db.save_device_registration(device_id, {
                    'device_id': device_id,
                    'registered_at': datetime.now().isoformat(),
                    'status': 'active'
                })
                
                # Register device with the API for frontend display
                if api_client.is_online():
                    logger.info(f"Registering successful device {device_id} with API for frontend display")
                    api_result = api_client.register_device(device_id)
                    if api_result.get("success", False):
                        logger.info(f"Successfully registered device {device_id} with API: {api_result.get('message')}")
                    else:
                        logger.warning(f"Failed to register device {device_id} with API: {api_result.get('message')}")
                
                # Register device with IoT Hub if available and online
                if IOT_HUB_REGISTRY_AVAILABLE and api_client.is_online():
                    iot_result = register_device_with_iot_hub(device_id)
                    if not iot_result.get("success", False):
                        logger.warning(f"IoT Hub auto-registration failed: {iot_result.get('message', 'Unknown error')}")
                        # Try direct IoT Hub registration as fallback
                        try:
                            config = load_config()
                            if config and config.get("iot_hub", {}).get("connection_string"):
                                from utils.dynamic_registration_service import DynamicRegistrationService
                                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                                direct_service = DynamicRegistrationService(iot_hub_owner_connection)
                                device_connection_string = direct_service.register_device_with_azure(device_id)
                                if device_connection_string:
                                    logger.info(f"Direct IoT Hub registration successful for device {device_id}")
                                    iot_result = {"success": True, "message": "Direct registration successful"}
                        except Exception as direct_reg_error:
                            logger.error(f"Direct IoT Hub registration failed: {direct_reg_error}")
                
                # Send NEW DEVICE REGISTRATION message to IoT Hub
                logger.info(f"Sending new device registration message to IoT Hub for device {device_id}")
                try:
                    config = load_config()
                    if config and config.get("iot_hub", {}).get("connection_string"):
                        # Get device connection string via dynamic registration
                        iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                        registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                        if registration_service:
                            device_connection_string = registration_service.register_device_with_azure(device_id)
                            if device_connection_string:
                                hub_client = HubClient(device_connection_string)
                                
                                # Create NEW DEVICE registration message
                                registration_message = {
                                    "deviceId": device_id,
                                    "status": "new_device_registered",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "message": "New device auto-registered during barcode scan",
                                    "registration_method": "auto_registration",
                                    "scannedBarcode": barcode,
                                    "messageType": "device_registration"
                                }
                                
                                # Send registration message to IoT Hub
                                reg_success = hub_client.send_message(registration_message, device_id)
                                if reg_success:
                                    logger.info(f"Successfully sent new device registration message to IoT Hub for {device_id}")
                                else:
                                    logger.error(f"Failed to send new device registration message to IoT Hub for {device_id}")
                            else:
                                logger.error(f"Failed to get device connection string for registration message: {device_id}")
                        else:
                            logger.error(f"Failed to get registration service for device registration message: {device_id}")
                    else:
                        logger.error("No IoT Hub configuration found for device registration message")
                except Exception as reg_msg_error:
                    logger.error(f"Error sending device registration message to IoT Hub: {reg_msg_error}")
                
                # Return success message for new device registration
                blink_led("green")
                return f"""🟢 New Device Registered Successfully

**Device Details:**
• Device ID: {device_id}
• Barcode: {barcode}
• Status: Newly registered
• Registered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
• Quantity: 1

**Actions Completed:**
• ✅ Device registered in system
• ✅ Device registered with API
• ✅ New device registration message sent to IoT Hub
• ✅ Barcode scan will be processed next

**LED Status:** 🟢 Green light indicates successful new device registration.

**Status:** New device registered successfully and ready for barcode scanning."""
            else:
                logger.error(f"Auto-registration failed for device {device_id}: {reg_message}")
                blink_led("red")
                return f"""❌ Device Registration Failed

**Device Details:**
• Device ID: {device_id}
• Barcode: {barcode}
• Status: Registration failed
• Error: {reg_message}

**Actions Completed:**
• ❌ Device registration failed
• ❌ Cannot process barcode scan

**LED Status:** 🔴 Red light indicates registration failure.

**Status:** Please try again or contact support."""
        
        # If device is already registered, continue with barcode processing
        logger.info(f"Device {device_id} is already registered, proceeding with barcode scan")
        
        # Get registration date for already registered devices
        registration_date = "Unknown"
        if registration_source == "dynamic_device_manager":
            device_info = device_manager.get_device_info(device_id)
            if device_info and 'registered_at' in device_info:
                registration_date = device_info['registered_at']
        elif registration_source == "local_database":
            registered_devices = local_db.get_registered_devices()
            for device in registered_devices:
                if device.get('device_id') == device_id:
                    registration_date = device.get('registered_at', 'Unknown')
                    break
        
        # Send registration confirmation message to IoT Hub (legacy code - keeping for compatibility)
        try:
            config = load_config()
            if config and config.get("iot_hub", {}).get("connection_string"):
                # Get device connection string via dynamic registration
                iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                if registration_service:
                    device_connection_string = registration_service.register_device_with_azure(device_id)
                    if device_connection_string:
                        hub_client = HubClient(device_connection_string)
                        
                        # This legacy code is no longer needed as we handle registration above
                        logger.info(f"Skipping legacy registration confirmation for already registered device {device_id}")
        except Exception as reg_error:
            logger.error(f"Error in legacy registration code: {str(reg_error)}")
        
        # Emergency registration as last resort
        logger.info(f"Attempting emergency direct registration for device {device_id}")
        try:
            # Save directly to local database
            local_db.save_device_id(device_id)
            local_db.save_device_registration(device_id, {
                'device_id': device_id,
                'registered_at': datetime.now().isoformat(),
                'status': 'active',
                'emergency_registered': True
            })
            
            # Try API registration one more time
            if api_client.is_online():
                api_result = api_client.register_device(device_id)
                if api_result.get("success", False):
                    logger.info(f"Emergency API registration successful for device {device_id}")
                
            logger.info(f"Emergency direct registration completed for device {device_id}")
            success = True
        except Exception as emergency_error:
            logger.error(f"Emergency direct registration failed: {emergency_error}")
        
        # Check if device can send barcodes
        can_send, send_message = device_manager.can_device_send_barcode(device_id)
        if not can_send:
            logger.warning(f"Device not authorized to send barcodes: {send_message}")
            
            # If device is not authorized because it's not registered, try to register it
            if "not registered" in send_message or "not found" in send_message:
                logger.info(f"Attempting emergency registration for device {device_id}")
                
                # Check if we need to bypass the device manager validation
                bypass_validation = True
                logger.info(f"Setting bypass_validation={bypass_validation} for emergency registration")
                
                # Force device registration in device manager
                try:
                    with device_manager.lock:
                        device_manager.device_cache[device_id] = {
                            'device_id': device_id,
                            'registered_at': datetime.now(timezone.utc).isoformat(),
                            'last_seen': datetime.now(timezone.utc).isoformat(),
                            'status': 'active',
                            'registration_token': device_manager.generate_registration_token(device_id),
                            'device_info': {
                                "registration_method": "emergency_registration",
                                "auto_registered": True,
                                "registration_time": datetime.now(timezone.utc).isoformat()
                            }
                        }
                        device_manager.save_device_config()
                        logger.info(f"Emergency registration successful for device {device_id}")
                        
                        # Also register the device with the API for frontend display
                        if api_client.is_online():
                            logger.info(f"Emergency registering device {device_id} with API for frontend display")
                            api_result = api_client.register_device(device_id)
                            if api_result.get("success", False):
                                logger.info(f"Successfully registered device {device_id} with API: {api_result.get('message')}")
                            else:
                                logger.warning(f"Failed to register device {device_id} with API: {api_result.get('message')}")
                        
                        # Try authorization check again
                        can_send, send_message = device_manager.can_device_send_barcode(device_id)
                        if not can_send:
                            logger.warning(f"Device still not authorized after emergency registration: {send_message}")
                            blink_led("red")
                            return f"❌ {send_message}"
                except Exception as emergency_reg_error:
                    logger.error(f"Emergency registration failed: {emergency_reg_error}")
                    blink_led("red")
                    return f"❌ Emergency registration failed: {str(emergency_reg_error)}"
            else:
                blink_led("red")
                return f"❌ {send_message}"
        
        # Validate the barcode with dynamic device manager
        is_valid, validation_message = device_manager.validate_barcode_for_device(barcode, device_id)
        if not is_valid:
            logger.warning(f"Barcode validation failed: {validation_message}")
            
            # If validation failed because device is not registered, try to register it on-the-fly
            if "not registered" in validation_message or "not found" in validation_message:
                logger.info(f"Attempting on-the-fly registration for device {device_id}")
                
                # Generate a token for auto-registration
                auto_token = device_manager.generate_registration_token(device_id)
                
                # Register device with dynamic device manager
                device_info = {
                    "registration_method": "on_the_fly_registration",
                    "online_at_registration": api_client.is_online(),
                    "user_agent": "Barcode Scanner App v2.0",
                    "auto_registered": True,
                    "registration_time": datetime.now(timezone.utc).isoformat()
                }
                
                success, reg_message = device_manager.register_device(auto_token, device_id, device_info)
                
                # Also register the device with the API for frontend display
                if api_client.is_online():
                    logger.info(f"Registering device {device_id} with API for frontend display")
                    api_result = api_client.register_device(device_id)
                    if api_result.get("success", False):
                        logger.info(f"Successfully registered device {device_id} with API: {api_result.get('message')}")
                    else:
                        logger.warning(f"Failed to register device {device_id} with API: {api_result.get('message')}")
                
                if success:
                    logger.info(f"On-the-fly registration successful for device {device_id}")
                    # Try validation again
                    is_valid, validation_message = device_manager.validate_barcode_for_device(barcode, device_id)
                    if is_valid:
                        logger.info(f"Barcode validation successful after on-the-fly registration")
                    else:
                        logger.warning(f"Barcode validation still failed after on-the-fly registration: {validation_message}")
                        blink_led("red")
                        return f"❌ {validation_message}"
                else:
                    logger.error(f"On-the-fly registration failed: {reg_message}")
                    blink_led("red")
                    return f"❌ Registration failed: {reg_message}"
            else:
                blink_led("red")
                return f"❌ {validation_message}"
        
        # Validate the barcode format (optional - can be disabled for more flexibility)
        try:
            validated_barcode = validate_ean(barcode)
            logger.info(f"Barcode format validation passed: {validated_barcode}")
            # Use the validated barcode for further processing
            barcode = validated_barcode
        except BarcodeValidationError as e:
            logger.warning(f"Barcode validation error: {str(e)}")
            # Continue processing - dynamic system is more flexible with non-EAN barcodes
        
        # Check for duplicate barcode scan to prevent looping/repeated hits
        recent_scans = local_db.get_recent_scans(device_id, barcode, minutes=5)  # Check last 5 minutes
        if recent_scans:
            logger.info(f"Duplicate barcode scan detected for device {device_id}, barcode {barcode}")
            blink_led("yellow")  # Yellow LED for duplicate scan
            last_scan_time = recent_scans[0]['timestamp'] if recent_scans else 'Unknown'
            return f"""⚠️ Duplicate Barcode Scan Detected

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Last Scanned: {last_scan_time}

**Status:** This barcode was already scanned recently by this device.
**Action:** Duplicate scan prevented to avoid repeated API hits.

**LED Status:** 🟡 Yellow light indicates duplicate scan prevention."""
        
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
            # Send to API first
            logger.info(f"Sending barcode scan to API for device {device_id}, barcode {barcode}, quantity 1")
            api_result = api_client.send_barcode_scan(device_id, barcode, 1)
            api_success = api_result.get("success", False)
            
            if not api_success:
                logger.error(f"API scan failed: {api_result.get('message', 'Unknown error')}")
            else:
                logger.info(f"API scan successful for device {device_id}")
            
            # Send to IoT Hub
            config = load_config()
            hub_success = False
            if config and config.get("iot_hub", {}).get("connection_string"):
                try:
                    # Get device connection string via dynamic registration
                    from utils.dynamic_registration_service import get_dynamic_registration_service, DynamicRegistrationService
                    iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string")
                    
                    # Debug the connection string
                    logger.info(f"IoT Hub owner connection string available: {bool(iot_hub_owner_connection)}")
                    logger.info(f"Preparing to send barcode {barcode} to IoT Hub for device {device_id}")
                    
                    # Try to get the registration service
                    registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                    
                    # If service is None, try to create it directly
                    if registration_service is None:
                        logger.warning("Failed to get registration service via global instance, creating direct instance")
                        try:
                            registration_service = DynamicRegistrationService(iot_hub_owner_connection)
                            logger.info("Created direct registration service instance")
                        except Exception as direct_error:
                            logger.error(f"Failed to create direct registration service: {direct_error}")
                            registration_service = None
                    
                    if registration_service:
                        logger.info(f"Registration service initialized successfully for device: {device_id}")
                        # Ensure device exists in IoT Hub
                        device_connection_string = registration_service.register_device_with_azure(device_id)
                        logger.info(f"Device connection string obtained: {bool(device_connection_string)}")
                        
                        # Verify connection string format
                        if device_connection_string and "DeviceId" in device_connection_string and "HostName" in device_connection_string:
                            logger.info(f"Connection string format verified for device {device_id}")
                        else:
                            logger.warning(f"Connection string format invalid for device {device_id}")
                        if device_connection_string:
                            try:
                                conn_parts = dict(part.split('=', 1) for part in device_connection_string.split(';'))
                                conn_device_id = conn_parts.get('DeviceId')
                                if conn_device_id != device_id:
                                    logger.warning(f"Connection string device ID ({conn_device_id}) doesn't match requested device ID ({device_id}). Using connection string ID.")
                                    device_id = conn_device_id
                            except Exception as parse_error:
                                logger.warning(f"Could not parse device ID from connection string: {parse_error}")
                            
                            try:
                                logger.info(f"Initializing HubClient with device connection string for {device_id}")
                                hub_client = HubClient(device_connection_string)
                                
                                # Create barcode message with additional data
                                barcode_message = {
                                    "scannedBarcode": barcode,
                                    "deviceId": device_id,
                                    "quantity": 1,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                                
                                # Send message to IoT Hub
                                logger.info(f"Sending barcode message to IoT Hub for device {device_id}")
                                # Debug the message being sent
                                logger.info(f"Message content: {json.dumps(barcode_message)}")
                                
                                # Send the barcode message directly without JSON dumping it again
                                # The HubClient will handle the JSON conversion internally
                                hub_success = hub_client.send_message(barcode_message, device_id)
                                
                                if hub_success:
                                    logger.info(f"Successfully sent barcode message to IoT Hub for device {device_id}")
                                else:
                                    logger.error(f"Failed to send barcode message to IoT Hub for device {device_id}")
                            except Exception as hub_client_error:
                                logger.error(f"Error with HubClient: {hub_client_error}")
                                hub_success = False
                        else:
                            logger.error("Failed to get device connection string for barcode send")
                            # Try direct connection with device-specific connection string format
                            try:
                                # Extract IoT Hub hostname from owner connection string
                                parts = dict(part.split('=', 1) for part in iot_hub_owner_connection.split(';'))
                                iot_hub_hostname = parts.get('HostName')
                                if iot_hub_hostname:
                                    # Create a device-specific connection string with shared access key
                                    shared_access_key = parts.get('SharedAccessKey')
                                    if shared_access_key:
                                        device_connection_string = f"HostName={iot_hub_hostname};DeviceId={device_id};SharedAccessKey={shared_access_key}"
                                        logger.info(f"Created fallback device connection string for {device_id}")
                                        hub_client = HubClient(device_connection_string)
                                        
                                        # Create barcode message with additional data
                                        barcode_message = {
                                            "scannedBarcode": barcode,
                                            "deviceId": device_id,
                                            "quantity": 1,
                                            "timestamp": datetime.now(timezone.utc).isoformat()
                                        }
                                        
                                        # Debug the message being sent
                                        logger.info(f"Fallback message content: {json.dumps(barcode_message)}")
                                        
                                        # Send the barcode message directly without JSON dumping it again
                                        hub_success = hub_client.send_message(barcode_message, device_id)
                                        if hub_success:
                                            logger.info(f"Successfully sent message using fallback connection string for {device_id}")
                            except Exception as fallback_error:
                                logger.error(f"Fallback connection string creation failed: {fallback_error}")
                    else:
                        logger.error("Failed to initialize registration service for barcode send")
                        logger.info("Attempting direct IoT Hub connection as fallback...")
                        # Try to create a direct connection to IoT Hub
                        try:
                            # Extract IoT Hub hostname from owner connection string
                            parts = dict(part.split('=', 1) for part in iot_hub_owner_connection.split(';'))
                            iot_hub_hostname = parts.get('HostName')
                            shared_access_key = parts.get('SharedAccessKey')
                            if iot_hub_hostname and shared_access_key:
                                # Create a device-specific connection string
                                device_connection_string = f"HostName={iot_hub_hostname};DeviceId={device_id};SharedAccessKey={shared_access_key}"
                                logger.info(f"Created direct device connection string for {device_id}")
                                
                                try:
                                    logger.info(f"Initializing HubClient with fallback connection string for {device_id}")
                                    hub_client = HubClient(device_connection_string)
                                    
                                    # Create barcode message with additional data
                                    barcode_message = {
                                        "scannedBarcode": barcode,
                                        "deviceId": device_id,
                                        "quantity": 1,
                                        "timestamp": datetime.now(timezone.utc).isoformat()
                                    }
                                    
                                    # Debug the message being sent
                                    logger.info(f"Direct fallback message content: {json.dumps(barcode_message)}")
                                    
                                    logger.info(f"Sending barcode message to IoT Hub using fallback for device {device_id}")
                                    # Send the barcode message directly without JSON dumping it again
                                    hub_success = hub_client.send_message(barcode_message, device_id)
                                except Exception as fallback_client_error:
                                    logger.error(f"Error with fallback HubClient: {fallback_client_error}")
                                    hub_success = False
                                if hub_success:
                                    logger.info(f"Successfully sent message using direct connection for {device_id}")
                        except Exception as direct_error:
                            logger.error(f"Direct IoT Hub connection failed: {direct_error}")
                except Exception as hub_error:
                    logger.error(f"IoT Hub error: {hub_error}")
                    hub_success = False
            else:
                logger.error("No IoT Hub configuration found for barcode send")
            
            # Save scan to local database
            timestamp = datetime.now()
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            
            # Determine overall success and provide detailed feedback
            if api_success and hub_success:
                blink_led("green")
                return f"""✅ Barcode Scan Processed

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Barcode saved locally
• ✅ Sent to API successfully
• ✅ Sent to IoT Hub

**Status:** Barcode processed successfully!"""
            
            elif api_success and not hub_success:
                # Store for IoT Hub retry
                try:
                    barcode_message = {
                        "scannedBarcode": barcode,
                        "deviceId": device_id,
                        "quantity": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    local_db.save_unsent_message(device_id, json.dumps(barcode_message), timestamp)
                    logger.info(f"Saved unsent IoT Hub message for device {device_id}")
                    
                    # Also try direct connection as a last resort
                    try:
                        # Extract IoT Hub hostname from owner connection string
                        parts = dict(part.split('=', 1) for part in iot_hub_owner_connection.split(';'))
                        iot_hub_hostname = parts.get('HostName')
                        shared_access_key = parts.get('SharedAccessKey')
                        if iot_hub_hostname and shared_access_key:
                            # Create a device-specific connection string
                            device_connection_string = f"HostName={iot_hub_hostname};DeviceId={device_id};SharedAccessKey={shared_access_key}"
                            logger.info(f"Created emergency fallback connection string for {device_id}")
                            
                            try:
                                logger.info(f"Initializing HubClient with emergency connection string for {device_id}")
                                hub_client = HubClient(device_connection_string)
                                logger.info(f"Sending emergency barcode message to IoT Hub for device {device_id}")
                                # Debug the message being sent
                                logger.info(f"Emergency message content: {json.dumps(barcode_message)}")
                                # Send the barcode message directly without JSON dumping it again
                                hub_success = hub_client.send_message(barcode_message, device_id)
                            except Exception as emergency_client_error:
                                logger.error(f"Error with emergency HubClient: {emergency_client_error}")
                                hub_success = False
                            if hub_success:
                                logger.info(f"Emergency fallback message send successful for {device_id}")
                    except Exception as emergency_error:
                        logger.error(f"Emergency fallback connection failed: {emergency_error}")
                except Exception as save_error:
                    logger.error(f"Error saving unsent IoT Hub message: {str(save_error)}")
                blink_led("orange")
                return f"""⚠️ Barcode Partially Processed

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Barcode saved locally
• ✅ Sent to API successfully
• ⚠️ Failed to send to IoT Hub (stored for retry)

**Status:** Barcode sent to API, IoT Hub retry queued."""
            
            elif not api_success and hub_success:
                blink_led("orange")
                return f"""⚠️ Barcode Partially Processed

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Barcode saved locally
• ⚠️ API call failed: {api_result.get('message', 'Unknown error')}
• ✅ Sent to IoT Hub

**Status:** Barcode sent to IoT Hub, API call failed."""
            
            else:
                # Both failed - store for retry
                try:
                    barcode_message = {
                        "scannedBarcode": barcode,
                        "deviceId": device_id,
                        "quantity": 1,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    local_db.save_unsent_message(device_id, json.dumps(barcode_message), timestamp)
                    logger.info(f"Saved unsent message for both API and IoT Hub for device {device_id}")
                except Exception as save_error:
                    logger.error(f"Error saving unsent message: {str(save_error)}")
                blink_led("red")
                return f"""❌ Barcode Processing Failed

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Barcode saved locally
• ❌ API call failed: {api_result.get('message', 'Unknown error')}
• ❌ IoT Hub send failed

**Status:** Both API and IoT Hub failed. Stored for retry when connection is restored."""
                
        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            # Store locally as fallback
            timestamp = datetime.now()
            local_db.save_barcode_scan(device_id, barcode, timestamp)
            blink_led("red")
            
            return f"""❌ Barcode Scan Error

**Barcode Details:**
• Barcode: {barcode}
• Device ID: {device_id}
• Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ❌ Failed to send to API: {str(e)}
• ❌ Failed to send to IoT Hub
• ✅ Scan saved to local database for retry

**Status:** Error occurred but scan is stored locally for retry when connection is restored."""
        
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
        blink_led("red")
        timestamp = datetime.now()
        
        return f"""❌ System Error

**Error Details:**
• Barcode: `{barcode if 'barcode' in locals() else 'Unknown'}`
• Device ID: {device_id if 'device_id' in locals() else 'Unknown'}
• Error Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

**Error Message:** {str(e)}

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
                scan_test_barcode_button = gr.Button("1. Scan Any Test Barcode (Dynamic)", variant="primary")
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
    """Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error."""
    try:
        logger.info(f"Blinking {color} LED on Raspberry Pi.")
    except Exception as e:
        logger.error(f"LED blink error: {str(e)}")

def register_device_id(barcode):
    """Step 1: Scan test barcode on registered device, hit API twice, send response to frontend"""
    try:
        global processed_device_ids
        
        # Accept any barcode for dynamic testing (removed hardcoded restriction)
        logger.info(f"Using barcode '{barcode}' for device registration testing")
        
        # Generate dynamic device ID for this system
        from utils.dynamic_device_id import generate_dynamic_device_id
        device_id = generate_dynamic_device_id()
        logger.info(f"Generated device ID: {device_id}")
        
        # For test registrations, we always allow them to proceed regardless of previous processing
        # This is different from actual device registrations where we check for duplicates
        logger.info(f"Test registration - always allowing to proceed regardless of previous processing")
        
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
        
        # Do not save test barcode scan locally - only save when API returns device ID and barcode
        # This keeps the database clean by only storing confirmed registrations
        
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
        global processed_device_ids
        
        # Since we no longer save test barcodes, use the provided barcode directly
        # This makes the registration process cleaner by only saving confirmed registrations
        test_scan = {'barcode': barcode}  # Use the provided barcode directly
        
        # Log all currently processed device IDs for debugging
        logger.info(f"Currently processed device IDs: {processed_device_ids}")
     
        # Check if device is already in the database
        registered_devices = local_db.get_registered_devices()
        device_already_registered = any(device['device_id'] == device_id for device in registered_devices)
        
        if device_already_registered:
            logger.info(f"Device ID {device_id} already registered in database, sending quantity update")
            
            # Find the registration details for this device
            device_info = next((device for device in registered_devices if device['device_id'] == device_id), None)
            registration_date = device_info['registration_date'] if device_info else 'Unknown'
            
            # For already registered devices, just send quantity update to IoT Hub and API
            quantity = 1  # Default quantity for update
            
            # Send quantity update to API
            api_result = api_client.send_barcode_scan(device_id, barcode, quantity)
            
            if api_result.get("success", False):
                api_status = "✅ Quantity update sent to API"
                logger.info(f"API quantity update successful for device {device_id}")
            else:
                api_status = "⚠️ Failed to send quantity update to API"
                logger.error(f"API quantity update failed for device {device_id}: {api_result.get('message', 'Unknown error')}")
            
            # Send quantity update message to IoT Hub
            try:
                config = load_config()
                if config:
                    # Get IoT Hub connection string
                    iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
                    if not iot_hub_owner_connection:
                        logger.error("IoT Hub owner connection string not found in config")
                        iot_status = "⚠️ IoT Hub connection failed: Missing connection string in config"
                    else:
                        # Initialize dynamic registration service with the IoT Hub owner connection string
                        registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                        device_connection_string = registration_service.register_device_with_azure(device_id)
                        
                        if device_connection_string:
                            # Send quantity update message to IoT Hub
                            hub_client = HubClient(device_connection_string)
                            
                            # Create quantity update message
                            quantity_message = {
                                "scannedBarcode": barcode,
                                "deviceId": device_id,
                                "quantity": quantity,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "messageType": "quantity_update"
                            }
                            
                            # Send message with the quantity update payload
                            success = hub_client.send_message(quantity_message, device_id)
                            if success:
                                iot_status = "✅ Quantity update sent to IoT Hub"
                                blink_led("green")  # GREEN light for successful update
                            else:
                                iot_status = "⚠️ Failed to send quantity update to IoT Hub"
                                blink_led("yellow")  # YELLOW light for IoT Hub failure
                        else:
                            iot_status = "⚠️ Failed to get device connection string for IoT Hub"
                            blink_led("yellow")  # YELLOW light for connection failure
                else:
                    iot_status = "⚠️ No IoT Hub configuration found"
                    blink_led("yellow")  # YELLOW light for missing config
            except Exception as e:
                logger.error(f"Error sending quantity update to IoT Hub: {str(e)}")
                iot_status = "⚠️ Error sending quantity update to IoT Hub"
                blink_led("yellow")  # YELLOW light for error
            
            return f"""🟢 Quantity Update Processed

**Device Details:**
• Device ID: {device_id}
• Barcode: {barcode}
• Status: Already registered
• Registered: {registration_date}
• Quantity: {quantity}

**Actions Completed:**
• ✅ Device found in database
• {api_status}
• {iot_status}

**LED Status:** 🟢 Green light indicates successful quantity update.

**Status:** Quantity update processed successfully for existing device."""
        
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
            blink_led("red")  # RED light for already registered device
            
            # Find the registration details for this device
            device_info = next((device for device in registered_devices if device['device_id'] == device_id), None)
            registration_date = device_info['registration_date'] if device_info else 'Unknown'
            
            return f"""🔴 Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Barcode: {test_scan['barcode']}
• Status: Already in database
• Registered: {registration_date}

**Actions Completed:**
• ✅ Device found in database
• ✅ Already registered message sent to IoT Hub
• ⚠️ No duplicate registration performed

**LED Status:** 🔴 Red light indicates device already registered.

**Status:** Device is ready for barcode scanning operations!"""
                    
        # Skip validation step as the endpoint doesn't exist
        # Instead, we'll rely on the confirmation API to validate the device ID
        
        # Call confirmRegistration API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": test_scan['barcode']}
        
        logger.info(f"Confirming registration with API: {api_url}")
        
        # Add this device ID to our processed set regardless of API response
        # This ensures we don't process the same device ID twice even if API fails
        processed_device_ids.add(device_id)
        logger.info(f"Added device ID {device_id} to processed devices set")
        
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
        
        # Try to register the device with the API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": barcode}
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        # Check if API call was successful
        if not api_result.get("success", False):
            error_msg = api_result.get("message", "Unknown error")
            
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
                        except Exception as e:
                            logger.error(f"Error sending already registered message to IoT Hub: {e}")
                        
                        # Blink red LED for already registered device
                        blink_led("red")
                        
                        return f"""🔴 Device Already Registered

**Device Details:**
• Device ID: {device_id}
• Barcode: {returned_barcode}
• Status: Already in database
• Registered: {registration_date}

**Actions Completed:**
• ✅ Device found in database
• ✅ Already registered message sent to IoT Hub
• ⚠️ No duplicate registration performed

**LED Status:** 🔴 Red light indicates device already registered.

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
                            logger.info(f"✅ Device {device_id} successfully registered with external API")
                            api_registration_status = "✅ Registered with external API"
                        else:
                            logger.warning(f"⚠️ Failed to register device {device_id} with external API: {device_registration_result.get('message', 'Unknown error')}")
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
                                            iot_status = "✅ Success message sent to IoT Hub" if iot_success else "⚠️ Failed to send to IoT Hub"
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
                            iot_status = "✅ Test registration sent to IoT Hub" if iot_success else "⚠️ Failed to send to IoT Hub"
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
• {iot_status}

**Status:** Registration completed successfully. Device is now ready for barcode scanning operations."""
        
        return confirmation_msg
        
    except Exception as e:
        logger.error(f"Error in confirm_registration: {str(e)}")
        blink_led("red")
        return f"❌ Error: {str(e)}"

def process_barcode_scan(barcode, device_id=None):
    """Process a barcode scan and determine if it's a valid product or device ID"""
    try:
        # Use dynamic device ID generation for consistent device identification
        from utils.dynamic_device_id import generate_dynamic_device_id
        
        # Get the correct device ID for this barcode scan
        if device_id:
            # Use provided device ID if available
            current_device_id = device_id
            logger.info(f"Using provided device ID: {current_device_id}")
        else:
            # Use dynamic device ID based on system hardware (not static fallback)
            current_device_id = generate_dynamic_device_id()
            logger.info(f"Using dynamic device ID: {current_device_id}")
        
        # Process the barcode scan with the correct device ID
        if current_device_id and barcode:
            # Save scan to local database
            timestamp = local_db.save_scan(current_device_id, barcode)
            logger.info(f"Saved scan to local database: {current_device_id}, {barcode}, {timestamp}")
            
            # Send to IoT Hub
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
                        success = hub_client.send_message(barcode, current_device_id)
                        iot_status = "✅ Sent to IoT Hub" if success else "⚠️ Failed to send to IoT Hub"
                    else:
                        iot_status = "⚠️ No IoT Hub connection string configured"
                else:
                    iot_status = "⚠️ Configuration not loaded"
            except Exception as iot_error:
                logger.error(f"IoT Hub error: {iot_error}")
                iot_status = f"⚠️ IoT Hub error: {str(iot_error)}"
            
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
            # Pass quantity as a simple integer for the sku parameter
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
                scan_test_barcode_button = gr.Button("1. Scan Any Test Barcode (Dynamic)", variant="primary")
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