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

# Override the is_online method for testing
orig_is_online = api_client.is_online

def patched_is_online():
    """Patched version of is_online that respects simulated_offline_mode"""
    if simulated_offline_mode:
        return False
    return orig_is_online()
    
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

def process_barcode_scan(barcode, device_id):
    """Unified function to handle barcode scanning - either for registration or normal operation"""
    try:
        # Check if this is the test barcode for registration
        if barcode == "817994ccfe14":
            # This is a test barcode - handle registration
            return register_device_id(barcode)
        
        # This is a normal barcode - check if device is registered
        saved_device_id = local_db.get_device_id()
        if not saved_device_id:
            return "❌ Device not registered. Please complete the two-step registration process first:\n1. Click 'Scan Test Barcode'\n2. Click 'Confirm Registration'"
        
        # Use saved device ID if none provided
        if not device_id or not device_id.strip():
            device_id = saved_device_id
        
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
            # Get status and return success message
            status = hub_client.get_status()
            return f"""✅ Message sent successfully!

**Details:**
- Device ID: {device_id}
- Barcode: {validated_barcode}
- Messages sent: {status['messages_sent']}
- Last message time: {status['last_message_time']}"""
        else:
            return "❌ Failed to send message to IoT Hub. Message saved locally and will be sent when connection is restored."
            
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {str(e)}")
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
            success = message_client.send_message(message_payload)
            
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
    # Launch the Gradio app
    app.launch(server_name="0.0.0.0", server_port=7862)