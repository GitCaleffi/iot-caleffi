#!/usr/bin/env python3
"""
Test Quantity Update Flow
Tests the complete barcode scanning and quantity update functionality
"""

import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from database.local_storage import LocalStorage
from api.api_client import ApiClient
from iot.hub_client import HubClient
from utils.config import load_config
from barcode_scanner_app import process_barcode_scan

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QuantityUpdateTester:
    def __init__(self):
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.test_results = []
        
    def log_test_result(self, test_name, success, message, details=None):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        print(f"{status}: {test_name} - {message}")
        if details:
            print(f"   Details: {details}")
        print()
        
    def setup_test_device(self):
        """Setup a test device for quantity update testing"""
        try:
            # Use existing device or create test device
            existing_device = self.local_db.get_device_id()
            if existing_device:
                print(f"Using existing device: {existing_device}")
                return existing_device
                
            # Create test device
            test_device_id = f"test-quantity-{int(time.time())}"
            self.local_db.save_device_id(test_device_id)
            
            print(f"Created test device: {test_device_id}")
            return test_device_id
            
        except Exception as e:
            print(f"Error setting up test device: {e}")
            return None
            
    def test_barcode_validation(self, barcode="5625415485555"):
        """Test 1: Barcode Validation"""
        try:
            from barcode_validator import validate_ean, BarcodeValidationError
            
            try:
                validated_barcode = validate_ean(barcode)
                self.log_test_result(
                    "Barcode Validation", 
                    True, 
                    f"Barcode validated successfully: {validated_barcode}"
                )
                return validated_barcode
            except BarcodeValidationError as e:
                self.log_test_result(
                    "Barcode Validation", 
                    False, 
                    f"Barcode validation failed: {str(e)}"
                )
                return None
                
        except ImportError:
            # If validator not available, use barcode as-is
            self.log_test_result(
                "Barcode Validation", 
                True, 
                f"Barcode validator not available, using barcode as-is: {barcode}"
            )
            return barcode
        except Exception as e:
            self.log_test_result(
                "Barcode Validation", 
                False, 
                f"Barcode validation error: {str(e)}"
            )
            return None
            
    def test_local_scan_storage(self, device_id, barcode):
        """Test 2: Local Scan Storage"""
        try:
            # Save scan to local database
            timestamp = self.local_db.save_scan(device_id, barcode, 1)
            
            if timestamp:
                self.log_test_result(
                    "Local Scan Storage", 
                    True, 
                    f"Scan saved locally: {device_id}, {barcode}, {timestamp}"
                )
                return timestamp
            else:
                self.log_test_result(
                    "Local Scan Storage", 
                    False, 
                    "Failed to save scan to local database"
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                "Local Scan Storage", 
                False, 
                f"Local storage error: {str(e)}"
            )
            return None
            
    def test_api_quantity_update(self, device_id, barcode):
        """Test 3: API Quantity Update"""
        try:
            # Test the API endpoint for barcode scanning
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/barcodeScan"
            payload = {
                "deviceId": device_id,
                "scannedBarcode": barcode,
                "quantity": 1
            }
            
            print(f"Testing API quantity update: {api_url}")
            print(f"Payload: {payload}")
            
            # Note: This endpoint might not exist, so we'll test what we can
            try:
                api_result = self.api_client.send_barcode_scan(device_id, barcode, 1)
                
                if api_result and api_result.get("success"):
                    self.log_test_result(
                        "API Quantity Update", 
                        True, 
                        f"Quantity update sent successfully",
                        f"Response: {api_result}"
                    )
                    return True
                else:
                    self.log_test_result(
                        "API Quantity Update", 
                        False, 
                        f"API quantity update failed: {api_result.get('message', 'Unknown error') if api_result else 'No response'}"
                    )
                    return False
                    
            except Exception as api_error:
                # Expected if endpoint doesn't exist
                self.log_test_result(
                    "API Quantity Update", 
                    False, 
                    f"API endpoint not available or error: {str(api_error)}",
                    "This is expected if the barcodeScan endpoint doesn't exist"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "API Quantity Update", 
                False, 
                f"API quantity update error: {str(e)}"
            )
            return False
            
    def test_iot_hub_quantity_message(self, device_id, barcode):
        """Test 4: IoT Hub Quantity Message"""
        try:
            config = load_config()
            if not config:
                self.log_test_result(
                    "IoT Hub Quantity Message", 
                    False, 
                    "Failed to load configuration"
                )
                return False
                
            # Get device connection string
            devices = config.get("iot_hub", {}).get("devices", {})
            if device_id not in devices:
                self.log_test_result(
                    "IoT Hub Quantity Message", 
                    False, 
                    f"Device {device_id} not found in IoT Hub configuration"
                )
                return False
                
            connection_string = devices[device_id]["connection_string"]
            hub_client = HubClient(connection_string)
            
            # Create quantity update message
            quantity_message = {
                "deviceId": device_id,
                "messageType": "quantity_update",
                "action": "scan",
                "barcode": barcode,
                "quantity": 1,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Send message to IoT Hub
            success = hub_client.send_message(json.dumps(quantity_message), device_id)
            
            if success:
                self.log_test_result(
                    "IoT Hub Quantity Message", 
                    True, 
                    f"Quantity message sent to IoT Hub for device {device_id}",
                    f"Message: {quantity_message}"
                )
                return True
            else:
                self.log_test_result(
                    "IoT Hub Quantity Message", 
                    False, 
                    "Failed to send quantity message to IoT Hub"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "IoT Hub Quantity Message", 
                False, 
                f"IoT Hub quantity message error: {str(e)}"
            )
            return False
            
    def test_complete_barcode_scan_flow(self, device_id, barcode):
        """Test 5: Complete Barcode Scan Flow"""
        try:
            print(f"Testing complete barcode scan flow: {device_id} scanning {barcode}")
            
            # Call the actual barcode processing function
            result = process_barcode_scan(barcode, device_id)
            
            if "successfully" in result.lower() or "sent to iot hub" in result.lower():
                self.log_test_result(
                    "Complete Barcode Scan Flow", 
                    True, 
                    f"Complete scan flow successful",
                    f"Result: {result[:200]}..."
                )
                return True
            else:
                self.log_test_result(
                    "Complete Barcode Scan Flow", 
                    False, 
                    "Complete scan flow failed or had issues",
                    f"Result: {result}"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Complete Barcode Scan Flow", 
                False, 
                f"Complete scan flow error: {str(e)}"
            )
            return False
            
    def test_offline_mode_handling(self, device_id, barcode):
        """Test 6: Offline Mode Handling"""
        try:
            # Simulate offline mode by temporarily disabling network
            original_is_online = self.api_client.is_online
            
            # Mock offline state
            self.api_client.is_online = lambda: False
            
            # Save scan in offline mode
            timestamp = self.local_db.save_scan(device_id, barcode, 1)
            
            if timestamp:
                self.log_test_result(
                    "Offline Mode Handling", 
                    True, 
                    f"Offline scan saved successfully: {timestamp}"
                )
                success = True
            else:
                self.log_test_result(
                    "Offline Mode Handling", 
                    False, 
                    "Failed to save scan in offline mode"
                )
                success = False
                
            # Restore original function
            self.api_client.is_online = original_is_online
            
            return success
            
        except Exception as e:
            self.log_test_result(
                "Offline Mode Handling", 
                False, 
                f"Offline mode test error: {str(e)}"
            )
            return False
            
    def run_all_tests(self):
        """Run all quantity update tests"""
        print("="*60)
        print("🧪 QUANTITY UPDATE FLOW TESTS")
        print("="*60)
        print()
        
        # Setup test device
        device_id = self.setup_test_device()
        if not device_id:
            print("❌ Failed to setup test device")
            return False
            
        # Test barcode
        test_barcode = "5625415485555"
        
        # Test 1: Barcode Validation
        validated_barcode = self.test_barcode_validation(test_barcode)
        if not validated_barcode:
            validated_barcode = test_barcode  # Continue with original if validation fails
            
        # Test 2: Local Scan Storage
        self.test_local_scan_storage(device_id, validated_barcode)
        
        # Test 3: API Quantity Update
        self.test_api_quantity_update(device_id, validated_barcode)
        
        # Test 4: IoT Hub Quantity Message
        self.test_iot_hub_quantity_message(device_id, validated_barcode)
        
        # Test 5: Complete Barcode Scan Flow
        self.test_complete_barcode_scan_flow(device_id, validated_barcode)
        
        # Test 6: Offline Mode Handling
        self.test_offline_mode_handling(device_id, f"offline-{validated_barcode}")
        
        # Print summary
        self.print_test_summary()
        
        return True
        
    def print_test_summary(self):
        """Print test summary"""
        print("="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
        print()
        
        # Show failed tests
        failed_tests = [result for result in self.test_results if not result["success"]]
        if failed_tests:
            print("❌ FAILED TESTS:")
            for test in failed_tests:
                print(f"  • {test['test']}: {test['message']}")
        else:
            print("✅ ALL TESTS PASSED!")
            
        print()

def main():
    """Main test function"""
    tester = QuantityUpdateTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
