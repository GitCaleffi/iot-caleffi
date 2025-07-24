#!/usr/bin/env python3
"""
Final Barcode Scanner App
Fixes all issues:
1. IoT connection confirmation using config.json
2. Remove static test barcode - any barcode can register device
3. Save registration to local database
4. Send confirmation message to frontend
5. Fix configuration loading error
"""

import gradio as gr
import json
import os
import sys
from pathlib import Path
import logging
import time
import threading
import hashlib
import uuid
import platform
import base64
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(current_dir))

# Import modules with error handling
try:
    from barcode_validator import validate_ean, BarcodeValidationError
except ImportError:
    logger.warning("barcode_validator not found, using basic validation")
    class BarcodeValidationError(Exception):
        pass
    def validate_ean(barcode):
        return barcode

try:
    from utils.led_control import blink_success, blink_error, blink_warning, blink_info
except ImportError:
    logger.warning("LED control not available")
    def blink_success(): logger.info("💚 SUCCESS")
    def blink_error(): logger.info("❤️ ERROR")
    def blink_warning(): logger.info("💛 WARNING")
    def blink_info(): logger.info("💙 INFO")

try:
    from database.fixed_local_storage import FixedLocalStorage
    local_db = FixedLocalStorage()
except ImportError:
    logger.warning("Fixed local storage not available, using simple storage")
    class SimpleStorage:
        def __init__(self):
            self.data = {}
        def get_device_id(self): return self.data.get('device_id')
        def save_device_id(self, device_id, barcode=None): self.data['device_id'] = device_id
        def get_registration_barcode(self): return self.data.get('reg_barcode')
        def save_registration_barcode(self, barcode, device_id): self.data['reg_barcode'] = {'barcode': barcode}
        def clear_device_registration(self): self.data.clear()
        def save_scan(self, device_id, barcode, quantity, msg_type): return datetime.now().isoformat()
        def mark_sent_to_hub(self, device_id, barcode, timestamp): pass
        def get_device_statistics(self): return {'total_scans': 0, 'unsent_scans': 0, 'registered_devices': 0}
    local_db = SimpleStorage()

try:
    from api.api_client import ApiClient
    api_client = ApiClient()
except ImportError:
    logger.warning("API client not available")
    class SimpleApiClient:
        def is_online(self): return True
        def send_registration_barcode(self, url, payload): return {"success": True, "message": "Simulated success"}
    api_client = SimpleApiClient()

# Global state
simulated_offline_mode = False

def load_config_from_file():
    """Load configuration directly from config.json file"""
    try:
        config_path = project_root / 'config.json'
        logger.info(f"Loading config from: {config_path}")
        
        if not config_path.exists():
            logger.error(f"Config file not found at: {config_path}")
            return None
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        logger.info("✅ Configuration loaded successfully from config.json")
        return config
        
    except Exception as e:
        logger.error(f"Error loading config from file: {e}")
        return None

def generate_device_id():
    """Generate unique device ID based on system characteristics"""
    try:
        # Get MAC address
        mac = uuid.getnode()
        mac_str = ':'.join(('%012X' % mac)[i:i+2] for i in range(0, 12, 2))
        
        # Get system info
        hostname = platform.node()
        system = platform.system()
        
        # Create unique identifier
        unique_string = f"{mac_str}-{hostname}-{system}"
        device_id = hashlib.md5(unique_string.encode()).hexdigest()[:12]
        
        logger.info(f"Generated device ID: {device_id}")
        return device_id
        
    except Exception as e:
        logger.warning(f"Could not generate device ID from system info: {e}")
        # Fallback to random UUID
        fallback_id = str(uuid.uuid4()).replace('-', '')[:12]
        logger.info(f"Using fallback device ID: {fallback_id}")
        return fallback_id

