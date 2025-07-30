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
import time
logger = logging.getLogger(__name__)

current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config
from iot.hub_client import HubClient
from database.local_storage import LocalStorage
from api.api_client import ApiClient
from inventory_manager import InventoryManager
from enhanced_device_registration_backup import EnhancedDeviceRegistration

# Initialize database and API client
local_db = LocalStorage()
api_client = ApiClient()
inventory_manager = InventoryManager()
device_registration = EnhancedDeviceRegistration()

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
retry_interval = 60  # seconds
retry_running = False
retry_lock = threading.Lock()
last_queue_check = datetime.now()

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

def send_barcode_to_iot_hub(barcode, device_id, quantity=1):
    """
    Enhanced barcode processing with inventory management and device registration
    """
    try:
        # Validate barcode using the EAN validator
        try:
            barcode = validate_ean(barcode)
        except BarcodeValidationError as e:
            return f"❌ Error: {str(e)}"
            
        # Check if we're online
        is_online = api_client.is_online()
        
        # If no device ID provided and we're online, check if barcode is a device ID
        if is_online and not device_id:
            device_validation = device_registration.validate_and_register_device(barcode)
            
            if device_validation['success']:
                if device_validation['type'] == 'test_barcode':
                    return f"✅ TEST BARCODE DETECTED\n\nConfirmation: OK\n\nThe barcode {barcode} has been identified as a test barcode."
                
                elif device_validation['type'] == 'new_device':
                    return f"""✅ NEW DEVICE REGISTERED SUCCESSFULLY!
                    
**Device ID:** {device_validation['device_id']}
**Test Barcode:** {device_validation['test_barcode']}
**Status:** Device registered and ready for use
**API Notification:** {device_validation['registration_result']['api_result']['message']}

The device has been registered across all systems and a test barcode has been generated."""

                elif device_validation['type'] == 'existing_device':
                    device_id = device_validation['device_id']
                    local_db.save_device_id(device_id)
                    return f"✅ Device ID validated and saved: {device_id}"
            else:
                # Not a device ID, continue with normal barcode processing
                pass
        
        # If no device ID provided, try to get from local storage
        if not device_id:
            device_id = local_db.get_device_id()
            if not device_id:
                return "❌ Error: No device ID provided. Please scan a valid device ID first."
            logger.info(f"Using saved device ID: {device_id}")
        
        # Process the barcode scan with enhanced inventory management
        scan_result = inventory_manager.process_barcode_scan(barcode, device_id, quantity)
        
        if scan_result['type'] == 'test_barcode':
            return f"✅ TEST BARCODE PROCESSED\n\n{scan_result['message']}"
        
        elif scan_result['type'] == 'inventory_update':
            inventory_result = scan_result['inventory_result']
            status = scan_result['status']
            
            # Check for inventory alerts
            if status['alert_level'] == 'CRITICAL':
                alert_msg = f"🚨 CRITICAL ALERT: {status['message']}"
            elif status['alert_level'] == 'HIGH':
                alert_msg = f"⚠️ HIGH ALERT: {status['message']}"
            elif status['alert_level'] == 'MEDIUM':
                alert_msg = f"⚠️ LOW STOCK: {status['message']}"
            else:
                alert_msg = f"✅ {status['message']}"
            
            # Continue with IoT Hub processing if online
            if is_online:
                # Load configuration
                config = load_config()
                if not config:
                    return f"{alert_msg}\n\n❌ Error: Failed to load configuration"

                # Save scan to local database (already done in inventory_manager)
                timestamp = local_db.save_scan(device_id, barcode, quantity)
                
                # Determine connection string for the device
                devices_config = config.get("iot_hub", {}).get("devices", {})
                if device_id in devices_config:
                    connection_string = devices_config[device_id]["connection_string"]
                else:
                    connection_string = config.get("iot_hub", {}).get("connection_string", None)
                    if not connection_string:
                        return f"{alert_msg}\n\n❌ Error: Device ID '{device_id}' not found in configuration."

                # Create IoT Hub client and send message
                hub_client = HubClient(connection_string)
                success = hub_client.send_message(barcode, device_id, quantity)

                if success:
                    local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                    status_info = hub_client.get_status()
                    
                    return f"""{alert_msg}

✅ Message sent to IoT Hub successfully!

**Inventory Details:**
- EAN: {barcode}
- Previous Quantity: {inventory_result['previous_quantity']}
- Change: {inventory_result['quantity_change']:+d}
- New Quantity: {inventory_result['new_quantity']}

**IoT Hub Details:**
- Device ID: {device_id}
- Messages sent: {status_info['messages_sent']}
- Last message time: {status_info['last_message_time']}"""
                else:
                    return f"""{alert_msg}

❌ Failed to send to IoT Hub (saved locally for retry)

**Inventory Updated:**
- EAN: {barcode}
- Previous Quantity: {inventory_result['previous_quantity']}
- Change: {inventory_result['quantity_change']:+d}
- New Quantity: {inventory_result['new_quantity']}"""
            else:
                return f"""{alert_msg}

📥 Device offline - inventory updated locally

**Inventory Details:**
- EAN: {barcode}
- Previous Quantity: {inventory_result['previous_quantity']}
- Change: {inventory_result['quantity_change']:+d}
- New Quantity: {inventory_result['new_quantity']}
- Status: Will sync when online"""
        
        else:
            return f"❌ Error: {scan_result.get('message', 'Unknown error occurred')}"

    except Exception as e:
        logger.error(f"Error in send_barcode_to_iot_hub: {str(e)}")
        return f"❌ Error: {str(e)}"

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

