"""
API client for communicating with the barcode scanner backend services.
"""

import requests
import json
import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# Registration control - avoid circular import
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
        Confirm device registration with the API.
        
        IMPORTANT: This method is for DEVICE REGISTRATION ONLY - NO INVENTORY UPDATES!
        
        Args:
            device_id (str): The device ID to confirm registration for
            pi_ip (str): The Raspberry Pi IP address (optional)
            
        Returns:
            dict: Result with success flag and message
        """
        try:
            url = f"{self.base_url}/raspberry/confirmRegistration"
            payload = {
                "deviceId": device_id,
                "timestamp": int(time.time()),
                "status": "registered",
                "operation_type": "device_registration",  # Explicit operation type
                "messageType": "device_registration",  # Additional explicit type
                "action": "registration_confirmation",  # Clear action type
                "no_inventory_update": True,  # Explicit flag to prevent inventory updates
                "registration_only": True  # Additional safety flag
            }
            
            # Add Pi IP if provided
            if pi_ip:
                payload["pi_ip"] = pi_ip
            
            logger.info(f"🔒 REGISTRATION ONLY - NO INVENTORY UPDATES")
            logger.info(f"Sending confirmation registration to: {url}")
            logger.info(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                url, 
                json=payload, 
                timeout=self.timeout
            )
            
            logger.info(f"Confirmation registration response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                # Handle empty response body gracefully
                response_data = None
                if response.text and response.text.strip():
                    try:
                        response_data = response.json()
                    except json.JSONDecodeError:
                        response_data = response.text
                
                return {
                    "success": True,
                    "message": f"Device {device_id} registration confirmed successfully (NO INVENTORY IMPACT)",
                    "response": response_data
                }
            else:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}",
                    "response": response.text
                }
                
        except Exception as e:
            logger.error(f"Error confirming device registration: {e}")
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
            # Use only the working API endpoint with correct payload format
            endpoints_to_try = [
                ("raspberry/saveDeviceId", {"deviceId": barcode}),  # API expects deviceId field with barcode value
            ]
            
            last_error = None
            for endpoint, payload in endpoints_to_try:
                try:
                    url = f"{self.base_url}/{endpoint}"
                    response = self.session.post(
                        url, 
                        json=payload, 
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"API success with endpoint {endpoint}: {response.text}")
                        return {
                            "success": True,
                            "message": f"Barcode scan sent successfully via {endpoint}"
                        }
                    else:
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        logger.warning(f"API endpoint {endpoint} failed: {last_error}")
                        
                except Exception as e:
                    last_error = f"Error: {str(e)}"
                    logger.warning(f"API endpoint {endpoint} error: {last_error}")
            
            # If all endpoints failed, return the last error
            return {
                "success": False,
                "message": f"All API endpoints failed. Last error: {last_error}"
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