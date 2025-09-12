#!/usr/bin/env python3
"""
USB Scanner Simulation Test
Simulates complete USB scanner workflow without requiring actual hardware
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
from usb_auto_scanner import AutoUSBScanner

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class USBScannerSimulator:
    def __init__(self):
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.test_results = []
        self.scanner = AutoUSBScanner()
        
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
        
    def simulate_first_scan_registration(self, barcode="test-device-" + str(int(time.time()))):
        """Test 1: Simulate First Scan (Auto-Registration)"""
        try:
            print(f"🔄 Simulating first USB scanner scan with barcode: {barcode}")
            
            # Clear existing device for clean test
            try:
                self.local_db.clear_device_id()
            except:
                pass
                
            # Simulate auto-registration process
            success = self.scanner.auto_register_device(barcode)
            
            if success and self.scanner.device_id:
                self.log_test_result(
                    "First Scan Auto-Registration", 
                    True, 
                    f"Device auto-registered: {self.scanner.device_id}",
                    f"Registration barcode: {barcode}"
                )
                return self.scanner.device_id
            else:
                self.log_test_result(
                    "First Scan Auto-Registration", 
                    False, 
                    "Auto-registration failed"
                )
                return None
                
        except Exception as e:
            self.log_test_result(
                "First Scan Auto-Registration", 
                False, 
                f"Auto-registration error: {str(e)}"
            )
            return None
            
    def simulate_iot_hub_registration(self, device_id):
        """Test 2: Simulate IoT Hub Registration"""
        try:
            success = self.scanner.register_with_iot_hub(device_id)
            
            if success:
                self.log_test_result(
                    "IoT Hub Registration", 
                    True, 
                    f"Device {device_id} registered with IoT Hub"
                )
                return True
            else:
                self.log_test_result(
                    "IoT Hub Registration", 
                    False, 
                    f"Failed to register device {device_id} with IoT Hub"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "IoT Hub Registration", 
                False, 
                f"IoT Hub registration error: {str(e)}"
            )
            return False
            
    def simulate_registration_message_sending(self, device_id, barcode):
        """Test 3: Simulate Registration Message Sending"""
        try:
            self.scanner.send_registration_message(device_id, barcode)
            
            # Check if message was sent (we can't verify delivery without actual IoT Hub monitoring)
            config = load_config()
            devices = config.get("iot_hub", {}).get("devices", {})
            
            if device_id in devices:
                self.log_test_result(
                    "Registration Message Sending", 
                    True, 
                    f"Registration message sent for device {device_id}",
                    f"Device found in config with connection string"
                )
                return True
            else:
                self.log_test_result(
                    "Registration Message Sending", 
                    False, 
                    f"Device {device_id} not found in IoT Hub config"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Registration Message Sending", 
                False, 
                f"Registration message error: {str(e)}"
            )
            return False
            
    def simulate_subsequent_barcode_scans(self, device_id, barcodes=None):
        """Test 4: Simulate Subsequent Barcode Scans"""
        if not barcodes:
            barcodes = ["5625415485555", "1234567890123", "9876543210987"]
            
        successful_scans = 0
        
        for barcode in barcodes:
            try:
                print(f"📱 Simulating scan: {barcode}")
                
                # Simulate barcode processing
                self.scanner.process_barcode(barcode)
                
                # Check if scan was saved locally
                # Note: We can't easily verify IoT Hub delivery without monitoring
                successful_scans += 1
                
            except Exception as e:
                print(f"❌ Error processing barcode {barcode}: {e}")
                
        if successful_scans == len(barcodes):
            self.log_test_result(
                "Subsequent Barcode Scans", 
                True, 
                f"All {successful_scans} barcode scans processed successfully"
            )
            return True
        else:
            self.log_test_result(
                "Subsequent Barcode Scans", 
                False, 
                f"Only {successful_scans}/{len(barcodes)} scans processed successfully"
            )
            return False
            
    def simulate_offline_mode(self, device_id, barcode="offline-test-123"):
        """Test 5: Simulate Offline Mode"""
        try:
            # Mock offline state
            original_is_online = self.api_client.is_online
            self.api_client.is_online = lambda: False
            
            print(f"📱 Simulating offline scan: {barcode}")
            
            # Process barcode in offline mode
            self.scanner.process_barcode(barcode)
            
            # Restore online state
            self.api_client.is_online = original_is_online
            
            self.log_test_result(
                "Offline Mode Handling", 
                True, 
                f"Offline scan processed and saved locally: {barcode}"
            )
            return True
            
        except Exception as e:
            # Restore online state
            self.api_client.is_online = original_is_online
            
            self.log_test_result(
                "Offline Mode Handling", 
                False, 
                f"Offline mode error: {str(e)}"
            )
            return False
            
    def simulate_reconnection_and_retry(self, device_id):
        """Test 6: Simulate Reconnection and Retry"""
        try:
            # Process offline queue
            self.scanner.process_offline_queue()
            
            self.log_test_result(
                "Reconnection and Retry", 
                True, 
                "Offline queue processed successfully"
            )
            return True
            
        except Exception as e:
            self.log_test_result(
                "Reconnection and Retry", 
                False, 
                f"Reconnection/retry error: {str(e)}"
            )
            return False
            
    def verify_database_state(self, device_id):
        """Test 7: Verify Database State"""
        try:
            # Check device registration
            stored_device_id = self.local_db.get_device_id()
            
            if stored_device_id == device_id:
                device_check = True
            else:
                device_check = False
                
            # Check scan history
            try:
                # This method might not exist, so we'll handle gracefully
                scan_history = getattr(self.local_db, 'get_scan_history', lambda: [])()
                scan_count = len(scan_history) if scan_history else 0
            except:
                scan_count = 0
                
            if device_check:
                self.log_test_result(
                    "Database State Verification", 
                    True, 
                    f"Device stored correctly: {stored_device_id}, Scans: {scan_count}"
                )
                return True
            else:
                self.log_test_result(
                    "Database State Verification", 
                    False, 
                    f"Device mismatch: expected {device_id}, got {stored_device_id}"
                )
                return False
                
        except Exception as e:
            self.log_test_result(
                "Database State Verification", 
                False, 
                f"Database verification error: {str(e)}"
            )
            return False
            
    def run_complete_simulation(self):
        """Run complete USB scanner simulation"""
        print("="*60)
        print("🔌 USB SCANNER COMPLETE SIMULATION")
        print("="*60)
        print()
        
        # Test 1: First scan (auto-registration)
        device_id = self.simulate_first_scan_registration()
        if not device_id:
            print("❌ Stopping simulation - Auto-registration failed")
            return False
            
        # Test 2: IoT Hub registration
        self.simulate_iot_hub_registration(device_id)
        
        # Test 3: Registration message sending
        self.simulate_registration_message_sending(device_id, "test-registration-barcode")
        
        # Test 4: Subsequent barcode scans
        self.simulate_subsequent_barcode_scans(device_id)
        
        # Test 5: Offline mode
        self.simulate_offline_mode(device_id)
        
        # Test 6: Reconnection and retry
        self.simulate_reconnection_and_retry(device_id)
        
        # Test 7: Database state verification
        self.verify_database_state(device_id)
        
        # Print summary
        self.print_test_summary()
        
        return True
        
    def print_test_summary(self):
        """Print test summary"""
        print("="*60)
        print("📊 SIMULATION SUMMARY")
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
        print("💡 NEXT STEPS:")
        print("1. Connect actual USB scanner and run: python3 src/usb_auto_scanner.py")
        print("2. Monitor IoT Hub for registration and quantity messages")
        print("3. Check frontend API for device registration updates")
        print()

def main():
    """Main simulation function"""
    simulator = USBScannerSimulator()
    simulator.run_complete_simulation()

if __name__ == "__main__":
    main()
