"""
API client for communicating with the barcode scanner backend services.
"""

import requests
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Import registration flag to block API calls during registration
try:
    from barcode_scanner_app import REGISTRATION_IN_PROGRESS, registration_lock
except ImportError:
    # Fallback if import fails
    REGISTRATION_IN_PROGRESS = False
    import threading
    registration_lock = threading.Lock()

class ApiClient:
    """Client for handling API communications with the backend services."""
    
    def __init__(self, base_url: str = "https://api2.caleffionline.it/api/v1", timeout: int = 30):
        """
        Initialize the API client.
        
        Args:
            base_url (str): Base URL for the API
            timeout (int): Request timeout in seconds
        """
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'RaspberryPi-BarcodeScanner/1.0'
        })
        
        # Test barcodes that should not be sent to IoT Hub
        self.test_barcodes = {"817994ccfe14"}
    
    def is_online(self) -> bool:
        """
        Check if the device has internet connectivity using Python socket.
        
        Returns:
            bool: True if online, False otherwise
        """
        import socket
        try:
            # Use Python socket connection for live server compatibility
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                result = sock.connect_ex(("8.8.8.8", 53))  # DNS port
            return result == 0
        except Exception as e:
            logger.debug(f"Connectivity check failed: {e}")
            return False
    
    def is_test_barcode(self, barcode: str) -> bool:
        """
        Check if a barcode is a test barcode that should not be sent to IoT Hub.
        
        Args:
            barcode (str): The barcode to check
            
        Returns:
            bool: True if it's a test barcode
        """
        return barcode in self.test_barcodes
    
    def validate_device_id(self, device_id: str) -> Dict[str, Any]:
        """
        Validate if a device ID is valid by calling the API.
        
        Args:
            device_id (str): The device ID to validate
            
        Returns:
            dict: Validation result with isValid, responseMessage, and deviceId if valid
        """
        try:
            url = f"{self.base_url}/raspberry/validateDeviceId"
            payload = {"deviceId": device_id}
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "isValid": result.get("isValid", False),
                    "responseMessage": result.get("message", "Device ID validated"),
                    "deviceId": device_id
                }
            else:
                return {
                    "isValid": False,
                    "responseMessage": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error validating device ID: {e}")
            return {
                "isValid": False,
                "responseMessage": f"Error: {str(e)}"
            }
    
    def get_available_device_ids(self) -> Dict[str, Any]:
        """
        Fetch available device IDs from the registration API.
        
        Returns:
            dict: Result with success flag, device_ids list, and message
        """
        try:
            url = f"{self.base_url}/raspberry/getAvailableDevices"
            
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                result = response.json()
                device_ids = result.get("deviceIds", [])
                return {
                    "success": True,
                    "device_ids": device_ids,
                    "message": f"Successfully fetched {len(device_ids)} device IDs"
                }
            else:
                return {
                    "success": False,
                    "device_ids": [],
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error fetching available device IDs: {e}")
            return {
                "success": False,
                "device_ids": [],
                "message": f"Error: {str(e)}"
            }
    
    def test_registration_barcode(self, barcode: str) -> Dict[str, Any]:
        """
        Test the registration barcode API call.
        
        Args:
            barcode (str): The test barcode to send
            
        Returns:
            dict: Test result with success flag, status_code, message, and response
        """
        try:
            url = f"{self.base_url}/raspberry/saveDeviceId"
            payload = {"scannedBarcode": barcode}
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "message": "Registration API test successful",
                    "response": response.text
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"HTTP {response.status_code}: {response.text}",
                    "response": response.text
                }
                
        except Exception as e:
            logger.error(f"Error testing registration API: {e}")
            return {
                "success": False,
                "status_code": None,
                "message": f"Error: {str(e)}",
                "response": None
            }
    
    def send_registration_barcode(self, api_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a registration barcode to the specified API endpoint.
        
        Args:
            api_url (str): The API endpoint URL
            payload (dict): The payload to send
            
        Returns:
            dict: Result with success flag and message
        """
        try:
            response = self.session.post(
                api_url, 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Registration successful",
                    "response": response.text
                }
            else:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            logger.error(f"Error sending registration barcode: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    def register_device(self, device_id: str) -> Dict[str, Any]:
        """
        Register a device with the API.
        
        Args:
            device_id (str): The device ID to register
            
        Returns:
            dict: Result with success flag and message
        """
        try:
            url = f"{self.base_url}/raspberry/saveDeviceId"  # Changed endpoint
            payload = {"deviceId": device_id}
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Device {device_id} registered successfully",
                    "response": response.json()  # Include full response
                }
            else:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}",
                    "response": response.text
                }
                
        except Exception as e:
            logger.error(f"Error registering device: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "response": None
            }
    
    def confirm_registration(self, device_id: str, pi_ip: str = None) -> Dict[str, Any]:
        """
        Send device registration message to frontend API.
        This will show up as a registration event on the frontend.
        """
        try:
            # Send device registration to the working endpoint
            url = f"{self.base_url}/raspberry/saveDeviceId"
            payload = {
                "scannedBarcode": device_id,  # Use scannedBarcode format for better frontend integration
                "deviceId": device_id,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"📝 Sending device registration to frontend API: {url}")
            logger.info(f"Payload: {json.dumps(payload)}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            logger.info(f"Registration API response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Device {device_id} registration sent to frontend",
                    "response": response.json() if response.text else None
                }
            else:
                return {
                    "success": False,
                    "message": f"Registration API failed: {response.status_code} - {response.text}",
                    "response": response.text
                }
                
        except Exception as e:
            logger.error(f"Error sending device registration: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "response": None
            }
    
    def send_barcode_scan(self, device_id: str, barcode: str, quantity: int = 1) -> Dict[str, Any]:
        """
        Send a barcode scan to the API for processing.
        
        Args:
            device_id (str): The device ID that scanned the barcode
            barcode (str): The scanned barcode
            quantity (int): The quantity scanned (default: 1)
            
        Returns:
            dict: Result with success flag, message, and response data
        """
        # Check if registration is in progress and block quantity updates
        with registration_lock:
            if REGISTRATION_IN_PROGRESS:
                logger.warning("🚫 BLOCKING quantity update - device registration in progress")
                return {
                    "success": False,
                    "message": "Quantity update blocked during device registration",
                    "response": None
                }
        
        try:
            # Use the correct format that works (from our test)
            url = f"{self.base_url}/raspberry/saveDeviceId"
            payload = {
                "deviceId": device_id,
                "barcode": barcode  # Use 'barcode' not 'scannedBarcode'
            }
            
            logger.info(f"Sending barcode scan to API: {url}")
            logger.info(f"Payload: {json.dumps(payload)}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            logger.info(f"API Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Barcode scan sent successfully to frontend API",
                    "response": response.json() if response.text else None
                }
            else:
                return {
                    "success": False,
                    "message": f"API failed: {response.status_code} - {response.text}",
                    "response": response.text
                }
                
        except Exception as e:
            logger.error(f"Error sending barcode scan: {e}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the API.
        
        Returns:
            dict: Health check result
        """
        try:
            url = f"{self.base_url}/health"
            
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "API is healthy",
                    "status_code": response.status_code
                }
            else:
                return {
                    "success": False,
                    "message": f"API health check failed: HTTP {response.status_code}",
                    "status_code": response.status_code
                }
                
        except Exception as e:
            logger.error(f"Error during health check: {e}")
            return {
                "success": False,
                "message": f"Health check error: {str(e)}",
                "status_code": None
            }