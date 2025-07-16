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

# Initialize database and API client
local_db = LocalStorage()
api_client = ApiClient()

# For testing offline mode
simulated_offline_mode = False

def simulate_offline_mode():
    """
    Simulate being offline by overriding the is_online method
    """
    global simulated_offline_mode
    simulated_offline_mode = True
    logger.info("⚠️ Simulated OFFLINE mode activated")
    return "⚠️ OFFLINE mode simulated. Barcodes will be stored locally and sent when 'online'."  

def simulate_online_mode():
    """
    Restore normal online mode checking
    """
    global simulated_offline_mode
    simulated_offline_mode = False
    logger.info("✅ Simulated OFFLINE mode deactivated - normal operation restored")
    # Process any pending messages immediately
    result = process_unsent_messages(auto_retry=False)
    return "✅ Online mode restored. Any pending messages will now be sent.\n\n" + (result or "")

# Override the is_online method for testing
orig_is_online = api_client.is_online

def patched_is_online():
    """
    Patched version of is_online that respects simulated_offline_mode
    """
    if simulated_offline_mode:
        return False
    return orig_is_online()
    
api_client.is_online = patched_is_online

# Setup message retry system
retry_queue = queue.Queue()
retry_thread = None
retry_interval = 300  # seconds (increased from 60 to 300 - 5 minutes)
retry_running = False
retry_lock = threading.Lock()
last_queue_check = datetime.now()
retry_enabled = False  # Flag to enable/disable retry worker - DISABLED to prevent multiple entries

def validate_device_id(barcode):
    """
    Validate if a barcode is a valid device ID by calling the API
    
    Args:
        barcode (str): The barcode to validate
        
    Returns:
        dict: Validation result with isValid, responseMessage, and deviceId if valid
    """
    try:
        # Use API client to validate the device ID
        return api_client.validate_device_id(barcode)
    except Exception as e:
        logger.error(f"Error validating device ID: {str(e)}")
        return {"isValid": False, "responseMessage": f"Error: {str(e)}"}

def process_unsent_messages(auto_retry=False):
    """
    Process any unsent messages in the local database and try to send them to IoT Hub
    
    Args:
        auto_retry (bool): If True, this is an automatic retry and no UI message will be returned
    
    Returns:
        str: Status message about processed messages (if not auto_retry)
        None: If auto_retry is True
    """
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
        print(f"hub_____",HubClient)
        
        # Process each unsent message
        success_count = 0
        fail_count = 0
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["barcode"]
            timestamp = message["timestamp"]
            quantity = message.get("quantity", 1)  # Default to 1 if not present
            
            # Check if this is a test barcode - if so, skip sending to IoT Hub
            if api_client.is_test_barcode(barcode):
                logger.info(f"Skipping test barcode in unsent messages: {barcode} - BLOCKED from IoT Hub")
                # Mark as sent to remove it from unsent queue, but don't actually send to IoT Hub
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                success_count += 1  # Count as success since we handled it appropriately
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
            success = message_client.send_message(message_payload)
            
            if success:
                # Mark as sent in local database
                local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                success_count += 1
            else:
                fail_count += 1
                
        result_msg = f"Processed {len(unsent_messages)} unsent messages. Success: {success_count}, Failed: {fail_count}"
        logger.info(result_msg)
        
        # If auto retry and there are still failures, schedule another retry
        if auto_retry and fail_count > 0:
            schedule_retry()
            
        # Only return a message if this is not an auto retry
        if not auto_retry:
            return result_msg
        return None
        
    except Exception as e:
        error_msg = f"Error processing unsent messages: {str(e)}"
        logger.error(error_msg)
        
        # Schedule retry on failure if this is automatic
        if auto_retry:
            schedule_retry()
            return None
        return error_msg

