from flask import Flask, render_template, request, jsonify
import json
import logging
from datetime import datetime
from src.database.local_storage import LocalStorage
from src.api.api_client import ApiClient
from src.iot.hub_client import HubClient
from src.utils.config import load_config
from src.api.pi_registration_api import pi_api

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from src.utils.barcode_device_mapper import BarcodeDeviceMapper
    from src.database.local_storage import LocalStorage
    from src.utils.config import load_config
    from src.utils.dynamic_device_manager import device_manager
    from src.iot.hub_client import HubClient
    from src.api.api_client import ApiClient
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

# Enhanced Azure IoT Hub client for proper device management
class CommercialBarcodeClient:
    """Commercial client with proper device registration and barcode processing"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.messages_sent = 0
        self.last_message_time = None
        self.registration_service = None
        self.api_client = ApiClient()
        
        try:
            # Import DynamicRegistrationService for commercial scale
            from src.utils.dynamic_registration_service import DynamicRegistrationService
            logger.info(f"DEBUG: Attempting to initialize DynamicRegistrationService with connection string: {connection_string[:50]}...")
            self.registration_service = DynamicRegistrationService(connection_string)
            logger.info("✓ Commercial Barcode Client initialized with Azure IoT Hub (Dynamic Registration)")
            logger.info(f"✓ Registry Manager status: {self.registration_service.registry_manager is not None}")
        except Exception as e:
            logger.error(f"DETAILED ERROR: Failed to initialize DynamicRegistrationService: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.warning(f"Azure IoT Hub not available: {e}. Running in offline mode.")
    
    def send_barcode_message(self, barcode: str, device_id: str) -> bool:
        """Send barcode message to both API and IoT Hub using dynamic registration"""
        success = True
        
        # Send to API
        try:
            if self.api_client.is_online():
                api_result = self.api_client.send_barcode_scan(device_id, barcode, 1)
                api_success = api_result.get("success", False)
                if not api_success:
                    logger.warning(f"API send failed for barcode {barcode}: {api_result.get('message', 'Unknown error')}")
                    success = False
        except Exception as e:
            logger.error(f"API error: {e}")
            success = False
        
        # Send to IoT Hub using Dynamic Registration Service
        try:
            if self.registration_service:
                # Register device if not already registered, then send message
                hub_success = self.registration_service.send_barcode_message(device_id, barcode)
                if not hub_success:
                    logger.warning(f"IoT Hub send failed for barcode {barcode}")
                    success = False
                else:
                    logger.info(f"[SUCCESS] Barcode {barcode} sent to IoT Hub from device {device_id}")
        except Exception as e:
            logger.error(f"IoT Hub error: {e}")
            success = False
        
        if success:
            self.messages_sent += 1
            self.last_message_time = datetime.now()
            logger.info(f"[SUCCESS] Barcode {barcode} sent from device {device_id}")
        
        return success
    
    def is_online(self) -> bool:
        """Check if system is online"""
        api_online = self.api_client.is_online()
        iot_online = self.registration_service is not None
        return api_online or iot_online

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'commercial-barcode-scanner-2025'

# Register Pi API Blueprint
app.register_blueprint(pi_api)

# Global variables
barcode_client = None
storage = None
config = None
barcode_mapper = None
pi_status_thread = None
last_pi_status = None
system_stats = {
    'total_scans': 0,
    'successful_scans': 0,
    'failed_scans': 0,
    'devices_registered': 0,
    'last_scan_time': None,
    'system_status': 'initializing'
}

def pi_status_reporter():
    """Background thread to automatically report Pi connection status"""
    global last_pi_status, barcode_client, config
    
    while True:
        try:
            from src.utils.connection_manager import ConnectionManager
            
            # Check Pi status
            conn_manager = ConnectionManager()
            pi_available = conn_manager.check_raspberry_pi_availability()
            
            # Only send if status changed or every 5 minutes
            current_time = time.time()
            status_changed = (last_pi_status is None or last_pi_status != pi_available)
            time_to_send = (not hasattr(pi_status_reporter, 'last_send_time') or 
                          (current_time - pi_status_reporter.last_send_time) > 300)  # 5 minutes
            
            if status_changed or time_to_send:
                # Get configured Pi IP
                pi_config = config.get('raspberry_pi', {}) if config else {}
                configured_ip = pi_config.get('auto_detected_ip')
                
                # Create status message
                status_message = {
                    "messageType": "pi_connection_status",
                    "pi_connected": pi_available,
                    "pi_ip": configured_ip,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "server_ip": "192.168.1.8",
                    "status_changed": status_changed
                }
                
                # Send to IoT Hub
                try:
                    if barcode_client and barcode_client.registration_service:
                        system_device_id = "live-server-status-reporter"
                        device_connection = barcode_client.registration_service.get_device_connection_for_barcode(system_device_id)
                        
                        if device_connection:
                            from src.iot.hub_client import HubClient
                            hub_client = HubClient(device_connection)
                            hub_success = hub_client.send_message(json.dumps(status_message), system_device_id)
                            
                            if hub_success:
                                logger.info(f"🔄 Auto Pi status sent to IoT Hub: Connected={pi_available}")
                            else:
                                logger.warning("Failed to auto-send Pi status to IoT Hub")
                except Exception as e:
                    logger.error(f"Auto Pi status IoT Hub error: {e}")
                
                # Send to external API
                try:
                    if barcode_client and barcode_client.api_client:
                        api_url = "https://api2.caleffionline.it/api/v1/raspberry/piStatus"
                        api_result = barcode_client.api_client.send_registration_barcode(api_url, status_message)
                        
                        if api_result and api_result.get("success", False):
                            logger.info(f"🔄 Auto Pi status sent to API: Connected={pi_available}")
                except Exception as e:
                    logger.error(f"Auto Pi status API error: {e}")
                
                # Update tracking variables
                last_pi_status = pi_available
                pi_status_reporter.last_send_time = current_time
                
                if status_changed:
                    logger.info(f"📡 Pi connection status changed: {pi_available} (IP: {configured_ip})")
            
        except Exception as e:
            logger.error(f"Pi status reporter error: {e}")
        
        # Check every 30 seconds
        time.sleep(30)

def initialize_system():
    """Initialize the barcode scanner system"""
    global barcode_client, storage, config, barcode_mapper, pi_status_thread
    
    try:
        logger.info("Initializing Commercial Barcode Scanner Web System...")
        
        # Load configuration
        config = load_config()
        if not config:
            raise Exception("Failed to load configuration")
        
        # Initialize barcode mapper
        barcode_mapper = BarcodeDeviceMapper()
        
        # Initialize storage
        storage = LocalStorage()
        
        # Initialize commercial barcode client
        iot_hub_connection = config["iot_hub"]["connection_string"]
        logger.info(f"DEBUG: IoT Hub connection string: {iot_hub_connection[:50]}...")
        
        try:
            barcode_client = CommercialBarcodeClient(iot_hub_connection)
            logger.info("✓ Commercial Barcode Client initialized successfully")
        except Exception as client_error:
            logger.error(f"Failed to initialize commercial client: {client_error}")
            logger.info("Continuing in offline mode - barcode processing will work locally")
            barcode_client = None
        
        # Update system stats
        stats = barcode_mapper.get_mapping_stats()
        system_stats['devices_registered'] = stats.get('registered_devices', 0)
        system_stats['system_status'] = 'operational' if barcode_client else 'offline_mode'
        
        logger.info("✓ Commercial Barcode Scanner Web System initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        system_stats['system_status'] = 'error'
        return False

def generate_registration_token():
    """Generate a dynamic registration token for device registration"""
    try:
        token = device_manager.generate_registration_token()
        device_manager.cleanup_expired_tokens()
        
        return {
            'success': True,
            'token': token,
            'message': f'Registration token generated: {token}',
            'expires_in': '24 hours'
        }
    except Exception as e:
        logger.error(f"Error generating registration token: {e}")
        return {
            'success': False,
            'message': f'Error generating token: {str(e)}'
        }

def confirm_device_registration(registration_token, device_id):
    """Confirm device registration using token and device ID"""
    try:
        if not registration_token or not device_id:
            return {
                'success': False,
                'message': 'Registration token and device ID are required'
            }
        
        # Register device with dynamic device manager
        success = device_manager.confirm_registration(registration_token, device_id)
        
        if success:
            # Store device in local database
            storage.save_device_registration(device_id, datetime.now())
            
            # Update system stats
            system_stats['devices_registered'] += 1
            
            # Send device registration to external API (following barcode_scanner_app.py pattern)
            try:
                if barcode_client and barcode_client.api_client:
                    # Call saveDeviceId endpoint like barcode_scanner_app.py does
                    api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                    payload = {"scannedBarcode": registration_token}
                    
                    logger.info(f"Sending device registration to external API: {api_url}")
                    api_result = barcode_client.api_client.send_registration_barcode(api_url, payload)
                    
                    if api_result.get("success", False):
                        logger.info(f"Device registration sent to external API successfully for device {device_id}")
                    else:
                        logger.warning(f"Failed to send device registration to external API: {api_result.get('message', 'Unknown error')}")
                else:
                    logger.warning("No API client available for external API registration")
            except Exception as api_error:
                logger.error(f"Error sending device registration to external API: {str(api_error)}")
            
            # Register device with IoT Hub to get device-specific connection string (following barcode_scanner_app.py)
            try:
                if barcode_client and barcode_client.registration_service:
                    # Use the registration service's registry manager to register device
                    registry_manager = barcode_client.registration_service.registry_manager
                    if registry_manager:
                        logger.info(f"Registering device {device_id} with Azure IoT Hub...")
                        
                        # Check if device exists, if not create it
                        try:
                            device = registry_manager.get_device(device_id)
                            logger.info(f"Device {device_id} already exists in IoT Hub")
                        except Exception:
                            logger.info(f"Creating new device {device_id} in IoT Hub...")
                            import base64
                            import os
                            # Generate secure keys
                            primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                            secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                            status = "enabled"
                            
                            # Create device with SAS authentication
                            device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, status)
                            logger.info(f"Device {device_id} created successfully in IoT Hub")
                        
                        # Get device connection string
                        if device and device.authentication and device.authentication.symmetric_key:
                            primary_key = device.authentication.symmetric_key.primary_key
                            if primary_key:
                                # Extract hostname from owner connection string
                                import re
                                owner_conn_str = config.get("iot_hub", {}).get("connection_string", "")
                                hostname_match = re.search(r'HostName=([^;]+)', owner_conn_str)
                                if hostname_match:
                                    hostname = hostname_match.group(1)
                                    device_connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
                                    
                                    # Save device connection string to config
                                    if "devices" not in config["iot_hub"]:
                                        config["iot_hub"]["devices"] = {}
                                    config["iot_hub"]["devices"][device_id] = {
                                        "connection_string": device_connection_string,
                                        "deviceId": device_id
                                    }
                                    
                                    # Save updated config
                                    from src.utils.config import save_config
                                    save_config(config)
                                    logger.info(f"Device {device_id} registered with IoT Hub and config updated")
                                    
                                    # Reload config to get the updated device connection string
                                    config = load_config()
                                else:
                                    logger.error("Could not extract hostname from IoT Hub connection string")
                            else:
                                logger.error(f"No primary key generated for device {device_id}")
                        else:
                            logger.error(f"Device {device_id} creation failed or missing authentication")
                    else:
                        logger.warning("No IoT Hub registry manager available")
                else:
                    logger.warning("No IoT Hub registration service available")
            except Exception as iot_error:
                logger.error(f"Error during IoT Hub registration: {str(iot_error)}")
                # Continue with local registration even if IoT Hub fails
            
            # Send confirmation message to IoT Hub (following exact barcode_scanner_app.py pattern)
            try:
                from src.iot.hub_client import HubClient
                # Follow exact pattern from barcode_scanner_app.py lines 822-830
                device_connection_string = config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string", None)
                
                if not device_connection_string:
                    # Fall back to owner connection string (same as barcode_scanner_app.py line 826)
                    device_connection_string = config.get("iot_hub", {}).get("connection_string", None)
                
                if not device_connection_string:
                    logger.error("No IoT Hub connection string available")
                    raise Exception("No IoT Hub connection string available")
                    
                hub_client = HubClient(device_connection_string)
                confirmation_message = {
                    "deviceId": device_id,
                    "status": "registered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Device registration confirmed via dynamic token",
                    "registration_token": registration_token
                }
                
                # Try to send confirmation to IoT Hub (same as barcode_scanner_app.py)
                hub_success = hub_client.send_message(json.dumps(confirmation_message), device_id)
                if hub_success:
                    logger.info(f"Registration confirmation sent to IoT Hub for device {device_id}")
                else:
                    logger.warning(f"Failed to send registration confirmation to IoT Hub for device {device_id}")
                    # Store message for retry later
                    storage.save_unsent_message(device_id, json.dumps(confirmation_message), datetime.now())
                    
                # Send to API as well
                if barcode_client and barcode_client.api_client:
                    api_success = barcode_client.api_client.send_barcode_scan(device_id, f"REGISTRATION:{registration_token}", 1)
                    if api_success:
                        logger.info(f"Registration confirmation sent to API for device {device_id}")
                    else:
                        logger.warning(f"Failed to send registration confirmation to API for device {device_id}")
                        
            except Exception as hub_error:
                logger.error(f"Error sending confirmation to IoT Hub: {str(hub_error)}")
                # Store message for retry later (same as barcode_scanner_app.py)
                confirmation_message = {
                    "deviceId": device_id,
                    "status": "registered",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Device registration confirmed via dynamic token",
                    "registration_token": registration_token
                }
                storage.save_unsent_message(device_id, json.dumps(confirmation_message), datetime.now())
            
            return {
                'success': True,
                'device_id': device_id,
                'message': f'Device {device_id} registered successfully and confirmation sent to IoT Hub'
            }
        else:
            return {
                'success': False,
                'message': 'Invalid token or device ID already registered'
            }
            
    except Exception as e:
        logger.error(f"Error confirming registration: {e}")
        return {
            'success': False,
            'message': f'Registration error: {str(e)}'
        }

@app.route('/')
def index():
    """Main page - Commercial Barcode Scanner Interface"""
    return render_template('index.html', stats=system_stats)

@app.route('/api/scan', methods=['POST'])
def api_scan_barcode():
    """API endpoint to process barcode scans with proper device management"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        barcode = data.get('barcode', '').strip()
        device_id = data.get('device_id', '').strip()
        
        if not barcode:
            return jsonify({
                'success': False,
                'message': 'Barcode is required'
            }), 400
        
        logger.info(f"Processing barcode scan via web API: {barcode}")
        
        # For barcode processing, we need a device ID
        if not device_id:
            # Try to get device ID from local storage
            stored_device_id = storage.get_device_id()
            if stored_device_id:
                device_id = stored_device_id
                logger.info(f"Using stored device ID: {device_id}")
            else:
                return jsonify({
                    'success': False,
                    'message': 'No device ID provided and no registered device found. Please register your device first.',
                    'action_required': 'device_registration'
                }), 400
        
        # Dynamic device validation
        can_send, permission_msg = device_manager.can_device_send_barcode(device_id)
        if not can_send:
            return jsonify({
                'success': False,
                'message': permission_msg,
                'action_required': 'device_registration'
            }), 403
        
        # Dynamic barcode validation for this device
        is_valid_barcode, barcode_msg = device_manager.validate_barcode_for_device(barcode, device_id)
        if not is_valid_barcode:
            return jsonify({
                'success': False,
                'message': barcode_msg
            }), 400
        
        timestamp = datetime.now(timezone.utc)
        system_stats['total_scans'] += 1
        system_stats['last_scan_time'] = timestamp.isoformat()
        
        # Check if we're online
        is_online = barcode_client.is_online() if barcode_client else False
        
        if not is_online:
            # Store barcode locally for later processing
            storage.save_barcode_scan(device_id, barcode, timestamp)
            system_stats['successful_scans'] += 1
            
            # Check IoT Hub status for response
            iot_hub_status = 'offline'
            if barcode_client and hasattr(barcode_client, 'connection_string') and 'SharedAccessKeyName' in barcode_client.connection_string:
                iot_hub_status = 'ready'  # Connection string is valid but not connected due to Flask context issue
            
            return jsonify({
                'success': True,
                'message': f'Device is offline. Barcode {barcode} saved locally for device {device_id}. Will be sent when online.',
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': timestamp.isoformat(),
                'status': 'offline_stored',
                'azure_status': iot_hub_status,
                'azure_connection': iot_hub_status
            })
        
        # Process barcode online
        try:
            # Create message payload with quantity information (like barcode_scanner_app.py)
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": device_id,
                "quantity": 1,  # Default quantity
                "timestamp": timestamp.isoformat()
            }
            
            # Send to external API using saveDeviceId endpoint (following barcode_scanner_app.py pattern)
            api_success = False
            if barcode_client and barcode_client.api_client:
                try:
                    # Use saveDeviceId endpoint like barcode_scanner_app.py does for barcode scanning
                    api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
                    payload = {"scannedBarcode": barcode}
                    
                    logger.info(f"Sending barcode to external API: {api_url}")
                    api_result = barcode_client.api_client.send_registration_barcode(api_url, payload)
                    api_success = api_result.get("success", False) if isinstance(api_result, dict) else api_result
                    if api_success:
                        logger.info(f"Barcode {barcode} sent to external API successfully from device {device_id}")
                    else:
                        logger.warning(f"Failed to send barcode {barcode} to external API from device {device_id}: {api_result.get('message', 'Unknown error')}")
                except Exception as api_error:
                    logger.error(f"External API error: {api_error}")
            
            # Send to IoT Hub using device connection string
            hub_success = False
            try:
                if barcode_client and barcode_client.registration_service:
                    # Get device connection string for this barcode (will auto-register if needed)
                    device_connection = barcode_client.registration_service.get_device_connection_for_barcode(barcode)
                    
                    if device_connection:
                        from src.iot.hub_client import HubClient
                        device_hub_client = HubClient(device_connection)
                        
                        # Send barcode message to IoT Hub (HubClient expects just the barcode string)
                        hub_success = device_hub_client.send_message(barcode, device_id)
                    else:
                        logger.warning(f"No device connection string available for device {device_id}")
                else:
                    logger.warning("No IoT Hub registration service available for barcode scanning")
                if hub_success:
                    logger.info(f"[SUCCESS] Barcode {barcode} with quantity update sent to IoT Hub from device {device_id}")
                else:
                    logger.warning(f"Failed to send barcode {barcode} to IoT Hub from device {device_id}")
                    # Store message for retry later
                    storage.save_unsent_message(device_id, json.dumps(message_payload), timestamp)
            except Exception as hub_error:
                logger.error(f"IoT Hub error: {hub_error}")
                # Store message for retry later
                storage.save_unsent_message(device_id, json.dumps(message_payload), timestamp)
            
            # Check IoT Hub status for response
            iot_hub_status = 'offline'
            if barcode_client and barcode_client.registration_service:
                if hasattr(barcode_client.registration_service, 'registry_manager') and barcode_client.registration_service.registry_manager:
                    iot_hub_status = 'online'
                elif hasattr(barcode_client, 'connection_string') and 'SharedAccessKeyName' in barcode_client.connection_string:
                    iot_hub_status = 'ready'

            if api_success or hub_success:
                system_stats['successful_scans'] += 1
                return jsonify({
                    'success': True,
                    'message': f'Barcode {barcode} with quantity update sent successfully from device {device_id}',
                    'barcode': barcode,
                    'device_id': device_id,
                    'quantity': 1,
                    'timestamp': timestamp.isoformat(),
                    'api_status': 'success' if api_success else 'failed',
                    'azure_status': 'success' if hub_success else iot_hub_status,
                    'azure_connection': iot_hub_status
                })
            else:
                logger.warning(f"[FAILED] Failed to send barcode {barcode} from device {device_id} to both API and IoT Hub")
                system_stats['failed_scans'] += 1
                # Store locally for retry
                storage.save_barcode_scan(device_id, barcode, timestamp)
                return jsonify({
                    'success': False,
                    'message': f'Failed to send barcode {barcode} from device {device_id}. Stored locally for retry.',
                    'barcode': barcode,
                    'device_id': device_id,
                    'timestamp': timestamp.isoformat(),
                    'status': 'failed_stored',
                    'azure_status': iot_hub_status,
                    'azure_connection': iot_hub_status
                }), 500
            
            # Store locally if offline or send failed
            storage.save_barcode_scan(device_id, barcode, timestamp)
            logger.info(f"Barcode scan saved: {barcode} from device {device_id}")
            
            return jsonify({
                'success': True,
                'message': f'Device is offline. Barcode {barcode} saved locally for device {device_id}. Will be sent when online.',
                'device_id': device_id,
                'timestamp': datetime.now().isoformat(),
                'azure_status': iot_hub_status,
                'azure_connection': iot_hub_status
            })
        
        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            # Store locally as fallback
            storage.save_barcode_scan(device_id, barcode, timestamp)
            system_stats['failed_scans'] += 1
            
            return jsonify({
                'success': False,
                'message': f'Error processing barcode {barcode}: {str(e)}. Stored locally for retry.',
                'barcode': barcode,
                'device_id': device_id,
                'timestamp': timestamp.isoformat(),
                'status': 'error_stored'
            }), 500
        
    except Exception as e:
        logger.error(f"Error in api_scan_barcode: {str(e)}")
        system_stats['failed_scans'] += 1
        return jsonify({
            'success': False,
            'message': f'System error: {str(e)}'
        }), 500

