#!/usr/bin/env python3
"""
Test Device Registration Flow
Tests the complete device registration API flow and IoT Hub messaging
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
from barcode_scanner_app import process_barcode_scan, register_device_with_iot_hub

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RegistrationFlowTester:
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
        
    def test_api_connectivity(self):
        """Test 1: API Connectivity"""
        try:
            is_online = self.api_client.is_online()
            if is_online:
                self.log_test_result(
                    "API Connectivity", 
                    True, 
                    "Successfully connected to API"
                )
                return True
            else:
                self.log_test_result(
                    "API Connectivity", 
                    False, 
                    "Failed to connect to API"
                )
                return False
        except Exception as e:
            self.log_test_result(
                "API Connectivity", 
                False, 
                f"API connectivity error: {str(e)}"
            )
            return False
            
    def test_device_registration_api(self, test_barcode="7079fa7ab32e"):
        """Test 2: Device Registration API Call"""
        try:
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
            payload = {"scannedBarcode": test_barcode}
            
            print(f"Testing device registration with barcode: {test_barcode}")
            api_result = self.api_client.send_registration_barcode(api_url, payload)
            
            if api_result.get("success", False):
                response_data = json.loads(api_result["response"])
                device_id = response_data.get("deviceId")
                
                self.log_test_result(
                    "Device Registration API", 
                    True, 
                    f"Device registered successfully: {device_id}",
                    f"Response: {response_data}"
                )
                return device_id
            else:
                self.log_test_result(
                    "Device Registration API", 
                    False, 
                    f"Registration failed: {api_result.get('message', 'Unknown error')}"
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                "Device Registration API", 
                False, 
                f"Registration API error: {str(e)}"
            )
            return None
            
    def test_iot_hub_device_creation(self, device_id):
        """Test 3: IoT Hub Device Creation"""
        try:
            registration_result = register_device_with_iot_hub(device_id)
            
            if registration_result.get("success"):
                connection_string = registration_result.get("connection_string")
                self.log_test_result(
                    "IoT Hub Device Creation", 
                    True, 
                    f"Device {device_id} created in IoT Hub",
                    f"Connection string generated: {connection_string[:50]}..."
                )
                return connection_string
            else:
                self.log_test_result(
                    "IoT Hub Device Creation", 
                    False, 
                    f"Failed to create device: {registration_result.get('error')}"
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                "IoT Hub Device Creation", 
                False, 
                f"IoT Hub creation error: {str(e)}"
            )
            return None
            
    def test_registration_message_sending(self, device_id, connection_string, test_barcode):
        """Test 4: Registration Message Sending to IoT Hub"""
        try:
            hub_client = HubClient(connection_string)
            
            # Create registration message
            registration_message = {
                "deviceId": device_id,
                "messageType": "device_registration",
                "action": "register",
                "scannedBarcode": test_barcode,
                "registrationMethod": "test_script",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "registered"
            }
            
            # Send message
            success = hub_client.send_message(json.dumps(registration_message), device_id)
            
            if success:
                self.log_test_result(
                    "Registration Message Sending", 
                    True, 
                    f"Registration message sent to IoT Hub for device {device_id}",
                    f"Message: {registration_message}"
                )
                return True
            else:
                self.log_test_result(
                    "Registration Message Sending", 
                    False, 
                    "Failed to send registration message to IoT Hub"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Registration Message Sending", 
                False, 
                f"Registration message error: {str(e)}"
            )
            return False
            
    def test_local_database_storage(self, device_id):
        """Test 5: Local Database Storage"""
        try:
            # Save device ID
            self.local_db.save_device_id(device_id)
            
            # Retrieve device ID
            stored_device_id = self.local_db.get_device_id()
            
            if stored_device_id == device_id:
                self.log_test_result(
                    "Local Database Storage", 
                    True, 
                    f"Device ID stored and retrieved successfully: {device_id}"
                )
                return True
            else:
                self.log_test_result(
                    "Local Database Storage", 
                    False, 
                    f"Device ID mismatch: stored {stored_device_id}, expected {device_id}"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Local Database Storage", 
                False, 
                f"Database storage error: {str(e)}"
            )
            return False
            
    def test_complete_registration_flow(self, test_barcode="817994ccfe14"):
        """Test 6: Complete Registration Flow (Simulates USB Scanner)"""
        try:
            print(f"Testing complete registration flow with barcode: {test_barcode}")
            
            # Clear existing device ID for clean test
            try:
                self.local_db.clear_device_id()
            except:
                pass
                
            # Call the actual registration function
            result = process_barcode_scan(test_barcode)
            
            # Check if device was registered
            registered_device_id = self.local_db.get_device_id()
            
            if registered_device_id and "Device Registration Successful" in result:
                self.log_test_result(
                    "Complete Registration Flow", 
                    True, 
                    f"Complete flow successful: {registered_device_id}",
                    f"Result: {result[:200]}..."
                )
                return registered_device_id
            else:
                self.log_test_result(
                    "Complete Registration Flow", 
                    False, 
                    "Complete flow failed or device not registered",
                    f"Result: {result}"
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                "Complete Registration Flow", 
                False, 
                f"Complete flow error: {str(e)}"
            )
            return None
            
    def run_all_tests(self):
        """Run all registration tests"""
        print("="*60)
        print("🧪 DEVICE REGISTRATION FLOW TESTS")
        print("="*60)
        print()
        
        # Test 1: API Connectivity
        if not self.test_api_connectivity():
            print("❌ Stopping tests - API not accessible")
            return False
            
        # Test 2: Device Registration API
        test_barcode = "817994ccfe14"
        device_id = self.test_device_registration_api(test_barcode)
        if not device_id:
            print("❌ Stopping tests - Device registration failed")
            return False
            
        # Test 3: IoT Hub Device Creation
        connection_string = self.test_iot_hub_device_creation(device_id)
        if not connection_string:
            print("❌ Stopping tests - IoT Hub device creation failed")
            return False
            
        # Test 4: Registration Message Sending
        self.test_registration_message_sending(device_id, connection_string, test_barcode)
        
        # Test 5: Local Database Storage
        self.test_local_database_storage(device_id)
        
        # Test 6: Complete Registration Flow
        self.test_complete_registration_flow("test-registration-" + str(int(time.time())))
        
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
    tester = RegistrationFlowTester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