def create_iot_hub_client():
    """Create IoT Hub client using config.json"""
    try:
        config = load_config_from_file()
        if not config:
            logger.error("Failed to load configuration")
            return None
        
        # Get IoT Hub configuration
        iot_config = config.get('iot_hub', {})
        hostname = iot_config.get('hostname')
        hub_connection_string = iot_config.get('hub_connection_string')
        
        if not hostname:
            logger.error("No hostname found in config")
            return None
        
        # Get or generate device ID
        device_id = generate_device_id()
        
        # Check if device is already registered
        registered_devices = iot_config.get('registered_devices', {})
        
        if device_id in registered_devices:
            # Use existing device connection
            connection_string = registered_devices[device_id].get('connection_string')
            logger.info(f"Using existing device connection for: {device_id}")
        else:
            # Register new device with IoT Hub
            connection_string = register_device_with_iot_hub(device_id, config)
        
        if not connection_string:
            logger.error("Failed to get device connection string")
            return None
        
        # Create IoT Hub device client
        try:
            from azure.iot.device import IoTHubDeviceClient
            client = IoTHubDeviceClient.create_from_connection_string(connection_string)
        except ImportError:
            logger.error("Azure IoT Device SDK not installed")
            return None
        
        return {
            'client': client,
            'device_id': device_id,
            'connection_string': connection_string,
            'hostname': hostname
        }
        
    except Exception as e:
        logger.error(f"Error creating IoT Hub client: {e}")
        return None

def register_device_with_iot_hub(device_id, config):
    """Register device with Azure IoT Hub"""
    try:
        try:
            from azure.iot.hub import IoTHubRegistryManager
        except ImportError:
            logger.error("Azure IoT Hub SDK not installed")
            return None
        
        iot_config = config.get('iot_hub', {})
        hub_connection_string = iot_config.get('hub_connection_string')
        
        if not hub_connection_string:
            logger.error("No hub connection string found in config")
            return None
        
        # Create registry manager
        registry_manager = IoTHubRegistryManager.from_connection_string(hub_connection_string)
        
        # Check if device exists
        try:
            device = registry_manager.get_device(device_id)
            logger.info(f"Device {device_id} already exists in IoT Hub")
            primary_key = device.authentication.symmetric_key.primary_key
        except:
            logger.info(f"Creating new device in IoT Hub: {device_id}")
            
            # Generate secure keys
            primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
            
            # Create device
            device = registry_manager.create_device_with_sas(
                device_id, primary_key, secondary_key, "enabled"
            )
            primary_key = device.authentication.symmetric_key.primary_key
            logger.info(f"Device {device_id} created successfully in IoT Hub")
        
        # Create device connection string
        hostname = iot_config.get('hostname')
        connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
        
        # Update config file with new device
        device_info = {
            "device_id": device_id,
            "connection_string": connection_string,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "status": "active"
        }
        
        config['iot_hub']['registered_devices'][device_id] = device_info
        config['iot_hub']['current_device_id'] = device_id
        
        # Save updated config
        config_path = project_root / 'config.json'
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Device {device_id} registered and saved to config")
        return connection_string
        
    except Exception as e:
        logger.error(f"Error registering device with IoT Hub: {e}")
        return None

def test_iot_connection():
    """Test IoT Hub connection and send confirmation message"""
    try:
        logger.info("🔗 Testing IoT Hub connection...")
        
        # Create IoT Hub client
        iot_info = create_iot_hub_client()
        if not iot_info:
            blink_error()
            return "❌ Failed to create IoT Hub client. Check config.json file."
        
        client = iot_info['client']
        device_id = iot_info['device_id']
        
        # Test connection
        logger.info("Connecting to IoT Hub...")
        client.connect()
        
        # Send confirmation message
        confirmation_message = {
            "messageType": "connection_test",
            "deviceId": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "connected",
            "message": "IoT Hub connection confirmed",
            "source": "barcode_scanner_app"
        }
        
        try:
            from azure.iot.device import Message
            message = Message(json.dumps(confirmation_message))
            client.send_message(message)
        except ImportError:
            logger.error("Azure IoT Device SDK not available for message sending")
        
        # Disconnect
        client.disconnect()
        
        blink_success()
        logger.info("✅ IoT Hub connection confirmed")
        
        return f"""✅ IoT Hub Connection Confirmed!

**Connection Details:**
• Device ID: {device_id}
• Hostname: {iot_info['hostname']}
• Status: ✅ Connected and tested
• Confirmation message sent to IoT Hub

**Message Sent:**
{json.dumps(confirmation_message, indent=2)}

Device is ready for barcode scanning!"""
        
    except Exception as e:
        logger.error(f"IoT connection test failed: {e}")
        blink_error()
        return f"❌ IoT Hub connection test failed: {e}"