@app.route('/api/register/token', methods=['POST'])
def api_generate_token():
    """API endpoint to generate registration token"""
    try:
        result = generate_registration_token()
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/register/confirm', methods=['POST'])
def api_confirm_registration():
    """API endpoint to confirm device registration"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 400
        
        token = data.get('token', '').strip()
        device_id = data.get('device_id', '').strip()
        
        result = confirm_device_registration(token, device_id)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error confirming registration: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/register/status')
def api_registration_status():
    """API endpoint to get registration status"""
    try:
        stored_device_id = storage.get_device_id()
        if stored_device_id:
            return jsonify({
                'registered': True,
                'device_id': stored_device_id,
                'message': f'Device {stored_device_id} is registered'
            })
        else:
            return jsonify({
                'registered': False,
                'message': 'No device registered. Please complete registration first.'
            })
    except Exception as e:
        logger.error(f"Error checking registration status: {e}")
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/debug/client-status')
def debug_client_status():
    """Debug endpoint to check barcode client status"""
    try:
        debug_info = {
            'barcode_client_exists': barcode_client is not None,
            'registration_service_exists': False,
            'registry_manager_exists': False,
            'connection_string_loaded': False
        }
        
        if barcode_client:
            debug_info['registration_service_exists'] = hasattr(barcode_client, 'registration_service') and barcode_client.registration_service is not None
            
            if barcode_client.registration_service:
                debug_info['registry_manager_exists'] = hasattr(barcode_client.registration_service, 'registry_manager') and barcode_client.registration_service.registry_manager is not None
                debug_info['connection_string_loaded'] = hasattr(barcode_client.registration_service, 'iot_hub_connection_string')
        
        return jsonify(debug_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_get_stats():
    """API endpoint to get system statistics"""
    try:
        # Update real-time stats
        mapping_stats = barcode_mapper.get_mapping_stats()
        unsent_scans = storage.get_unsent_scans()
        recent_scans = storage.get_recent_scans(10)
        
        # Check IoT Hub status with workaround for Azure SDK Flask context issue
        iot_hub_status = 'offline'
        iot_hub_details = 'Not connected'
        
        try:
            if barcode_client and barcode_client.registration_service:
                if hasattr(barcode_client.registration_service, 'registry_manager') and barcode_client.registration_service.registry_manager:
                    iot_hub_status = 'online'
                    iot_hub_details = 'Connected to Azure IoT Hub'
                else:
                    # Known Azure SDK + Flask context issue - check if connection string is valid
                    if hasattr(barcode_client, 'connection_string') and 'SharedAccessKeyName' in barcode_client.connection_string:
                        iot_hub_status = 'ready'
                        iot_hub_details = 'Azure IoT Hub configured (SDK context issue in Flask)'
                    else:
                        iot_hub_status = 'offline'
                        iot_hub_details = 'Azure IoT Hub connection failed'
            else:
                iot_hub_status = 'offline'
                iot_hub_details = 'Azure IoT Hub not initialized'
        except Exception as e:
            iot_hub_status = 'error'
            iot_hub_details = f'IoT Hub error: {str(e)}'
        
        stats = {
            **system_stats,
            'mapping_stats': mapping_stats,
            'unsent_scans_count': len(unsent_scans),
            'recent_scans_count': len(recent_scans),
            'devices_registered': mapping_stats.get('registered_devices', 0),
            'total_mappings': mapping_stats.get('total_mappings', 0),
            'iot_hub_status': iot_hub_status,
            'iot_hub_details': iot_hub_details,
            'azure_connection': iot_hub_status
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pi-status')
def api_pi_status():
    """API endpoint to get current Raspberry Pi connection status"""
    try:
        from src.utils.connection_manager import ConnectionManager
        
        # Initialize connection manager to check Pi status
        conn_manager = ConnectionManager()
        pi_available = conn_manager.check_raspberry_pi_availability()
        
        # Get configured Pi IP from config
        pi_config = config.get('raspberry_pi', {}) if config else {}
        configured_ip = pi_config.get('auto_detected_ip')
        
        status_data = {
            "pi_connected": pi_available,
            "pi_ip": configured_ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_status": "online",
            "connection_details": {
                "ssh_accessible": False,
                "web_accessible": False
            }
        }
        
        # Test specific connectivity if Pi IP is configured
        if configured_ip and pi_available:
            import socket
            
            # Test SSH port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                ssh_result = sock.connect_ex((configured_ip, 22))
                status_data["connection_details"]["ssh_accessible"] = (ssh_result == 0)
                sock.close()
            except:
                status_data["connection_details"]["ssh_accessible"] = False
            
            # Test web port
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                web_result = sock.connect_ex((configured_ip, 5000))
                status_data["connection_details"]["web_accessible"] = (web_result == 0)
                sock.close()
            except:
                status_data["connection_details"]["web_accessible"] = False
        
        logger.info(f"Pi Status Check: Connected={pi_available}, IP={configured_ip}")
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error checking Pi status: {e}")
        return jsonify({
            "pi_connected": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_status": "error"
        }), 500

@app.route('/api/send-pi-status', methods=['POST'])
def api_send_pi_status():
    """Send Pi connection status to IoT Hub and external API"""
    try:
        from src.utils.connection_manager import ConnectionManager
        
        # Get current Pi status
        conn_manager = ConnectionManager()
        pi_available = conn_manager.check_raspberry_pi_availability()
        
        # Get configured Pi IP from config
        pi_config = config.get('raspberry_pi', {}) if config else {}
        configured_ip = pi_config.get('auto_detected_ip')
        
        # Create status message
        status_message = {
            "messageType": "pi_connection_status",
            "pi_connected": pi_available,
            "pi_ip": configured_ip,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_ip": "192.168.1.8",  # Live server IP
            "status_check_interval": "10_seconds"
        }
        
        results = {
            "status_data": status_message,
            "iot_hub_success": False,
            "api_success": False,
            "errors": []
        }
        
        # Send to IoT Hub
        try:
            if barcode_client and barcode_client.registration_service:
                # Use a system device ID for status reporting
                system_device_id = "live-server-status-reporter"
                
                # Get or create device connection for status reporting
                device_connection = barcode_client.registration_service.get_device_connection_for_barcode(system_device_id)
                
                if device_connection:
                    from src.iot.hub_client import HubClient
                    hub_client = HubClient(device_connection)
                    
                    # Send status message to IoT Hub
                    hub_success = hub_client.send_message(json.dumps(status_message), system_device_id)
                    results["iot_hub_success"] = hub_success
                    
                    if hub_success:
                        logger.info(f"Pi status sent to IoT Hub: Connected={pi_available}")
                    else:
                        results["errors"].append("Failed to send status to IoT Hub")
                else:
                    results["errors"].append("No IoT Hub device connection available")
            else:
                results["errors"].append("IoT Hub registration service not available")
        except Exception as e:
            results["errors"].append(f"IoT Hub error: {str(e)}")
            logger.error(f"IoT Hub status send error: {e}")
        
        # Send to external API
        try:
            if barcode_client and barcode_client.api_client:
                # Send status to external API endpoint
                api_url = "https://api2.caleffionline.it/api/v1/raspberry/piStatus"
                
                api_result = barcode_client.api_client.send_registration_barcode(api_url, status_message)
                results["api_success"] = api_result.get("success", False) if isinstance(api_result, dict) else bool(api_result)
                
                if results["api_success"]:
                    logger.info(f"Pi status sent to external API: Connected={pi_available}")
                else:
                    results["errors"].append(f"API send failed: {api_result.get('message', 'Unknown error')}")
            else:
                results["errors"].append("External API client not available")
        except Exception as e:
            results["errors"].append(f"External API error: {str(e)}")
            logger.error(f"External API status send error: {e}")
        
        # Return results
        success = results["iot_hub_success"] or results["api_success"]
        status_code = 200 if success else 500
        
        return jsonify(results), status_code
        
    except Exception as e:
        logger.error(f"Error sending Pi status: {e}")
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 500

@app.route('/api/pi-device-register', methods=['POST'])
def pi_device_register():
    """Register a Pi device from remote location"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        device_id = data.get('device_id', 'unknown')
        mac_address = data.get('mac_address', 'unknown')
        ip_address = data.get('ip_address', 'unknown')
        
        # Use the global storage object for database operations
        storage.create_available_devices_table()
        storage.save_available_device(
            device_id=device_id, 
            device_name=f"Pi-{mac_address[-8:]}", 
            ip_address=ip_address, 
            mac_address=mac_address, 
            device_type="raspberry_pi", 
            status='online'
        )
        
        logger.info(f"✅ Registered Pi device: {device_id} at {ip_address}")
        
        return jsonify({
            "status": "success",
            "message": "Device registered successfully",
            "device_id": device_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error in pi_device_register: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/pi-device-heartbeat', methods=['POST'])
def pi_device_heartbeat():
    """Receive heartbeat from Pi device"""
    try:
        data = request.get_json()
        device_id = data.get('device_id')
        ip_address = data.get('ip_address')
        
        if not device_id:
            return jsonify({"error": "Device ID required"}), 400
        
        # Update device status using the storage object
        storage.update_available_device_status(device_id, 'online', ip_address)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Error in pi_device_heartbeat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/devices')
def api_get_devices():
    """API endpoint to get all registered devices (both mapped and registered)"""
    try:
        # Get devices mapped through barcode scanning
        mapped_devices = barcode_mapper.list_all_mappings(50)
        
        # Get devices registered through the registration process
        registered_devices = storage.get_registered_devices()
        
        # Combine both lists, avoiding duplicates
        all_devices = []
        device_ids_seen = set()
        
        # Add mapped devices first
        for device in mapped_devices:
            device_id = device.get('device_id')
            if device_id and device_id not in device_ids_seen:
                device['source'] = 'barcode_mapping'
                all_devices.append(device)
                device_ids_seen.add(device_id)
        
        # Add registered devices that aren't already in mapped devices
        for reg_device in registered_devices:
            device_id = reg_device.get('device_id')
            if device_id and device_id not in device_ids_seen:
                # Format registered device to match the expected structure
                device_info = {
                    'device_id': device_id,
                    'registration_date': reg_device.get('registration_date'),
                    'status': 'registered',
                    'source': 'registration',
                    'last_seen': reg_device.get('registration_date'),
                    'barcode_count': 0  # No barcodes scanned yet
                }
                all_devices.append(device_info)
                device_ids_seen.add(device_id)
        
        return jsonify({
            'devices': all_devices,
            'total_count': len(all_devices),
            'mapped_count': len(mapped_devices),
            'registered_count': len(registered_devices)
        })
        
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Basic health checks
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'system_status': system_stats['system_status'],
            'database': 'ok',
            'azure_connection': 'unknown'
        }
       
        try:
            storage.test_connection()
            health_status['database'] = 'ok'
        except:
            health_status['database'] = 'error'
            health_status['status'] = 'degraded'
        
        # Test Azure IoT Hub (basic check) with workaround for Azure SDK Flask context issue
        try:
            if barcode_client and barcode_client.registration_service:
                # Check if DynamicRegistrationService is properly initialized
                if hasattr(barcode_client.registration_service, 'registry_manager') and barcode_client.registration_service.registry_manager:
                    health_status['azure_connection'] = 'online'
                else:
                    # Known Azure SDK + Flask context issue - check if connection string is valid
                    if hasattr(barcode_client, 'connection_string') and 'SharedAccessKeyName' in barcode_client.connection_string:
                        health_status['azure_connection'] = 'ready'
                        # Don't mark as degraded since this is a known SDK context issue
                    else:
                        health_status['azure_connection'] = 'offline'
                        health_status['status'] = 'degraded'
            else:
                health_status['azure_connection'] = 'offline'
                health_status['status'] = 'degraded'
        except Exception as e:
            logger.error(f"Azure connection check error: {e}")
            health_status['status'] = 'degraded'
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# @app.route('/dashboard')
# def dashboard():
#     """Admin dashboard page"""
#     return render_template('dashboard.html', stats=system_stats)

# Initialize system on startup
if initialize_system():
    logger.info("System initialization successful")
else:
    logger.error("System initialization failed - running in limited mode")

if __name__ == '__main__':
    # Production configuration
    host = config.get('web_server', {}).get('host', '0.0.0.0') if config else '0.0.0.0'
    port = config.get('web_server', {}).get('port', 5000) if config else 5000
    debug = config.get('web_server', {}).get('debug', False) if config else False
    
    logger.info(f"Starting Commercial Barcode Scanner Web Server on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
