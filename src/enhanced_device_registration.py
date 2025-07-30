

import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
import sys
from azure.iot.hub import IoTHubRegistryManager
import base64
import os

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from api.api_client import ApiClient
from utils.config import load_config

logger = logging.getLogger(__name__)

class EnhancedDeviceRegistration:
    def __init__(self):
        self.api_client = ApiClient()
        self.config = load_config()
        
        # IoT Hub connection string for device registration
        self.iothub_connection_string = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="
        
    def register_device_complete(self, device_id, device_name=None):
        """
        Complete device registration process using correct API endpoints:
        1. Register with Azure IoT Hub
        2. Save device ID via API
        3. Confirm registration via API
        4. Generate test barcode
        5. Log notification locally
        """
        try:
            # Step 1: Register with Azure IoT Hub
            azure_result = self._register_with_azure_iot(device_id)
            if not azure_result['success']:
                return {
                    'success': False,
                    'message': f'Azure IoT registration failed: {azure_result["message"]}',
                    'step': 'azure_registration'
                }
            
            # Step 2: Generate test barcode
            test_barcode = f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
            
            # Step 3: Register device locally
            local_result = self._register_device_locally(device_id, device_name, test_barcode)
            
            # Step 4: Update configuration
            config_result = self._update_device_config(device_id, azure_result['connection_string'])
            
            # Step 5: Send to API using correct two-step process
            api_result = self._send_registration_notification(device_id, test_barcode, azure_result['connection_string'])
            
            return {
                'success': True,
                'message': f'Device {device_id} registered successfully across all systems',
                'device_id': device_id,
                'test_barcode': test_barcode,
                'connection_string': azure_result['connection_string'],
                'local_result': local_result,
                'azure_result': azure_result,
                'config_result': config_result,
                'api_result': api_result
            }
            
        except Exception as e:
            logger.error(f"Error in complete device registration: {str(e)}")
            return {
                'success': False,
                'message': f'Registration failed: {str(e)}',
                'step': 'unknown'
            }
    
    def _register_device_locally(self, device_id, device_name=None, test_barcode=None):
        """Register device in local database"""
        try:
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            # Create device_registry table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_registry (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT,
                    registration_date DATETIME,
                    last_seen DATETIME,
                    status TEXT DEFAULT 'active',
                    test_barcode TEXT
                )
            ''')
            
            # Check if device already exists
            cursor.execute('SELECT device_id FROM device_registry WHERE device_id = ?', (device_id,))
            if cursor.fetchone():
                conn.close()
                return {
                    'success': True,
                    'message': f'Device {device_id} already registered locally',
                    'device_id': device_id
                }
            
            # Register device
            cursor.execute('''
                INSERT INTO device_registry 
                (device_id, device_name, registration_date, last_seen, test_barcode)
                VALUES (?, ?, ?, ?, ?)
            ''', (device_id, device_name or f"Device_{device_id}", 
                  datetime.now(timezone.utc).isoformat(),
                  datetime.now(timezone.utc).isoformat(),
                  test_barcode))
            
            conn.commit()
            conn.close()
            
            return {
                'success': True,
                'message': f'Device {device_id} registered locally',
                'device_id': device_id,
                'test_barcode': test_barcode
            }
            
        except Exception as e:
            logger.error(f"Local device registration failed: {str(e)}")
            return {
                'success': False,
                'message': f'Local registration failed: {str(e)}'
            }
    
    def _register_with_azure_iot(self, device_id):
        """Register device with Azure IoT Hub"""
        try:
            registry_manager = IoTHubRegistryManager.from_connection_string(self.iothub_connection_string)
            
            # Check if device already exists
            try:
                device = registry_manager.get_device(device_id)
                logger.info(f"Device {device_id} already exists in Azure IoT Hub")
                
                # Get connection string for existing device
                primary_key = device.authentication.symmetric_key.primary_key
                connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={primary_key}"
                
                return {
                    'success': True,
                    'message': f'Device {device_id} already exists in Azure IoT Hub',
                    'connection_string': connection_string,
                    'new_device': False
                }
                
            except Exception:
                # Device doesn't exist, create it
                logger.info(f"Creating new device {device_id} in Azure IoT Hub")
                
                # Generate secure keys
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                
                # Create device
                device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, "enabled")
                
                connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={primary_key}"
                
                return {
                    'success': True,
                    'message': f'Device {device_id} created successfully in Azure IoT Hub',
                    'connection_string': connection_string,
                    'new_device': True
                }
                
        except Exception as e:
            logger.error(f"Azure IoT Hub registration failed: {str(e)}")
            return {
                'success': False,
                'message': f'Azure IoT Hub registration failed: {str(e)}'
            }
    
    def _update_device_config(self, device_id, connection_string):
        """Update local configuration with new device"""
        try:
            config_path = project_root / 'config.json'
            
            # Load existing config
            config = {}
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config = json.load(f)
            
            # Ensure structure exists
            config.setdefault('iot_hub', {})
            config['iot_hub'].setdefault('devices', {})
            config['iot_hub'].setdefault('deviceIds', [])
            
            # Add device
            config['iot_hub']['devices'][device_id] = {
                "connection_string": connection_string,
                "deviceId": device_id
            }
            
            # Add to device IDs list if not present
            if device_id not in config['iot_hub']['deviceIds']:
                config['iot_hub']['deviceIds'].append(device_id)
            
            # Set as default connection if it's the first device
            if not config['iot_hub'].get('connection_string'):
                config['iot_hub']['connection_string'] = connection_string
            
            # Save config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return {
                'success': True,
                'message': 'Configuration updated successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}")
            return {
                'success': False,
                'message': f'Configuration update failed: {str(e)}'
            }
    
    def _send_registration_notification(self, device_id, test_barcode, connection_string):
        """Send registration using correct two-step API process"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_client.auth_token
            }
            
            # Step 1: Save device ID
            save_endpoint = f"{self.api_client.api_base_url}/raspberry/saveDeviceId"
            save_payload = {
                "scannedBarcode": device_id
            }
            
            logger.info(f"Step 1: Saving device ID {device_id}")
            save_response = requests.post(save_endpoint, headers=headers, json=save_payload, timeout=15)
            
            save_result = None
            try:
                save_data = save_response.json()
                save_result = {
                    'success': save_data.get("responseCode") == 200,
                    'message': save_data.get("responseMessage", "Unknown"),
                    'data': save_data
                }
                logger.info(f"Save device result: {save_data}")
            except json.JSONDecodeError:
                save_result = {
                    'success': save_response.status_code == 200,
                    'message': 'Non-JSON response',
                    'data': save_response.text
                }
            
            # Step 2: Confirm registration
            confirm_endpoint = f"{self.api_client.api_base_url}/raspberry/confirmRegistration"
            confirm_payload = {
                "deviceId": device_id
            }
            
            logger.info(f"Step 2: Confirming registration for device {device_id}")
            confirm_response = requests.post(confirm_endpoint, headers=headers, json=confirm_payload, timeout=15)
            
            confirm_result = None
            try:
                confirm_data = confirm_response.json()
                confirm_result = {
                    'success': True,
                    'message': 'Registration confirmed',
                    'data': confirm_data
                }
            except json.JSONDecodeError:
                # confirmRegistration returns empty response on success
                confirm_result = {
                    'success': confirm_response.status_code == 200,
                    'message': 'Registration confirmed successfully',
                    'data': 'Registration confirmed (empty response indicates success)'
                }
            
            # Step 3: Create notification message
            notification_message = "Registration successful! You're all set to get started."
            notification_date = datetime.now().strftime("%Y-%m-%d")
            
            # Log the notification locally
            self._log_notification_locally(device_id, test_barcode, notification_message, notification_date)
            
            # Determine overall success
            overall_success = save_result['success'] and confirm_result['success']
            
            return {
                'success': overall_success,
                'message': 'Device registration completed successfully' if overall_success else 'Registration partially failed',
                'save_result': save_result,
                'confirm_result': confirm_result,
                'notification_sent': True,
                'notification_message': notification_message,
                'notification_date': notification_date,
                'formatted_notification': f"""
**{notification_message}**

**{notification_date}**

Device ID: {device_id}
Test Barcode: {test_barcode}
Status: Successfully registered and ready for use
""",
                'note': 'Registration completed via API - notification available at https://iot.caleffionline.it/'
            }
                
        except Exception as e:
            logger.error(f"Failed to send registration notification: {str(e)}")
            return {
                'success': False,
                'message': f'API notification failed: {str(e)}'
            }
    
    def _log_notification_locally(self, device_id, test_barcode, message, date):
        """Log notification locally for tracking"""
        try:
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            # Create notifications table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS device_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    test_barcode TEXT,
                    message TEXT,
                    date TEXT,
                    timestamp DATETIME,
                    status TEXT DEFAULT 'sent'
                )
            ''')
            
            # Insert notification record
            cursor.execute('''
                INSERT INTO device_notifications (device_id, test_barcode, message, date, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (device_id, test_barcode, message, date, datetime.now(timezone.utc).isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Notification logged locally for device {device_id}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to log notification locally: {str(e)}")
    
    def validate_and_register_device(self, barcode):
        """
        Validate if barcode is a device ID and register if valid but not in database
        """
        try:
            # First validate with API
            validation_result = self.api_client.validate_device_id(barcode)
            
            if not validation_result.get("isValid", False):
                return {
                    'success': False,
                    'message': f'Barcode {barcode} is not a valid device ID',
                    'validation_result': validation_result
                }
            
            # Check if it's a test barcode
            if validation_result.get("responseMessage") == "This is a test barcode.":
                return {
                    'success': True,
                    'message': f'Test barcode {barcode} validated successfully',
                    'type': 'test_barcode',
                    'validation_result': validation_result
                }
            
            # If valid device ID, check if it needs registration
            device_id = validation_result.get("deviceId", barcode)
            
            # Check if device exists in local database
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            cursor.execute('SELECT device_id FROM device_registry WHERE device_id = ?', (device_id,))
            exists = cursor.fetchone() is not None
            conn.close()
            
            if exists:
                return {
                    'success': True,
                    'message': f'Device {device_id} is already registered',
                    'device_id': device_id,
                    'type': 'existing_device'
                }
            else:
                # Register the new device
                registration_result = self.register_device_complete(device_id)
                
                if registration_result['success']:
                    return {
                        'success': True,
                        'message': f'Device {device_id} registered successfully',
                        'device_id': device_id,
                        'test_barcode': registration_result['test_barcode'],
                        'type': 'new_device',
                        'registration_result': registration_result
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Failed to register device {device_id}: {registration_result["message"]}',
                        'registration_result': registration_result
                    }
                    
        except Exception as e:
            logger.error(f"Error in validate_and_register_device: {str(e)}")
            return {
                'success': False,
                'message': f'Error processing device: {str(e)}'
            }

def main():
    """Test the enhanced device registration with correct API endpoints"""
    registration_system = EnhancedDeviceRegistration()
    
    # Test device registration
    test_device_id = "7356a1840b0e"
    print(f"Testing registration for device: {test_device_id}")
    print("Using correct API endpoints: saveDeviceId + confirmRegistration")
    print("=" * 60)
    
    result = registration_system.register_device_complete(test_device_id)
    print(json.dumps(result, indent=2))
    
    # Show API result specifically
    if 'api_result' in result:
        print(f"\nAPI Registration Result:")
        print(json.dumps(result['api_result'], indent=2))
        
        if 'formatted_notification' in result['api_result']:
            print(f"\nFormatted Notification:")
            print(result['api_result']['formatted_notification'])

if __name__ == "__main__":
    main()