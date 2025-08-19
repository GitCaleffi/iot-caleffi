"""
Dynamic Barcode Scanner Application
Scalable for 50,000+ users with no hardcoded device dependencies
"""

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
from barcode_validator import validate_ean, BarcodeValidationError

logger = logging.getLogger(__name__)

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config
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
1. Copy this token to the 'Registration Token' field below
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
            "user_agent": "Barcode Scanner App v2.0 Dynamic"
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
            hub_client = HubClient()
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
            hub_client = HubClient()
            hub_success = hub_client.send_message(barcode, device_id)
            
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
        # Get device stats from dynamic device manager
        stats = device_manager.get_registration_stats()
        
        # Get local device info
        local_device_id = local_db.get_device_id()
        
        status_text = "# Device Registration Status\n\n"
        
        if local_device_id:
            device_info = device_manager.get_device_info(local_device_id)
            if device_info:
                status_text += f"✅ **Local Device:** {local_device_id} (Registered)\n"
                status_text += f"**Registration Method:** {device_info.get('device_info', {}).get('registration_method', 'Legacy')}\n"
                status_text += f"**Registered At:** {device_info.get('registered_at', 'Unknown')}\n"
                status_text += f"**Last Seen:** {device_info.get('last_seen', 'Unknown')}\n"
                status_text += f"**Status:** {device_info.get('status', 'Unknown')}\n\n"
            else:
                status_text += f"⚠️ **Local Device:** {local_device_id} (Legacy registration)\n\n"
        else:
            status_text += "❌ **Local Device:** Not registered\n\n"
        
        # System-wide statistics
        status_text += "## System Statistics\n"
        status_text += f"**Total Devices:** {stats['total_devices']}\n"
        status_text += f"**Active Devices:** {stats['active_devices']}\n"
        status_text += f"**Inactive Devices:** {stats['inactive_devices']}\n"
        status_text += f"**Pending Registrations:** {stats['pending_registrations']}\n"
        status_text += f"**Total Tokens Generated:** {stats['total_tokens_generated']}\n"
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        return f"❌ Error: {str(e)}"

def get_device_statistics():
    """Get detailed device statistics for administrators"""
    try:
        stats = device_manager.get_registration_stats()
        all_devices = device_manager.get_all_devices()
        
        stats_text = "# Device Statistics Dashboard\n\n"
        
        # Overview
        stats_text += "## Overview\n"
        stats_text += f"- **Total Registered Devices:** {stats['total_devices']}\n"
        stats_text += f"- **Active Devices:** {stats['active_devices']}\n"
        stats_text += f"- **Inactive Devices:** {stats['inactive_devices']}\n"
        stats_text += f"- **Pending Registrations:** {stats['pending_registrations']}\n"
        stats_text += f"- **Total Registration Tokens Generated:** {stats['total_tokens_generated']}\n\n"
        
        # Recent devices
        if all_devices:
            stats_text += "## Recent Device Registrations\n"
            sorted_devices = sorted(all_devices.items(), 
                                  key=lambda x: x[1].get('registered_at', ''), 
                                  reverse=True)[:10]
            
            for device_id, device_info in sorted_devices:
                reg_method = device_info.get('device_info', {}).get('registration_method', 'Legacy')
                status = device_info.get('status', 'Unknown')
                registered_at = device_info.get('registered_at', 'Unknown')[:19]  # Remove microseconds
                
                stats_text += f"- **{device_id}** ({status}) - {reg_method} - {registered_at}\n"
        
        return stats_text
        
    except Exception as e:
        logger.error(f"Error getting device statistics: {str(e)}")
        return f"❌ Error: {str(e)}"