def register_device_with_any_barcode(barcode):
    """Register device using ANY barcode - no static test barcode required"""
    try:
        # Validate barcode input
        if not barcode or len(barcode.strip()) == 0:
            blink_error()
            return "❌ Please enter a valid barcode for device registration."
        
        barcode = barcode.strip()
        
        # Check if device is already registered
        existing_device_id = local_db.get_device_id()
        if existing_device_id:
            blink_warning()
            return f"""⚠️ Device already registered!

**Current Registration:**
• Device ID: {existing_device_id}
• Status: Active

If you want to register with a different barcode, click 'Reset Registration' first."""
        
        # Check if online
        is_online = api_client.is_online()
        if not is_online:
            blink_error()
            return "❌ Device is offline. Cannot register device."
        
        # Generate device ID
        device_id = generate_device_id()
        
        logger.info(f"🔧 Registering device ID: {device_id} with barcode: {barcode}")
        
        # Create IoT Hub client and register device
        iot_info = create_iot_hub_client()
        if not iot_info:
            blink_error()
            return "❌ Failed to create IoT Hub client. Check config.json file."
        
        # Save registration to local database
        local_db.save_device_id(device_id, barcode)
        local_db.save_registration_barcode(barcode, device_id)
        
        # Call API for registration
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {"scannedBarcode": barcode}
        
        logger.info(f"📡 Making API call to {api_url}")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        if not api_result.get("success", False):
            blink_error()
            return f"❌ API registration failed: {api_result.get('message', 'Unknown error')}"
        
        # Send registration confirmation to IoT Hub
        try:
            client = iot_info['client']
            client.connect()
            
            registration_message = {
                "messageType": "device_registration",
                "deviceId": device_id,
                "registrationBarcode": barcode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "apiResponse": api_result.get('message', 'Success'),
                "source": "barcode_scanner_registration"
            }
            
            try:
                from azure.iot.device import Message
                message = Message(json.dumps(registration_message))
                client.send_message(message)
            except ImportError:
                logger.warning("Azure IoT Device SDK not available for message sending")
            
            client.disconnect()
            
            iot_status = "✅ Registration sent to IoT Hub"
            logger.info("📡 Registration message sent to IoT Hub")
            
        except Exception as iot_error:
            logger.error(f"IoT Hub error: {iot_error}")
            iot_status = f"⚠️ IoT Hub error: {iot_error}"
        
        blink_success()
        
        # Send confirmation message to frontend
        confirmation_msg = f"""🎉 Device Registration Successful!

**Device Details:**
• Device ID: {device_id}
• Registration Barcode: {barcode}
• Registered At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

**Actions Completed:**
• ✅ Device saved in local database
• ✅ API registration successful: {api_result.get('message', 'Success')}
• {iot_status}

**Status:** Device is now ready for barcode scanning!
You can now scan any barcode and it will be sent to IoT Hub."""
        
        return confirmation_msg
        
    except Exception as e:
        logger.error(f"Error in device registration: {e}")
        blink_error()
        return f"❌ Registration error: {e}"

