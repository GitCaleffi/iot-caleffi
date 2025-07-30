#!/usr/bin/env python3
"""
Enhanced Device Registration System - FIXED VERSION
Handles device registration, test barcode generation, and API notifications
"""

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
        Complete device registration process:
        1. Check if device exists in local database
        2. Register with Azure IoT Hub if needed
        3. Generate test barcode
        4. Send notification to client API
        5. Update local configuration
        """
        try:
            # Step 1: Check local database and register if needed
            local_result = self._register_device_locally(device_id, device_name)
            
            if not local_result['success'] and 'already registered' not in local_result['message']:
                return {
                    'success': False,
                    'message': f'Local registration failed: {local_result["message"]}',
                    'step': 'local_registration'
                }
            
            # Step 2: Register with Azure IoT Hub
            azure_result = self._register_with_azure_iot(device_id)
            if not azure_result['success']:
                return {
                    'success': False,
                    'message': f'Azure IoT registration failed: {azure_result["message"]}',
                    'step': 'azure_registration'
                }
            
            # Step 3: Get test barcode
            test_barcode = local_result.get('test_barcode') or self._get_device_test_barcode(device_id)
            
            # Step 4: Update configuration
            config_result = self._update_device_config(device_id, azure_result['connection_string'])
            
            # Step 5: Send comprehensive notification to API (FIXED)
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
    
    def _register_device_locally(self, device_id, device_name=None):
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
                    'success': False,
                    'message': f'Device {device_id} already registered',
                    'device_id': device_id
                }
            
            # Generate test barcode for the device
            test_barcode = f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
            
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
    
    def _get_device_test_barcode(self, device_id):
        """Get the test barcode for a device"""
        try:
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT test_barcode FROM device_registry WHERE device_id = ?', (device_id,))
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
        except:
            return f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
    
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
        """Send comprehensive registration notification to client API - FIXED VERSION"""
        try:
            # Use the working saveDeviceId endpoint with notification data
            endpoint = f"{self.api_client.api_base_url}/raspberry/saveDeviceId"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_client.auth_token
            }
            
            # Create payload with notification information
            payload = {
                "scannedBarcode": device_id,
                "notificationType": "device_registration",
                "notificationMessage": "Registration successful! You're all set to get started.",
                "notificationDate": datetime.now().strftime("%Y-%m-%d"),
                "testBarcode": test_barcode,
                "registrationStatus": "success",
                "connectionString": connection_string,
                "registrationTime": datetime.now(timezone.utc).isoformat(),
                "message": f"Device {device_id} has been registered and is ready for use"
            }
            
            logger.info(f"Sending registration notification for device {device_id} to {endpoint}")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=15)
            
            # Handle response safely
            try:
                data = response.json()
                
                if data.get("responseCode") == 200:
                    return {
                        'success': True,
                        'message': 'Registration notification sent to client API successfully',
                        'api_response': data.get("responseMessage", "Success"),
                        'notification_sent': True,
                        'notification_message': "Registration successful! You're all set to get started.",
                        'notification_date': datetime.now().strftime("%Y-%m-%d"),
                        'full_response': data
                    }
                else:
                    return {
                        'success': False,
                        'message': f'API notification failed: {data.get("responseMessage", "Unknown error")}',
                        'api_response': data
                    }
                    
            except json.JSONDecodeError:
                # Handle non-JSON responses
                if response.status_code == 200:
                    return {
                        'success': True,
                        'message': 'Registration notification sent successfully (non-JSON response)',
                        'api_response': response.text,
                        'notification_sent': True,
                        'notification_message': "Registration successful! You're all set to get started.",
                        'notification_date': datetime.now().strftime("%Y-%m-%d")
                    }
                else:
                    return {
                        'success': False,
                        'message': f'API returned status {response.status_code}: {response.text}',
                        'api_response': response.text
                    }
                
        except Exception as e:
            logger.error(f"Failed to send registration notification: {str(e)}")
            return {
                'success': False,
                'message': f'API notification failed: {str(e)}'
            }
    
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
    """Test the enhanced device registration with the fixed notification"""
    registration_system = EnhancedDeviceRegistration()
    
    # Test device registration
    test_device_id = "7356a1840b0e"
    print(f"Testing registration for device: {test_device_id}")
    
    result = registration_system.register_device_complete(test_device_id)
    print(json.dumps(result, indent=2))
    
    # Show API result specifically
    if 'api_result' in result:
        print(f"\nAPI Notification Result:")
        print(json.dumps(result['api_result'], indent=2))

if __name__ == "__main__":
    main()