def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them to IoT Hub"""
    try:
        # Get unsent messages from local database
        unsent_messages = local_db.get_unsent_messages()
        
        if not unsent_messages:
            result_msg = "No unsent messages found."
            logger.info(result_msg)
            if not auto_retry:
                return result_msg
            return None
        
        success_count = 0
        fail_count = 0
        
        # Create IoT Hub client
        hub_client = HubClient()
        
        for device_id, barcode, timestamp, quantity in unsent_messages:
            # Check if device is still registered and active
            can_send, _ = device_manager.can_device_send_barcode(device_id)
            if not can_send:
                logger.warning(f"Skipping unsent message for inactive device: {device_id}")
                fail_count += 1
                continue
            
            # Create payload with quantity
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": quantity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Try to send the message with quantity
            success = hub_client.send_message(barcode, device_id)
            
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

def register_device_with_iot_hub(device_id):
    """Register a device with Azure IoT Hub and update the config file"""
    try:
        if not IOT_HUB_REGISTRY_AVAILABLE:
            return {"success": False, "message": "Azure IoT Hub Registry Manager not available"}
        
        config = load_config()
        if not config:
            return {"success": False, "message": "Configuration not loaded"}
        
        iot_hub_config = config.get("iot_hub", {})
        connection_string = iot_hub_config.get("connection_string")
        
        if not connection_string:
            return {"success": False, "message": "IoT Hub connection string not configured"}
        
        # Create registry manager
        registry_manager = IoTHubRegistryManager(connection_string)
        
        # Create device
        primary_key = os.urandom(32).hex()
        secondary_key = os.urandom(32).hex()
        
        device = Device(
            device_id=device_id,
            authentication=AuthenticationMechanism(
                symmetric_key=SymmetricKey(
                    primary_key=primary_key,
                    secondary_key=secondary_key
                )
            ),
            capabilities=DeviceCapabilities(iot_edge=False)
        )
        
        # Register device
        created_device = registry_manager.create_device_with_sas(device)
        
        logger.info(f"Device {device_id} registered successfully with IoT Hub")
        return {"success": True, "message": f"Device {device_id} registered with IoT Hub"}
        
    except Exception as e:
        logger.error(f"Error registering device with IoT Hub: {str(e)}")
        return {"success": False, "message": str(e)}

# Create Gradio interface with dynamic device management
with gr.Blocks(title="Dynamic Barcode Scanner", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🔍 Dynamic Barcode Scanner")
    gr.Markdown("*Scalable for 50,000+ users with no hardcoded device dependencies*")
    
    with gr.Row():
        # Left column for barcode scanning
        with gr.Column():
            gr.Markdown("## 📱 Scan Barcode")
            
            barcode_input = gr.Textbox(label="Barcode", placeholder="Scan or enter any barcode")
            device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID (optional if registered)")
            
            with gr.Row():
                send_button = gr.Button("📤 Send Barcode", variant="primary", size="lg")
                clear_button = gr.Button("🗑️ Clear", variant="secondary")
                
            output_text = gr.Markdown("")
            
        # Right column for device registration & management
        with gr.Column():
            gr.Markdown("## 🔐 Device Registration & Management")
            
            gr.Markdown("### Dynamic Registration Process")
            with gr.Row():
                generate_token_button = gr.Button("1️⃣ Generate Registration Token", variant="primary")
                confirm_registration_button = gr.Button("2️⃣ Confirm Registration", variant="primary")
            
            registration_token_input = gr.Textbox(
                label="Registration Token", 
                placeholder="Enter registration token from step 1",
                type="password"
            )
            
            with gr.Row():
                # registration_status_button = gr.Button("📊 Check Registration Status")
                process_unsent_button = gr.Button("🔄 Process Unsent Messages")
                device_stats_button = gr.Button("📈 View Device Statistics")
                
            status_text = gr.Markdown("")
            
            with gr.Row():
                gr.Markdown("### 🧪 Test Offline Mode")
                simulate_offline_button = gr.Button("📴 Simulate Offline Mode")
                simulate_online_button = gr.Button("📶 Restore Online Mode")
            
            offline_status_text = gr.Markdown("**Current mode:** 🟢 Online")
            
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
    
    # Dynamic registration handlers
    def handle_token_generation():
        msg, token = generate_registration_token()
        return msg, token
    
    generate_token_button.click(
        fn=handle_token_generation,
        inputs=[],
        outputs=[status_text, registration_token_input]
    )
    
    confirm_registration_button.click(
        fn=confirm_registration,
        inputs=[registration_token_input, device_id_input],
        outputs=[status_text]
    )
    
    registration_status_button.click(
        fn=get_registration_status,
        inputs=[],
        outputs=[status_text]
    )
    
    device_stats_button.click(
        fn=get_device_statistics,
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
    # Clean up expired tokens on startup
    device_manager.cleanup_expired_tokens()
    
    # Launch the application
    app.launch(
        server_name="0.0.0.0", 
        server_port=7862,  # Different port to avoid conflicts
        share=False,
        show_error=True
    )
