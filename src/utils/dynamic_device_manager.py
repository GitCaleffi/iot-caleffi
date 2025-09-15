"""
Dynamic Device Manager for Barcode Scanner Application
Handles dynamic device registration, validation, and management for scalable deployment
"""

import json
import logging
import uuid
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)

class DynamicDeviceManager:
    """
    Manages device registration and validation dynamically without hardcoded values.
    Supports scalable deployment for 50,000+ users.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "device_config.json"
        self.device_cache = {}
        self.registration_tokens = {}
        self.lock = threading.RLock()
        self.load_device_config()
        
    def load_device_config(self):
        """Load device configuration from file or create default"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.device_cache = config.get('devices', {})
                    self.registration_tokens = config.get('registration_tokens', {})
            else:
                self.device_cache = {}
                self.registration_tokens = {}
                self.save_device_config()
        except Exception as e:
            logger.error(f"Error loading device config: {e}")
            self.device_cache = {}
            self.registration_tokens = {}
    
    def save_device_config(self):
        """Save device configuration to file"""
        try:
            config = {
                'devices': self.device_cache,
                'registration_tokens': self.registration_tokens,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving device config: {e}")
    
    def generate_registration_token(self, device_identifier: str = None) -> str:
        """
        Generate a unique registration token for device registration.
        This replaces the hardcoded test barcode approach.
        """
        with self.lock:
            # Create unique token based on timestamp, device info, and random UUID
            timestamp = str(int(time.time() * 1000))
            device_part = device_identifier or "unknown"
            unique_id = str(uuid.uuid4())
            
            # Create a hash-based token that's unique but deterministic for the same input
            token_data = f"{timestamp}_{device_part}_{unique_id}"
            token = hashlib.sha256(token_data.encode()).hexdigest()[:16]
            
            # Store token with expiration (24 hours)
            expiration = datetime.now(timezone.utc).timestamp() + (24 * 60 * 60)
            self.registration_tokens[token] = {
                'device_identifier': device_part,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': expiration,
                'used': False
            }
            
            self.save_device_config()
            logger.info(f"Generated registration token: {token}")
            return token
    
    def validate_registration_token(self, token: str) -> Tuple[bool, str]:
        """
        Validate a registration token.
        Returns (is_valid, message)
        """
        with self.lock:
            if token not in self.registration_tokens:
                return False, "Invalid registration token"
            
            token_data = self.registration_tokens[token]
            
            # Check if token is expired
            if datetime.now(timezone.utc).timestamp() > token_data['expires_at']:
                return False, "Registration token has expired"
            
            # Check if token was already used
            if token_data['used']:
                return False, "Registration token has already been used"
            
            return True, "Valid registration token"
    
    def register_device(self, token: str, device_id: str, device_info: Dict = None) -> Tuple[bool, str]:
        """
        Register a device using a valid token.
        Returns (success, message)
        """
        with self.lock:
            # Validate token first
            is_valid, message = self.validate_registration_token(token)
            if not is_valid:
                return False, message
            
            # Check if device_id already exists
            if device_id in self.device_cache:
                return False, f"Device ID {device_id} is already registered"
            
            # Mark token as used
            self.registration_tokens[token]['used'] = True
            
            # Register the device
            self.device_cache[device_id] = {
                'registration_token': token,
                'registered_at': datetime.now(timezone.utc).isoformat(),
                'device_info': device_info or {},
                'status': 'active',
                'last_seen': datetime.now(timezone.utc).isoformat()
            }
            
            self.save_device_config()
            logger.info(f"Device {device_id} registered successfully")
            return True, f"Device {device_id} registered successfully"
    
    def is_device_registered(self, device_id: str) -> bool:
        """Check if a device is registered and active"""
        with self.lock:
            return device_id in self.device_cache and self.device_cache[device_id]['status'] == 'active'
    
    def get_device_info(self, device_id: str) -> Optional[Dict]:
        """Get device information"""
        with self.lock:
            return self.device_cache.get(device_id)
    
    def update_device_last_seen(self, device_id: str):
        """Update the last seen timestamp for a device"""
        with self.lock:
            if device_id in self.device_cache:
                self.device_cache[device_id]['last_seen'] = datetime.now(timezone.utc).isoformat()
                self.save_device_config()
    
    def get_all_devices(self) -> Dict:
        """Get all registered devices"""
        with self.lock:
            return self.device_cache.copy()
    
    def deactivate_device(self, device_id: str) -> Tuple[bool, str]:
        """Deactivate a device"""
        with self.lock:
            if device_id not in self.device_cache:
                return False, "Device not found"
            
            self.device_cache[device_id]['status'] = 'inactive'
            self.device_cache[device_id]['deactivated_at'] = datetime.now(timezone.utc).isoformat()
            self.save_device_config()
            return True, f"Device {device_id} deactivated"
    
    def cleanup_expired_tokens(self):
        """Remove expired registration tokens"""
        with self.lock:
            current_time = datetime.now(timezone.utc).timestamp()
            expired_tokens = [
                token for token, data in self.registration_tokens.items()
                if current_time > data['expires_at']
            ]
            
            for token in expired_tokens:
                del self.registration_tokens[token]
            
            if expired_tokens:
                self.save_device_config()
                logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
    
    def get_device_connection_string(self, device_id: str) -> Optional[str]:
        """
        Get the IoT Hub connection string for a registered device.

        Args:
            device_id: The ID of the device to get the connection string for

        Returns:
            str: The connection string if found, None otherwise
        """
        with self.lock:
            device = self.device_cache.get(device_id)
            if not device or device.get('status') != 'active':
                logger.warning(f"Device {device_id} not found or inactive")
                return None

            # First priority: Get connection string from device info in device_config.json
            if 'connection_string' in device.get('device_info', {}):
                connection_string = device['device_info']['connection_string']
                logger.info(f"Found connection string in device_config.json for {device_id}")
                return connection_string

            # Second priority: Get connection string from main config.json
            try:
                # Try to load config from the main config.json file
                config_path = Path(__file__).resolve().parent.parent.parent / 'config.json'
                if config_path.exists():
                    import json
                    with open(config_path, 'r') as f:
                        config = json.load(f)

                    if config and 'iot_hub' in config and 'devices' in config['iot_hub']:
                        device_configs = config['iot_hub']['devices']
                        if device_id in device_configs:
                            connection_string = device_configs[device_id].get('connection_string')
                            if connection_string:
                                logger.info(f"Found connection string in main config.json for {device_id}")
                                return connection_string

                # Third priority: Try using utils.config if available
                try:
                    from utils.config import load_config
                    config = load_config()
                    if config and 'iot_hub' in config and 'devices' in config['iot_hub']:
                        device_configs = config['iot_hub']['devices']
                        if device_id in device_configs:
                            connection_string = device_configs[device_id].get('connection_string')
                            if connection_string:
                                logger.info(f"Found connection string via utils.config for {device_id}")
                                return connection_string
                except ImportError:
                    logger.debug("utils.config not available, skipping")

                # Fourth priority: Try to generate from IoT Hub connection string
                iot_hub_conn = config.get('iot_hub', {}).get('connection_string') if config else None
                if iot_hub_conn and 'primary_key' in device.get('device_info', {}):
                    hostname = iot_hub_conn.split(';')[0].split('=')[1]
                    primary_key = device['device_info']['primary_key']
                    connection_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
                    logger.info(f"Generated connection string for {device_id}")
                    return connection_string

            except Exception as e:
                logger.error(f"Error getting connection string for {device_id}: {e}")
                return None

            logger.warning(f"No connection string found for device {device_id}")
            return None
    
    def get_registration_stats(self) -> Dict:
        """Get registration statistics"""
        with self.lock:
            active_devices = sum(1 for d in self.device_cache.values() if d['status'] == 'active')
            inactive_devices = sum(1 for d in self.device_cache.values() if d['status'] == 'inactive')
            pending_tokens = sum(1 for t in self.registration_tokens.values() if not t['used'])
            
            return {
                'total_devices': len(self.device_cache),
                'active_devices': active_devices,
                'inactive_devices': inactive_devices,
                'pending_registrations': pending_tokens,
                'total_tokens_generated': len(self.registration_tokens)
            }
    
    def validate_barcode_for_device(self, barcode: str, device_id: str) -> Tuple[bool, str]:
        """
        Validate if a barcode can be processed by a specific device.
        This replaces static barcode validation with dynamic rules.
        """
        with self.lock:
            # Check if device is registered
            if not self.is_device_registered(device_id):
                return False, f"Device {device_id} is not registered or active"
            
            # Update last seen
            self.update_device_last_seen(device_id)
            
            # Dynamic barcode validation (can be extended with custom rules)
            if not barcode or len(barcode.strip()) == 0:
                return False, "Empty barcode not allowed"
            
            # Basic barcode format validation (can be customized)
            if len(barcode) < 4:
                return False, "Barcode too short"
            
            return True, "Barcode valid for device"
    
    def can_device_send_barcode(self, device_id: str) -> Tuple[bool, str]:
        """
        Check if a device can send barcodes (dynamic permission check).
        This replaces static device permission checks.
        """
        with self.lock:
            if not self.is_device_registered(device_id):
                return False, f"Device {device_id} is not registered"
            
            device_info = self.device_cache[device_id]
            
            # Check device status
            if device_info['status'] != 'active':
                return False, f"Device {device_id} is not active"
            
            # Additional dynamic checks can be added here
            # For example: rate limiting, time-based restrictions, etc.
            
            return True, "Device authorized to send barcodes"

# Global instance for the application
device_manager = DynamicDeviceManager()