def fetch_available_devices():
    """
    Step 1: Fetch available device IDs from the registration API and store in local database
    
    Returns:
        str: Status message about the fetch operation
    """
    try:
        # Check if we're online
        if not api_client.is_online():
            return "❌ Device is offline. Cannot fetch available device IDs."
        
        # Fetch available device IDs from API
        result = api_client.get_available_device_ids()
        
        if result["success"]:
            device_ids = result["device_ids"]
            
            # Save to local database
            local_db.save_available_devices(device_ids)
            
            return f"✅ Successfully fetched and stored {len(device_ids)} available device IDs:\n\n" + "\n".join([f"• {device_id}" for device_id in device_ids])
        else:
            return f"❌ Failed to fetch device IDs: {result['message']}\n\n💡 **Workaround:** You can manually add device IDs using the 'Add Device ID' function below."
            
    except Exception as e:
        logger.error(f"Error fetching available devices: {str(e)}")
        return f"❌ Error: {str(e)}\n\n💡 **Workaround:** You can manually add device IDs using the 'Add Device ID' function below."

def add_device_id_manually(device_id):
    """
    Manually add a device ID to the local database
    
    Args:
        device_id (str): The device ID to add
        
    Returns:
        str: Status message about the operation
    """
    try:
        if not device_id or not device_id.strip():
            return "❌ Please enter a valid device ID."
        
        device_id = device_id.strip()
        
        # Check if we're online and validate the device ID
        if api_client.is_online():
            validation_result = validate_device_id(device_id)
            if not validation_result.get("isValid", False):
                return f"❌ Device ID '{device_id}' is not valid according to the API.\n\nResponse: {validation_result.get('responseMessage', 'Unknown error')}"
        
        # Get current available devices
        current_devices = local_db.get_available_devices()
        current_device_ids = [device['device_id'] for device in current_devices]
        
        # Check if device ID already exists
        if device_id in current_device_ids:
            return f"⚠️ Device ID '{device_id}' is already in the database."
        
        # Add the device ID to the list
        new_device_ids = current_device_ids + [device_id]
        
        # Save to local database
        local_db.save_available_devices(new_device_ids)
        
        return f"✅ Successfully added device ID '{device_id}' to the local database.\n\nTotal devices: {len(new_device_ids)}"
        
    except Exception as e:
        logger.error(f"Error adding device ID manually: {str(e)}")
        return f"❌ Error: {str(e)}"

def remove_device_id_manually(device_id):
    """
    Manually remove a device ID from the local database
    
    Args:
        device_id (str): The device ID to remove
        
    Returns:
        str: Status message about the operation
    """
    try:
        if not device_id or not device_id.strip():
            return "❌ Please enter a valid device ID."
        
        device_id = device_id.strip()
        
        # Get current available devices
        current_devices = local_db.get_available_devices()
        current_device_ids = [device['device_id'] for device in current_devices]
        
        # Check if device ID exists
        if device_id not in current_device_ids:
            return f"⚠️ Device ID '{device_id}' is not in the database."
        
        # Remove the device ID from the list
        new_device_ids = [did for did in current_device_ids if did != device_id]
        
        # Save to local database
        local_db.save_available_devices(new_device_ids)
        
        return f"✅ Successfully removed device ID '{device_id}' from the local database.\n\nRemaining devices: {len(new_device_ids)}"
        
    except Exception as e:
        logger.error(f"Error removing device ID manually: {str(e)}")
        return f"❌ Error: {str(e)}"

def clear_all_device_ids():
    """
    Clear all device IDs from the local database
    
    Returns:
        str: Status message about the operation
    """
    try:
        # Clear all device IDs
        local_db.save_available_devices([])
        
        return "✅ Successfully cleared all device IDs from the local database."
        
    except Exception as e:
        logger.error(f"Error clearing device IDs: {str(e)}")
        return f"❌ Error: {str(e)}"