def check_inventory_status(ean):
    """Check inventory status for a specific EAN"""
    try:
        status = inventory_manager.check_inventory_status(ean)
        if status['exists']:
            return f"""**Inventory Status for EAN: {ean}**

Product: {status.get('product_name', 'Unknown')}
Current Quantity: {status['current_quantity']}
Alert Level: {status['alert_level']}
Status: {status['message']}"""
        else:
            return f"❌ Product with EAN {ean} not found in inventory"
    except Exception as e:
        return f"❌ Error checking inventory: {str(e)}"

def get_inventory_alerts():
    """Get all active inventory alerts"""
    try:
        alerts = inventory_manager.get_active_alerts()
        if not alerts:
            return "✅ No active inventory alerts"
        
        alert_text = "**Active Inventory Alerts:**\n\n"
        for alert in alerts:
            severity_icon = "🚨" if alert['severity'] == 'CRITICAL' else "⚠️"
            alert_text += f"{severity_icon} **{alert['severity']}**: {alert['message']}\n"
            alert_text += f"   EAN: {alert['ean']} | Type: {alert['alert_type']}\n\n"
        
        return alert_text
    except Exception as e:
        return f"❌ Error getting alerts: {str(e)}"

def get_inventory_report():
    """Generate inventory report"""
    try:
        items = inventory_manager.get_inventory_report()
        if not items:
            return "No inventory items found"
        
        report = "**Inventory Report:**\n\n"
        
        # Group by status
        critical = [item for item in items if item['status'] == 'CRITICAL']
        out_of_stock = [item for item in items if item['status'] == 'OUT_OF_STOCK']
        low_stock = [item for item in items if item['status'] == 'LOW_STOCK']
        normal = [item for item in items if item['status'] == 'NORMAL']
        
        if critical:
            report += "🚨 **CRITICAL (Negative Stock):**\n"
            for item in critical:
                report += f"- {item['ean']}: {item['current_quantity']}\n"
            report += "\n"
        
        if out_of_stock:
            report += "❌ **OUT OF STOCK:**\n"
            for item in out_of_stock:
                report += f"- {item['ean']}: {item['current_quantity']}\n"
            report += "\n"
        
        if low_stock:
            report += "⚠️ **LOW STOCK:**\n"
            for item in low_stock:
                report += f"- {item['ean']}: {item['current_quantity']} (threshold: {item['min_threshold']})\n"
            report += "\n"
        
        report += f"✅ **NORMAL STOCK:** {len(normal)} items\n"
        
        return report
    except Exception as e:
        return f"❌ Error generating report: {str(e)}"

