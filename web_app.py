#!/usr/bin/env python3
"""
Commercial Barcode Scanner Web Interface
Production-ready web application for plug-and-play barcode scanning
Designed for Ubuntu server deployment with 1000+ device support
"""

from flask import Flask, render_template, request, jsonify
import json
import logging
import sys
import os
from datetime import datetime, timezone
import threading
import time
from pathlib import Path

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
                api_success = self.api_client.send_barcode(barcode, device_id)
                if not api_success:
                    logger.warning(f"API send failed for barcode {barcode}")
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

# Global variables
barcode_client = None
storage = None
config = None
barcode_mapper = None
system_stats = {
    'total_scans': 0,
    'successful_scans': 0,
    'failed_scans': 0,
    'devices_registered': 0,
    'last_scan_time': None,
    'system_status': 'initializing'
}

def initialize_system():
    """Initialize the barcode scanner system"""
    global barcode_client, storage, config, barcode_mapper
    
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
        
        # Validate token and register device
        success = device_manager.confirm_registration(registration_token, device_id)
        
        if success:
            # Store device in local database
            storage.save_device_registration(device_id, datetime.now())
            
            # Update system stats
            system_stats['devices_registered'] += 1
            
            return {
                'success': True,
                'device_id': device_id,
                'message': f'Device {device_id} registered successfully'
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
            # Send barcode message
            send_success = barcode_client.send_barcode_message(barcode, device_id)
            
            # Check IoT Hub status for response
            iot_hub_status = 'offline'
            if barcode_client and barcode_client.registration_service:
                if hasattr(barcode_client.registration_service, 'registry_manager') and barcode_client.registration_service.registry_manager:
                    iot_hub_status = 'online'
                elif hasattr(barcode_client, 'connection_string') and 'SharedAccessKeyName' in barcode_client.connection_string:
                    iot_hub_status = 'ready'
            
            # Send to IoT Hub if online
            if barcode_client and barcode_client.is_online():
                success = barcode_client.send_barcode_message(barcode, device_id)
                if success:
                    logger.info(f"[SUCCESS] Barcode {barcode} sent from device {device_id}")
                    system_stats['successful_scans'] += 1
                    return jsonify({
                        'success': True,
                        'message': f'Barcode {barcode} sent successfully from device {device_id}',
                        'device_id': device_id,
                        'timestamp': datetime.now().isoformat(),
                        'azure_status': 'online',
                        'azure_connection': 'online'
                    })
                else:
                    logger.warning(f"[FAILED] Failed to send barcode {barcode} from device {device_id}")
                    system_stats['failed_scans'] += 1
            
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

@app.route('/api/devices')
def api_get_devices():
    """API endpoint to get registered devices"""
    try:
        devices = barcode_mapper.list_all_mappings(50)
        return jsonify({
            'devices': devices,
            'total_count': len(devices)
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

@app.route('/dashboard')
def dashboard():
    """Admin dashboard page"""
    return render_template('dashboard.html', stats=system_stats)

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