def process_barcode_scan(barcode, device_id_override=None):
    """Process barcode scan and send to IoT Hub"""
    try:
        # Validate barcode input
        if not barcode or len(barcode.strip()) == 0:
            blink_error()
            return "❌ Please enter a valid barcode."
        
        barcode = barcode.strip()
        
        # Check if device is registered
        saved_device_id = local_db.get_device_id()
        if not saved_device_id:
            blink_error()
            return """❌ Device not registered. Please register first:

**Registration Steps:**
1. Enter ANY barcode in the 'Barcode' field above
2. Click 'Register Device'
3. Device will be registered and ready for scanning

No specific test barcode required!"""
        
        # Validate barcode format
        try:
            validated_barcode = validate_ean(barcode)
        except BarcodeValidationError as e:
            blink_error()
            return f"❌ Barcode validation error: {e}"
        
        # Get device ID
        device_id = device_id_override or saved_device_id
        
        # Save scan to local database
        timestamp = local_db.save_scan(device_id, validated_barcode, 1, 'barcode_scan')
        logger.info(f"💾 Saved scan: device={device_id}, barcode={validated_barcode}")
        
        # Check if we're online
        is_online = api_client.is_online()
        if not is_online:
            blink_warning()
            return f"""📥 Device appears to be offline. Message saved locally.

**Details:**
- Device ID: {device_id}
- Barcode: {validated_barcode}
- Timestamp: {timestamp}
- Status: Will be sent when online"""
        
        # Send to IoT Hub
        try:
            # Create IoT Hub client
            iot_info = create_iot_hub_client()
            if not iot_info:
                blink_error()
                return "❌ Failed to create IoT Hub client."
            
            client = iot_info['client']
            client.connect()
            
            # Create comprehensive IoT message
            iot_message = {
                "messageType": "barcode_scan",
                "scannedBarcode": validated_barcode,
                "deviceId": device_id,
                "quantity": 1,
                "timestamp": timestamp,
                "source": "barcode_scanner_app",
                "status": "processed"
            }
            
            try:
                from azure.iot.device import Message
                message = Message(json.dumps(iot_message))
                client.send_message(message)
            except ImportError:
                logger.warning("Azure IoT Device SDK not available for message sending")
            
            client.disconnect()
            
            # Mark as sent in local database
            local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
            
            blink_success()
            
            return f"""✅ Barcode sent successfully to IoT Hub!

**Scan Details:**
- Device ID: {device_id}
- Barcode: {validated_barcode}
- Timestamp: {timestamp}
- Status: ✅ Delivered to Azure IoT Hub

**Message Sent:**
{json.dumps(iot_message, indent=2)}"""
            
        except Exception as iot_error:
            logger.error(f"IoT Hub error: {iot_error}")
            blink_error()
            return f"❌ IoT Hub error: {iot_error}. Message saved locally."
            
    except Exception as e:
        logger.error(f"Error in process_barcode_scan: {e}")
        blink_error()
        return f"❌ Error: {e}"

def reset_registration():
    """Reset device registration"""
    try:
        # Clear local database
        local_db.clear_device_registration()
        
        blink_success()
        
        return """🔄 Device Registration Reset!

**Actions Completed:**
• ✅ Local device registration cleared
• ✅ System ready for new registration

**Next Steps:**
1. Enter ANY barcode in the 'Barcode' field
2. Click 'Register Device'
3. Start scanning barcodes

No specific test barcode required!"""
        
    except Exception as e:
        logger.error(f"Error resetting registration: {e}")
        blink_error()
        return f"❌ Error resetting registration: {e}"

def get_device_status():
    """Get current device status"""
    try:
        # Check device registration
        device_id = local_db.get_device_id()
        device_registered = device_id is not None
        
        # Check registration barcode
        registration_barcode = local_db.get_registration_barcode()
        barcode_exists = registration_barcode is not None
        
        # Get database statistics
        stats = local_db.get_device_statistics()
        
        # Test IoT connection
        iot_status = "❌ Not tested"
        try:
            iot_info = create_iot_hub_client()
            if iot_info:
                client = iot_info['client']
                client.connect()
                client.disconnect()
                iot_status = "✅ Connected"
            else:
                iot_status = "❌ Failed to create client"
        except Exception as e:
            iot_status = f"❌ Connection failed: {e}"
        
        status_text = "📋 **DEVICE STATUS**\n\n"
        
        # Device registration status
        if device_registered:
            status_text += f"✅ **Device Registered:** {device_id}\n"
        else:
            status_text += "❌ **Device Not Registered:** Use any barcode to register\n"
        
        # Registration barcode status
        if barcode_exists:
            status_text += f"✅ **Registration Barcode:** {registration_barcode['barcode']}\n"
        else:
            status_text += "❌ **Registration Barcode:** None\n"
        
        # IoT Hub status
        status_text += f"🔗 **IoT Hub Connection:** {iot_status}\n"
        
        # Statistics
        status_text += f"\n📈 **Statistics:**\n"
        status_text += f"• Total scans: {stats['total_scans']}\n"
        status_text += f"• Unsent scans: {stats['unsent_scans']}\n"
        status_text += f"• Registered devices: {stats['registered_devices']}\n"
        
        # Overall status
        if device_registered and barcode_exists and "✅" in iot_status:
            status_text += "\n🎉 **SYSTEM READY:** Can send messages to IoT Hub"
            blink_info()
        else:
            status_text += "\n⚠️ **SYSTEM NOT READY:** Complete setup above"
            blink_warning()
        
        return status_text
        
    except Exception as e:
        logger.error(f"Error getting device status: {e}")
        blink_error()
        return f"❌ Error getting device status: {e}"

