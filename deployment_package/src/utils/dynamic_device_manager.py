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
            
            # Check if device ID is already registered
            if device_id in self.device_cache:
                # Update last_seen timestamp for existing device
                self.device_cache[device_id]['last_seen'] = datetime.now(timezone.utc).isoformat()
                self.device_cache[device_id]['status'] = 'active'
                self.save_device_config()
                logger.info(f"Device {device_id} already registered - updated last_seen timestamp")
                return True, f"Device {device_id} already registered and active"
            
            # Mark token as used
            self.registration_tokens[token]['used'] = True
            
            # Register the device
            self.device_cache[device_id] = {
                'device_id': device_id,
                'registered_at': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'status': 'active',
                'registration_token': token,
                'device_info': device_info or {}
            }
            
            self.save_device_config()
            logger.info(f"Device {device_id} registered successfully")
            return True, f"Device {device_id} registered successfully"
    
    def confirm_registration(self, token: str, device_id: str) -> bool:
        """
        Confirm device registration using token and device ID.
        This is an alias for register_device for compatibility.
        """
        success, message = self.register_device(token, device_id)
        if success:
            logger.info(f"Device registration confirmed: {device_id}")
        else:
            logger.error(f"Device registration confirmation failed: {message}")
        return success
    
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
    
    def register_device_without_token(self, device_id: str, device_info: Dict = None) -> Tuple[bool, str]:
        """
        Register a device without requiring a token.
        Returns (success, message)
        """
        with self.lock:
            # Check if device ID is already registered
            if device_id in self.device_cache:
                # Update last_seen timestamp for existing device
                self.device_cache[device_id]['last_seen'] = datetime.now(timezone.utc).isoformat()
                self.device_cache[device_id]['status'] = 'active'
                self.save_device_config()
                logger.info(f"Device {device_id} already registered - updated last_seen timestamp")
                return True, f"Device {device_id} already registered and active"
            
            # Register the device
            self.device_cache[device_id] = {
                'device_id': device_id,
                'registered_at': datetime.now(timezone.utc).isoformat(),
                'last_seen': datetime.now(timezone.utc).isoformat(),
                'status': 'active',
                'registration_method': 'direct',
                'device_info': device_info or {}
            }
            
            self.save_device_config()
            logger.info(f"Device {device_id} registered successfully (without token)")
            return True, f"Device {device_id} registered successfully"
            
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
    
    def get_device_connection_string(self, device_id: str) -> Optional[str]:
        """
        Generate a device-specific connection string for IoT Hub.
        This uses the owner connection string from config and adds the DeviceId parameter.
        """
        try:
            from utils.config import load_config
            
            # Check if device is registered
            if not self.is_device_registered(device_id):
                logger.error(f"Cannot get connection string: Device {device_id} is not registered")
                return None
            
            # Load the IoT Hub owner connection string from config
            config = load_config()
            if not config or 'iot_hub' not in config or 'connection_string' not in config['iot_hub']:
                logger.error("IoT Hub connection string not found in config")
                return None
                
            owner_connection_string = config['iot_hub']['connection_string']
            if not owner_connection_string or owner_connection_string == "REPLACE_WITH_YOUR_IOT_HUB_CONNECTION_STRING":
                logger.error("Invalid IoT Hub connection string in config")
                return None
            
            # Parse the owner connection string
            parts = dict(part.split('=', 1) for part in owner_connection_string.split(';'))
            
            # Check if it has the required parts
            if 'HostName' not in parts or 'SharedAccessKey' not in parts:
                logger.error("Invalid IoT Hub connection string format")
                return None
            
            # Create a device-specific connection string
            device_connection_string = f"HostName={parts['HostName']};DeviceId={device_id};SharedAccessKey={parts['SharedAccessKey']}"
            logger.info(f"Generated device-specific connection string for {device_id}")
            
            return device_connection_string
            
        except Exception as e:
            logger.error(f"Error generating device connection string: {e}")
            return None

# Global instance for the application
device_manager = DynamicDeviceManager()