def register_new_device_manual(device_id, device_name):
    """Manually register a new device"""
    try:
        if not device_id:
            return "❌ Please provide a device ID"
        
        result = device_registration.register_device_complete(device_id, device_name)
        
        if result['success']:
            return f"""✅ Device registered successfully!

**Device ID:** {result['device_id']}
**Test Barcode:** {result['test_barcode']}
**Azure IoT:** {result['azure_result']['message']}
**API Notification:** {result['api_result']['message']}

The device is now ready for use."""
        else:
            return f"❌ Registration failed: {result['message']}"
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Enhanced Barcode Scanner & Inventory Management") as app:
    gr.Markdown("# Enhanced Barcode Scanner & Inventory Management")
    
    with gr.Tabs():
        # Main scanning tab
        with gr.TabItem("Barcode Scanner"):
            with gr.Row():
                # Left column for barcode scanning
                with gr.Column():
                    gr.Markdown("## Scan Barcode")
                    
                    barcode_input = gr.Textbox(label="Barcode", placeholder="Scan or enter barcode")
                    device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID")
                    
                    with gr.Row():
                        send_button = gr.Button("Send Barcode", variant="primary")
                        check_device_button = gr.Button("Check Device ID")
                        clear_button = gr.Button("Clear")
                        
                    with gr.Row():
                        auto_fill_button = gr.Button("Auto-fill Barcode from Device ID")
                    
                    output_text = gr.Markdown("")
                    
            
                with gr.Column():
                    gr.Markdown("## Status & Configuration")
                    
                    with gr.Row():
                        check_status_button = gr.Button("Check Online Status")
                        process_unsent_button = gr.Button("Process Unsent Messages")
                        
                    status_text = gr.Markdown("")
                    
                    with gr.Row():
                        gr.Markdown("### Test Offline Mode")
                        simulate_offline_button = gr.Button("Simulate Offline Mode")
                        simulate_online_button = gr.Button("Restore Online Mode")
                    
                    offline_status_text = gr.Markdown("Current mode: Online")
        
        # Inventory Management tab
        with gr.TabItem("Inventory Management"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## Inventory Status")
                    
                    ean_input = gr.Textbox(label="EAN Code", placeholder="Enter EAN to check status")
                    check_inventory_button = gr.Button("Check Inventory Status")
                    inventory_status_output = gr.Markdown("")
                    
                    gr.Markdown("## Inventory Alerts")
                    get_alerts_button = gr.Button("Get Active Alerts")
                    alerts_output = gr.Markdown("")
                
                with gr.Column():
                    gr.Markdown("## Inventory Report")
                    generate_report_button = gr.Button("Generate Inventory Report")
                    report_output = gr.Markdown("")
        
        # Device Registration tab
        with gr.TabItem("Device Registration"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("## Manual Device Registration")
                    
                    new_device_id_input = gr.Textbox(label="Device ID", placeholder="Enter new device ID")
                    new_device_name_input = gr.Textbox(label="Device Name (Optional)", placeholder="Enter device name")
                    register_device_button = gr.Button("Register Device", variant="primary")
                    registration_output = gr.Markdown("")
                
                with gr.Column():
                    gr.Markdown("## Device Information")
                    gr.Markdown("""
                    **Device Registration Process:**
                    1. Validates device ID with API
                    2. Registers with Azure IoT Hub
                    3. Generates test barcode
                    4. Sends notification to client API
                    5. Updates local configuration
                    
                    **Test Barcode Format:** TEST_{device_id}_{date}
                    """)
            
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

    # Set initial values for connection status and unsent count
    # Note: We'll use the refresh buttons to update these values instead of auto-updating on load

    # Set up event handlers
    send_button.click(
        fn=lambda barcode, device_id: send_barcode_to_iot_hub(barcode, device_id, quantity=1),
        inputs=[barcode_input, device_id_input],
        outputs=[output_text]
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
    
    # Inventory Management event handlers
    check_inventory_button.click(
        fn=check_inventory_status,
        inputs=[ean_input],
        outputs=[inventory_status_output]
    )
    
    get_alerts_button.click(
        fn=get_inventory_alerts,
        inputs=[],
        outputs=[alerts_output]
    )
    
    generate_report_button.click(
        fn=get_inventory_report,
        inputs=[],
        outputs=[report_output]
    )
    
    # Device Registration event handlers
    register_device_button.click(
        fn=register_new_device_manual,
        inputs=[new_device_id_input, new_device_name_input],
        outputs=[registration_output]
    )

# Add functions for automatic background retry



def retry_worker():
    """
    Background worker that continuously checks for and processes unsent messages
    """
    global retry_running, last_queue_check
    
    logger.info("Starting message retry worker thread")
    
    while retry_running:
        try:
            # Check if we need to process the queue (according to retry interval)
            current_time = datetime.now()
            time_since_last = (current_time - last_queue_check).total_seconds()
            
            if time_since_last >= retry_interval:
                last_queue_check = current_time
                
                # Check if we're online before attempting to retry
                if api_client.is_online():
                    logger.info("Auto-retry: Processing unsent messages")
                    process_unsent_messages(auto_retry=True)
                else:
                    logger.info("Auto-retry: Device is offline, skipping retry")
                    
        except Exception as e:
            logger.error(f"Error in retry worker: {str(e)}")
            
        # Sleep for a bit to avoid consuming too much CPU
        time.sleep(5)
    
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
    app.launch(server_name="0.0.0.0", server_port=7860)
    
    # Stop the retry thread when the app is shutting down
    stop_retry_thread()
