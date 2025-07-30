import requests
import logging
import json
from pathlib import Path
import sys
import os

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from utils.config import load_config

logger = logging.getLogger(__name__)

class ApiClient:
    def __init__(self):
        """Initialize API client with configuration"""
        self.config = load_config()
        self.api_base_url = "https://api2.caleffionline.it/api/v1"
        self.auth_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NiwiZW1haWwiOiJhcnBpNUB5b3BtYWlsLmNvbSIsImN1c3RvbWVySWQiOiI4MjAwNDciLCJpYXQiOjE3NDIxODYzODF9.cijDSnyQhpjMC89oOmSQ10oCBJHT6nHjqADzGwhrxpM"
        self.timeout = 10  # seconds
        
    def validate_device_id(self, barcode):
        """
        Validate if a barcode is a valid device ID by calling the API
        
        Args:
            barcode (str): The barcode to validate
            
        Returns:
            dict: Response with validation result and message
                {
                    "isValid": bool,
                    "responseMessage": str,
                    "deviceId": str (if valid)
                }
        """
        try:
            # Prepare API endpoint and headers
            endpoint = f"{self.api_base_url}/raspberry/saveDeviceId"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.auth_token
            }
            
            # Prepare payload
            payload = {
                "scannedBarcode": barcode
            }
            
            # Make API request
            logger.info(f"Validating device ID: {barcode}")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            # Parse response
            data = response.json()
            logger.info(f"API response: {data}")
            
            # Check response code and message
            if data.get("responseCode") == 200:
                if data.get("responseMessage") == "Action completed successfully":
                    # Extract device ID from response data
                    device_id = data.get("data", {}).get("deviceId", barcode)
                    if not device_id:  # If deviceId is empty in response, use the barcode
                        device_id = barcode
                        
                    return {
                        "isValid": True,
                        "responseMessage": "Action completed successfully",
                        "deviceId": device_id
                    }
                elif data.get("responseMessage") == "This is a test barcode.":
                    return {
                        "isValid": True,
                        "responseMessage": "This is a test barcode.",
                        "deviceId": "test_device"
                    }
                else:
                    return {
                        "isValid": True,  # It's still a 200 response
                        "responseMessage": data.get("responseMessage", "Unknown response")
                    }
            elif data.get("responseCode") == 400:
                return {
                    "isValid": False,
                    "responseMessage": data.get("responseMessage", "Invalid barcode.")
                }
            else:
                logger.error(f"API request returned unexpected response code: {data.get('responseCode')}")
                return {
                    "isValid": False,
                    "responseMessage": f"API request failed: {data.get('responseMessage', 'Unknown error')}"
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            return {
                "isValid": False,
                "responseMessage": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error during device validation: {str(e)}")
            return {
                "isValid": False,
                "responseMessage": f"Error: {str(e)}"
            }
    
    def is_online(self):
        """
        Check if the API is reachable
        
        Returns:
            bool: True if online, False otherwise
        """
        try:
            # Try to connect to the API with a simple request
            endpoint = f"{self.api_base_url}/raspberry/saveDeviceId"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.auth_token
            }
            # Use a test barcode for the check
            payload = {"scannedBarcode": "test"}
            response = requests.post(endpoint, headers=headers, json=payload, timeout=3)  # Short timeout for quick check
            
            # Even if we get an error response, if we can reach the server, we're online
            return True
        except requests.exceptions.RequestException:
            logger.info("Network appears to be offline")
            return False
        except Exception as e:
            logger.error(f"Error checking online status: {str(e)}")
            return False
            
    def is_test_barcode(self, barcode):
        """
        Determine if a barcode is a test barcode based on API response
        
        Args:
            barcode (str): The barcode to check
            
        Returns:
            bool: True if it's a test barcode, False otherwise
        """
        # Empty barcodes are not test barcodes
        if not barcode:
            return False
            
        # Primary method: Check with the API
        try:
            # Use API client to validate if it's a test barcode
            validation = self.validate_device_id(barcode)
            if validation.get("responseMessage", "") == "This is a test barcode.":
                logger.info(f"API identified {barcode} as a test barcode")
                return True
                
            # Check if API response contains any indicators of this being a test barcode
            response_message = validation.get("responseMessage", "").lower()
            if "test" in response_message or "demo" in response_message or "sample" in response_message:
                logger.info(f"API message indicates {barcode} might be a test barcode: {response_message}")
                return True
                
        except Exception as e:
            logger.warning(f"Failed to check if {barcode} is a test barcode via API: {e}")
            # If API check fails, we need a fallback mechanism
            # For now, let's consider it a production barcode when API fails
            return False
                
        return False
            
    def get_barcode_for_device(self, device_id):
        """
        Get a barcode associated with a specific device ID from the API
        
        Args:
            device_id (str): The device ID to look up
            
        Returns:
            dict: Result with success status, message, and barcode if found
                {
                    "success": bool,
                    "message": str,
                    "barcode": str (if found)
                }
        """
        try:
            # Prepare API endpoint and headers
            endpoint = f"{self.api_base_url}/raspberry/getBarcode"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.auth_token
            }
            
            # Prepare payload
            payload = {
                "deviceId": device_id
            }
            
            # Make API request
            logger.info(f"Getting barcode for device ID: {device_id}")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout)
            
            # Parse response
            data = response.json()
            logger.info(f"API response: {data}")
            
            # Check response code and extract barcode
            if data.get("responseCode") == 200:
                barcode = data.get("data", {}).get("barcode")
                if barcode:
                    return {
                        "success": True,
                        "message": "Barcode retrieved successfully",
                        "barcode": barcode
                    }
                else:
                    return {
                        "success": False,
                        "message": "No barcode found for this device ID"
                    }
            else:
                return {
                    "success": False,
                    "message": data.get("responseMessage", "Failed to retrieve barcode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error: {str(e)}")
            return {
                "success": False,
                "message": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving barcode: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}"
            }