def get_registration_status():
    """
    Get the current device registration status
    
    Returns:
        str: Formatted registration status
    """
    try:
        reg_status = local_db.is_device_registered()
        available_devices = local_db.get_available_devices()
        
        status_text = "📋 **DEVICE REGISTRATION STATUS**\n\n"
        
        # Available devices status
        if reg_status['has_available_devices']:
            status_text += f"✅ **Available Devices:** {reg_status['available_device_count']} devices found\n"
            for device in available_devices[:5]:  # Show first 5 devices
                status_text += f"   • {device['device_id']}\n"
            if len(available_devices) > 5:
                status_text += f"   • ... and {len(available_devices) - 5} more\n"
        else:
            status_text += "❌ **Available Devices:** No devices found - Please fetch device IDs\n"
        
        # Test barcode status
        if reg_status['test_barcode_scanned']:
            status_text += f"✅ **Test Barcode:** Scanned ({reg_status['test_barcode_value']}) at {reg_status['scanned_at']}\n"
        else:
            status_text += "❌ **Test Barcode:** Not scanned - Please scan: 817994ccfe14\n"
        
        # Overall status
        if reg_status['device_ready']:
            status_text += "\n🎉 **DEVICE READY:** Can send messages to IoT Hub"
        else:
            status_text += "\n⚠️ **DEVICE NOT READY:** Complete registration steps above"
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error getting registration status: {str(e)}")
        return f"❌ Error getting registration status: {str(e)}"

def test_registration_api():
    """
    Test the registration barcode API call with proper headers and JSON body
    
    Returns:
        str: Formatted test result
    """
    try:
        # Check if we're online
        if not api_client.is_online():
            return "❌ Device is offline. Cannot test registration API."
        
        # Test the registration barcode API
        result = api_client.test_registration_barcode("817994ccfe14")
        
        status_text = "🧪 **REGISTRATION API TEST**\n\n"
        status_text += f"**Test Barcode:** 817994ccfe14\n"
        status_text += f"**Endpoint:** https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId\n"
        status_text += f"**Headers:** Content-Type: application/json\n"
        status_text += f"**Body:** {{\"scannedBarcode\": \"817994ccfe14\"}}\n\n"
        
        if result["success"]:
            status_text += f"✅ **Status:** Success (HTTP {result['status_code']})\n"
            status_text += f"**Response:** {result['message']}\n"
            if result["response"]:
                status_text += f"**Full Response:** {result['response']}\n"
        else:
            status_text += f"❌ **Status:** Failed\n"
            if result["status_code"]:
                status_text += f"**HTTP Status:** {result['status_code']}\n"
            status_text += f"**Error:** {result['message']}\n"
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error testing registration API: {str(e)}")
        return f"❌ Error testing registration API: {str(e)}"

# --- Registration Step 1: Scan Test Barcode and Hit API Twice ---
def register_device_id(barcode):
    """
    Step 1: Scan test barcode on registered device, hit API twice, send response to frontend
    """
    try:
        # Only allow the test barcode for registration
        if barcode != "817994ccfe14":
            blink_led("red")
            return "❌ Only the test barcode (817994ccfe14) can be used for registration."
        
        is_online = api_client.is_online()
        if not is_online:
            blink_led("red")
            return "❌ Device is offline. Cannot register device."
        
        # First API call - saveDeviceId
        api_url_1 = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload_1 = {"scannedBarcode": barcode}
        
        logger.info(f"Making first API call to {api_url_1}")
        api_result_1 = api_client.send_registration_barcode(api_url_1, payload_1)
        
        if not api_result_1.get("success", False):
            blink_led("red")
            return f"❌ First API call failed: {api_result_1.get('message', 'Unknown error')}"
        
        # Second API call - same endpoint (as requested to hit twice)
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