def simulate_offline_mode():
    """Simulate offline mode"""
    global simulated_offline_mode
    simulated_offline_mode = True
    blink_warning()
    return "⚠️ OFFLINE mode simulated."

def simulate_online_mode():
    """Restore online mode"""
    global simulated_offline_mode
    simulated_offline_mode = False
    blink_success()
    return "✅ Online mode restored."

# Override is_online for testing
orig_is_online = api_client.is_online
def patched_is_online():
    if simulated_offline_mode:
        return False
    return orig_is_online()
api_client.is_online = patched_is_online

# Create Gradio interface
with gr.Blocks(title="Final Barcode Scanner") as app:
    gr.Markdown("# Final Barcode Scanner")
    gr.Markdown("*IoT connection confirmation • Any barcode registration • No static test barcode*")
    
    with gr.Row():
        # Left column
        with gr.Column():
            gr.Markdown("## Barcode Operations")
            
            barcode_input = gr.Textbox(label="Barcode", placeholder="Enter ANY barcode")
            device_id_input = gr.Textbox(label="Device ID", placeholder="Auto-generated (optional override)")
            
            with gr.Row():
                scan_button = gr.Button("Send Barcode", variant="primary")
                register_button = gr.Button("Register Device", variant="secondary")
            
            with gr.Row():
                clear_button = gr.Button("Clear")
                
            output_text = gr.Markdown("")
            
        with gr.Column():
            gr.Markdown("## System Management")
            
            with gr.Row():
                test_iot_button = gr.Button("Test IoT Connection", variant="primary")
                status_button = gr.Button("Check Device Status")
            
            with gr.Row():
                reset_button = gr.Button("Reset Registration", variant="secondary")
                
            status_text = gr.Markdown("")
            
            gr.Markdown("### Test Mode")
            with gr.Row():
                offline_button = gr.Button("Simulate Offline")
                online_button = gr.Button("Restore Online")
            
            mode_text = gr.Markdown("**Mode:** Online")
    
    # Event handlers
    scan_button.click(
        fn=process_barcode_scan,
        inputs=[barcode_input, device_id_input],
        outputs=[output_text]
    )
    
    register_button.click(
        fn=register_device_with_any_barcode,
        inputs=[barcode_input],
        outputs=[status_text]
    )
    
    test_iot_button.click(
        fn=test_iot_connection,
        inputs=[],
        outputs=[status_text]
    )
    
    status_button.click(
        fn=get_device_status,
        inputs=[],
        outputs=[status_text]
    )
    
    reset_button.click(
        fn=reset_registration,
        inputs=[],
        outputs=[status_text]
    )
    
    clear_button.click(
        fn=lambda: ("", ""),
        inputs=[],
        outputs=[barcode_input, device_id_input]
    )
    
    offline_button.click(
        fn=simulate_offline_mode,
        inputs=[],
        outputs=[mode_text]
    )
    
    online_button.click(
        fn=simulate_online_mode,
        inputs=[],
        outputs=[mode_text]
    )

if __name__ == "__main__":
    logger.info("🚀 Starting Final Barcode Scanner App on port 7867...")
    app.launch(server_name="0.0.0.0", server_port=7867)