# --- Registration Step 2: Confirm Registration ---
def confirm_registration(barcode, device_id):
    """
    Step 2: Frontend confirms registration, send confirmation message, save device in DB, send to IoT
    """
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
        
        # Call confirmRegistration API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/confirmRegistration"
        payload = {"deviceId": device_id, "scannedBarcode": test_scan['barcode']}
        
        logger.info(f"Confirming registration with API: {api_url}")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        if not api_result.get("success", False):
            blink_led("red")
            return f"❌ Confirmation failed: {api_result.get('message', 'Unknown error')}"
        
        # Save device ID to database
        local_db.save_device_id(device_id)
        
        # Send message to IoT Hub
        try:
            config = load_config()
            if config:
                # Get connection string
                connection_string = config.get("iot_hub", {}).get("connection_string", None)
                if connection_string:
                    hub_client = HubClient(connection_string)
                    
                    # Create registration message for IoT Hub
                    registration_message = {
                        "scannedBarcode": test_scan['barcode'],
                        "deviceId": device_id,
                        "messageType": "registration_confirmation",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Send to IoT Hub
                    iot_success = hub_client.send_message(registration_message)
                    iot_status = "✅ Sent to IoT Hub" if iot_success else "⚠️ Failed to send to IoT Hub"
                else:
                    iot_status = "⚠️ No IoT Hub connection string configured"
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

def register_device(device_id):
    """
    Register a device with the API and save it to the local database.
    """
    try:
        if not device_id or not device_id.strip():
            return "❌ Please enter a valid device ID."
        device_id = device_id.strip()
        # Call the API to register the device
        api_result = api_client.register_device(device_id)
        if not api_result.get("success", False):
            return f"❌ Device registration failed: {api_result.get('message', 'Unknown error')}"
        # Save the device ID to the local database
        local_db.save_device_id(device_id)
        return f"✅ Device {device_id} registered and saved successfully."
    except Exception as e:
        logger.error(f"Error in register_device: {str(e)}")
        return f"Error: {str(e)}"

# --- LED Blink Helper ---
def blink_led(color):
    """
    Blink the Raspberry Pi LED. Use 'green' for success, 'red' for error.
    This is a placeholder; replace with actual GPIO code if needed.
    """
    try:
        # Example: print to log, replace with GPIO code for real hardware
        logger.info(f"Blinking {color} LED on Raspberry Pi.")
    except Exception as e:
        logger.error(f"LED blink error: {str(e)}")

# --- Normal Operation: Send Barcode to IoT Hub ---
def send_barcode_to_iot_hub(barcode, device_id, quantity=1):
    """
    Send a barcode to the IoT Hub using the registered device ID.
    Only allowed after registration is complete.
    """
    try:
        reg_status = local_db.is_device_registered()
        if not reg_status['device_ready']:
            return "❌ Device not registered. Please complete registration (device ID + test barcode) first."
        # Validate barcode using the EAN validator (except test barcode)
        if barcode != "817994ccfe14":
            try:
                barcode = validate_ean(barcode)
            except BarcodeValidationError as e:
                return f"Error: {str(e)}"
        # Use saved device ID
        device_id = local_db.get_device_id()
        if not device_id:
            return "❌ No device ID found. Please register device ID first."
        # Load configuration
        config = load_config()
        if not config:
            return "Error: Failed to load configuration"
        # Save scan to local database with quantity
        timestamp = local_db.save_scan(device_id, barcode, quantity)
        logger.info(f"Saved scan to local database: {device_id}, {barcode}, quantity: {quantity}, {timestamp}")
        # If we're offline, store the message and return
        is_online = api_client.is_online()
        if not is_online:
            return f"📥 Device appears to be offline. Message saved locally.\n\n**Details:**\n- Device ID: {device_id}\n- Barcode: {barcode}\n- Quantity: {quantity}\n- Timestamp: {timestamp}\n- Status: Will be sent when online"
        # Determine connection string for the device
        devices_config = config.get("iot_hub", {}).get("devices", {})
        if device_id in devices_config:
            connection_string = devices_config[device_id]["connection_string"]
        else:
            connection_string = config.get("iot_hub", {}).get("connection_string", None)
            if not connection_string:
                return f"❌ Error: Device ID '{device_id}' not found in configuration and no default connection string provided."
        # Create IoT Hub client
        hub_client = HubClient(connection_string)
        # Send message (connection is handled internally)
        success = hub_client.send_message(barcode, device_id, quantity)
        if success:
            # Mark as sent in local database
            local_db.mark_sent_to_hub(device_id, barcode, timestamp)
            # Get status and return success message
            status = hub_client.get_status()
            return f"""
            ✅ Message sent successfully!

            **Details:**
            - Device ID: {device_id}
            - Barcode: {barcode}
            - Messages sent: {status['messages_sent']}
            - Last message time: {status['last_message_time']}
            """
        else:
            return "❌ Failed to send message to IoT Hub. Message saved locally and will be sent when connection is restored."
    except Exception as e:
        logger.error(f"Error in send_barcode_to_iot_hub: {str(e)}")
        return f"Error: {str(e)}"
            

# Function to auto-fill device ID from local storage
def get_saved_device_id():
    """Get the saved device ID from local storage"""
    try:
        return local_db.get_device_id() or ""  # Return empty string if no saved ID
    except Exception:
        return ""  # Return empty string on error

# Function to check if a barcode is a valid device ID
def check_barcode_is_device(barcode, device_id_elem):
    """Check if the scanned barcode is a valid device ID"""
    if not barcode:
        return device_id_elem
        
    # Validate the barcode as a device ID
    validation_result = validate_device_id(barcode)
    
    if validation_result.get("isValid", False):
        # If valid, update the device ID field
        return validation_result.get("deviceId", barcode)
    else:
        # If not valid, keep the current device ID
        return device_id_elem

# Create Gradio interface
with gr.Blocks(title="Barcode Scanner") as app:
    gr.Markdown("# Barcode Scanner")
    
    with gr.Row():
        # Left column for barcode scanning
        with gr.Column():
            gr.Markdown("## Scan Barcode")
            
            barcode_input = gr.Textbox(label="Barcode", placeholder="Scan or enter barcode")
            device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID")
            
            with gr.Row():
                send_button = gr.Button("Send Barcode", variant="primary")
                register_device_button = gr.Button("Register Device")
                check_device_button = gr.Button("Check Device ID")
                clear_button = gr.Button("Clear")
                
            with gr.Row():
                auto_fill_button = gr.Button("Auto-fill Barcode from Device ID")
            
            output_text = gr.Markdown("")
            
    
        with gr.Column():
            gr.Markdown("## Device Registration & Status")
            
            gr.Markdown("### Two-Step Registration Process")
            with gr.Row():
                scan_test_barcode_button = gr.Button("1. Scan Test Barcode (817994ccfe14)", variant="primary")
                confirm_registration_button = gr.Button("2. Confirm Registration", variant="primary")
                
            with gr.Row():
                fetch_devices_button = gr.Button("Fetch Available Device IDs", variant="secondary")
                registration_status_button = gr.Button("Check Registration Status")
                
            with gr.Row():
                test_api_button = gr.Button("Test Registration API", variant="secondary")
                check_status_button = gr.Button("Check Online Status")
                
            with gr.Row():
                process_unsent_button = gr.Button("Process Unsent Messages")
                
            status_text = gr.Markdown("")
            
            gr.Markdown("### Manual Device Management")
            with gr.Row():
                device_id_manual_input = gr.Textbox(label="Device ID", placeholder="Enter device ID to add/remove")
                
            with gr.Row():
                add_device_button = gr.Button("Add Device ID", variant="secondary")
                remove_device_button = gr.Button("Remove Device ID")
                clear_devices_button = gr.Button("Clear All Devices", variant="stop")
            
            device_management_text = gr.Markdown("")
            
            with gr.Row():
                gr.Markdown("### Test Offline Mode")
                simulate_offline_button = gr.Button("Simulate Offline Mode")
                simulate_online_button = gr.Button("Restore Online Mode")
            
            offline_status_text = gr.Markdown("Current mode: Online")
            offline_status_text = gr.Markdown("Current mode: Online")
            
    # Add the offline simulation button handlers INSIDE the Blocks context
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

    # Set up event handlers
    send_button.click(
        fn=send_barcode_to_iot_hub,
        inputs=[barcode_input, device_id_input],
        outputs=[output_text]
    )

    register_device_button.click(
        fn=register_device,
        inputs=[device_id_input],
        outputs=[output_text]
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
    
    # Registration handlers
    fetch_devices_button.click(
        fn=fetch_available_devices,
        inputs=[],
        outputs=[status_text]
    )
    
    registration_status_button.click(
        fn=get_registration_status,
        inputs=[],
        outputs=[status_text]
    )
    
    test_api_button.click(
        fn=test_registration_api,
        inputs=[],
        outputs=[status_text]
    )
    
    process_unsent_button.click(
        fn=lambda: process_unsent_messages(auto_retry=False),
        inputs=[],
        outputs=[status_text]
    )
    
    # Manual device management handlers
    add_device_button.click(
        fn=add_device_id_manually,
        inputs=[device_id_manual_input],
        outputs=[device_management_text]
    )
    
    remove_device_button.click(
        fn=remove_device_id_manually,
        inputs=[device_id_manual_input],
        outputs=[device_management_text]
    )
    
    clear_devices_button.click(
        fn=clear_all_device_ids,
        inputs=[],
        outputs=[device_management_text]
    )
    
    # Check if barcode is a device ID
    check_device_button.click(
        fn=check_barcode_is_device,
        inputs=[barcode_input, device_id_input],
        outputs=[device_id_input]
    )
    
    # Auto-check if barcode might be a device ID when barcode changes
    barcode_input.change(
        fn=check_barcode_is_device,
        inputs=[barcode_input, device_id_input],
        outputs=[device_id_input]
    )

# Add functions for automatic background retry

def retry_worker():
    """
    Background worker that continuously checks for and processes unsent messages
    """
    global retry_running, last_queue_check, retry_enabled
    
    logger.info("Starting message retry worker thread")
    
    while retry_running:
        try:
            # Check if retry is enabled
            if not retry_enabled:
                logger.debug("Auto-retry: Retry worker disabled, skipping")
                time.sleep(60)  # Sleep longer when disabled
                continue
                
            # Check if we need to process the queue (according to retry interval)
            current_time = datetime.now()
            time_since_last = (current_time - last_queue_check).total_seconds()
            
            if time_since_last >= retry_interval:
                last_queue_check = current_time
                
                # Check if we're online before attempting to retry
                if api_client.is_online():
                    # Only process unsent messages if there are any
                    unsent_messages = local_db.get_unsent_scans()
                    if unsent_messages:
                        logger.info(f"Auto-retry: Processing {len(unsent_messages)} unsent messages")
                        process_unsent_messages(auto_retry=True)
                    else:
                        logger.debug("Auto-retry: No unsent messages to process")
                else:
                    logger.debug("Auto-retry: Device is offline, skipping retry")
                    
        except Exception as e:
            logger.error(f"Error in retry worker: {str(e)}")
            
        # Sleep for a bit to avoid consuming too much CPU
        time.sleep(30)  # Increased sleep time to reduce frequency
    
    logger.info("Retry worker thread stopped")

def start_retry_thread():
    """
    Start the background retry thread if it's not already running
    """
    global retry_thread, retry_running
    
    with retry_lock:
        if retry_thread is None or not retry_thread.is_alive():
            retry_running = True
            retry_thread = threading.Thread(target=retry_worker, daemon=True)
            retry_thread.start()
            logger.info("Started retry background thread")

def stop_retry_thread():
    """
    Signal the retry thread to stop
    """
    global retry_running
    
    with retry_lock:
        retry_running = False
        logger.info("Signaled retry thread to stop")

def schedule_retry():
    """
    Ensure the retry thread is running
    """
    start_retry_thread()

# Start the background retry thread when the app starts

if __name__ == "__main__":
    # Start the automatic retry thread
    start_retry_thread()
    
    # Launch the Gradio app
    app.launch(server_name="0.0.0.0", server_port=7862)
    
    # Stop the retry thread when the app is shutting down
    stop_retry_thread()