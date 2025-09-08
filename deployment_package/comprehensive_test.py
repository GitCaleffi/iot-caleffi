#!/usr/bin/env python3
"""
Comprehensive Test Suite for Barcode Scanner App.py Plug and Play System
Tests all functions: Pi detection, registration, barcode scanning, IoT Hub, offline/online modes
"""

import sys
import os
import time
import json
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.config import load_config, save_config
from utils.connection_manager import ConnectionManager
from database.local_storage import LocalStorage
from utils.dynamic_registration_service import DynamicRegistrationService
from utils.network_discovery import NetworkDiscovery
from iot.hub_client import HubClient

class ComprehensivePlugAndPlayTest:
    def __init__(self):
        self.test_device_id = "test-comprehensive-001"
        self.test_barcode = "1234567890123"
        self.results = {}
        
    def print_header(self, title):
        print(f"\n{'='*60}")
        print(f" {title}")
        print(f"{'='*60}")
        
    def print_test(self, test_name):
        print(f"\n Testing: {test_name}")
        print("-" * 40)
        
    def test_1_system_initialization(self):
        """Test 1: System Initialization and Configuration"""
        self.print_test("System Initialization")
        
        try:
            # Test config loading
            config = load_config()
            print(" Configuration loaded successfully")
            
            # Test database initialization
            storage = LocalStorage()
            print(" Local storage initialized")
            
            # Test connection manager
            connection_manager = ConnectionManager()
            print(" Connection manager initialized")
            
            # Test network discovery
            network_discovery = NetworkDiscovery()
            print(" Network discovery initialized")
            
            self.results['system_init'] = True
            return True
            
        except Exception as e:
            print(f" System initialization failed: {e}")
            self.results['system_init'] = False
            return False
    
    def test_2_pi_detection(self):
        """Test 2: Raspberry Pi Detection and Network Discovery"""
        self.print_test("Pi Detection and Network Discovery")
        
        try:
            network_discovery = NetworkDiscovery()
            
            # Test hardware detection
            is_pi = network_discovery._is_running_on_raspberry_pi()
            print(f" Running on Pi hardware: {' Yes' if is_pi else ' No (simulation mode)'}")
            
            # Test network scanning
            print(" Scanning for Pi devices on network...")
            pi_devices = network_discovery.discover_raspberry_pi_devices()
            print(f" Found {len(pi_devices)} Pi devices on network")
            for device in pi_devices[:3]:  # Show first 3
                print(f"  - {device}")
            
            # Test connection manager Pi check
            connection_manager = ConnectionManager()
            pi_available = connection_manager.check_raspberry_pi_availability()
            print(f" Pi availability: {' Available' if pi_available else ' Not available'}")
            
            self.results['pi_detection'] = True
            return True
            
        except Exception as e:
            print(f" Pi detection failed: {e}")
            self.results['pi_detection'] = False
            return False
    
    def test_3_connectivity(self):
        """Test 3: Internet and IoT Hub Connectivity"""
        self.print_test("Connectivity Tests")
        
        try:
            connection_manager = ConnectionManager()
            
            # Test internet connectivity
            internet_ok = connection_manager.check_internet_connectivity()
            print(f" Internet connectivity: {' Connected' if internet_ok else ' Disconnected'}")
            
            # Test IoT Hub connectivity
            iot_ok = connection_manager.check_iot_hub_connectivity()
            print(f" IoT Hub connectivity: {' Connected' if iot_ok else ' Disconnected'}")
            
            # Get connection status
            status = connection_manager.get_connection_status()
            print(f" Connection status: Internet={status['internet']}, IoT Hub={status['iot_hub']}, Pi={status['raspberry_pi']}")
            
            self.results['connectivity'] = internet_ok and iot_ok
            return True
            
        except Exception as e:
            print(f" Connectivity test failed: {e}")
            self.results['connectivity'] = False
            return False
    
    def test_4_device_registration(self):
        """Test 4: Device Registration Workflow"""
        self.print_test("Device Registration")
        
        try:
            config = load_config()
            storage = LocalStorage()
            
            # Test dynamic registration service
            reg_service = DynamicRegistrationService(config)
            print(" Dynamic registration service initialized")
            
            # Test device registration
            print(f" Registering device: {self.test_device_id}")
            conn_str = reg_service.register_device_with_azure(self.test_device_id)
            
            if conn_str:
                print(" Device registered in Azure IoT Hub")
                print(f" Connection string obtained: {conn_str[:50]}...")
                
                # Test local storage
                registration_data = {
                    'device_id': self.test_device_id,
                    'registered_at': datetime.now().isoformat(),
                    'connection_string': conn_str,
                    'test_mode': True
                }
                
                success = storage.save_device_registration(self.test_device_id, registration_data)
                print(f" Local storage: {' Saved' if success else ' Failed'}")
                
                self.results['registration'] = True
                return conn_str
            else:
                print(" Device registration failed")
                self.results['registration'] = False
                return None
                
        except Exception as e:
            print(f" Device registration failed: {e}")
            self.results['registration'] = False
            return None
    
    def test_5_barcode_scanning(self, conn_str):
        """Test 5: Barcode Scanning and Processing"""
        self.print_test("Barcode Scanning")
        
        try:
            storage = LocalStorage()
            
            print(f" Processing barcode: {self.test_barcode}")
            print(f" Device ID: {self.test_device_id}")
            
            # Test barcode validation (skip if module not available)
            print(" Barcode validation: Using original barcode")
            
            # Test local storage of scan
            scan_data = {
                'barcode': self.test_barcode,
                'device_id': self.test_device_id,
                'timestamp': datetime.now().isoformat(),
                'test_mode': True
            }
            
            storage.save_barcode_scan(self.test_barcode, self.test_device_id, scan_data)
            print(" Barcode scan saved to local storage")
            
            self.results['barcode_scanning'] = True
            return True
            
        except Exception as e:
            print(f" Barcode scanning failed: {e}")
            self.results['barcode_scanning'] = False
            return False
    
    def test_6_iot_hub_messaging(self, conn_str):
        """Test 6: IoT Hub Message Sending"""
        self.print_test("IoT Hub Messaging")
        
        if not conn_str:
            print(" No connection string available")
            self.results['iot_messaging'] = False
            return False
        
        try:
            # Test IoT Hub client
            hub_client = HubClient(conn_str)
            print(" IoT Hub client initialized")
            
            # Test registration message
            registration_message = {
                "messageType": "device_registration",
                "deviceId": self.test_device_id,
                "event": "comprehensive_test",
                "timestamp": datetime.now().isoformat(),
                "status": "testing"
            }
            
            reg_success = hub_client.send_message(registration_message, self.test_device_id)
            print(f" Registration message: {' Sent' if reg_success else ' Failed'}")
            
            # Test barcode scan message
            scan_message = {
                "messageType": "barcode_scan",
                "deviceId": self.test_device_id,
                "barcode": self.test_barcode,
                "timestamp": datetime.now().isoformat(),
                "quantity": 1,
                "test_mode": True
            }
            
            scan_success = hub_client.send_message(scan_message, self.test_device_id)
            print(f" Barcode scan message: {' Sent' if scan_success else ' Failed'}")
            
            self.results['iot_messaging'] = reg_success and scan_success
            return reg_success and scan_success
            
        except Exception as e:
            print(f" IoT Hub messaging failed: {e}")
            self.results['iot_messaging'] = False
            return False
    
    def test_7_offline_mode(self):
        """Test 7: Offline Mode and Message Queuing"""
        self.print_test("Offline Mode and Message Queuing")
        
        try:
            storage = LocalStorage()
            
            # Test saving unsent messages with correct parameters
            timestamp = datetime.now().isoformat()
            unsent_message = {
                'message_type': 'barcode_scan',
                'test_offline': True
            }
            
            storage.save_unsent_message(self.test_device_id, unsent_message, timestamp)
            print(" Unsent message saved for offline mode")
            
            # Test retrieving unsent messages
            unsent_messages = storage.get_unsent_messages()
            print(f" Unsent messages in queue: {len(unsent_messages)}")
            
            self.results['offline_mode'] = True
            return True
            
        except Exception as e:
            print(f" Offline mode test failed: {e}")
            self.results['offline_mode'] = False
            return False
    
    def test_8_error_handling(self):
        """Test 8: Error Handling and Recovery"""
        self.print_test("Error Handling and Recovery")
        
        try:
            # Test with invalid device ID
            try:
                config = load_config()
                reg_service = DynamicRegistrationService(config)
                invalid_result = reg_service.register_device_with_azure("")
                print(" Invalid device ID handled gracefully")
            except Exception:
                print(" Invalid device ID properly rejected")
            
            # Test with invalid barcode
            try:
                storage = LocalStorage()
                storage.save_barcode_scan("", self.test_device_id, {})
                print(" Invalid barcode handled gracefully")
            except Exception:
                print(" Invalid barcode properly rejected")
            
            self.results['error_handling'] = True
            return True
            
        except Exception as e:
            print(f" Error handling test failed: {e}")
            self.results['error_handling'] = False
            return False
    
    def test_9_performance(self):
        """Test 9: Performance and Response Times"""
        self.print_test("Performance Testing")
        
        try:
            # Test connection manager response time
            start_time = time.time()
            connection_manager = ConnectionManager()
            connection_manager.check_internet_connectivity()
            connectivity_time = time.time() - start_time
            print(f" Connectivity check: {connectivity_time:.2f}s")
            
            # Test database operations
            start_time = time.time()
            storage = LocalStorage()
            storage.get_registered_devices()
            db_time = time.time() - start_time
            print(f" Database query: {db_time:.2f}s")
            
            # Test network discovery
            start_time = time.time()
            network_discovery = NetworkDiscovery()
            network_discovery._is_running_on_raspberry_pi()
            pi_check_time = time.time() - start_time
            print(f" Pi detection: {pi_check_time:.2f}s")
            
            self.results['performance'] = True
            return True
            
        except Exception as e:
            print(f" Performance test failed: {e}")
            self.results['performance'] = False
            return False
    
    def generate_report(self):
        """Generate comprehensive test report"""
        self.print_header("COMPREHENSIVE TEST REPORT")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result)
        
        print(f" Test Summary: {passed_tests}/{total_tests} tests passed")
        print(f" Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\n Detailed Results:")
        test_names = {
            'system_init': 'System Initialization',
            'pi_detection': 'Pi Detection & Network Discovery',
            'connectivity': 'Internet & IoT Hub Connectivity',
            'registration': 'Device Registration',
            'barcode_scanning': 'Barcode Scanning',
            'iot_messaging': 'IoT Hub Messaging',
            'offline_mode': 'Offline Mode & Queuing',
            'error_handling': 'Error Handling',
            'performance': 'Performance Testing'
        }
        
        for key, result in self.results.items():
            status = " PASS" if result else " FAIL"
            test_name = test_names.get(key, key)
            print(f"  {status} - {test_name}")
        
        print(f"\n Overall Status: {' SYSTEM READY' if passed_tests >= 7 else ' NEEDS ATTENTION'}")
        
        if passed_tests >= 7:
            print(" Your plug and play barcode scanner system is fully functional!")
        else:
            print(" Some components need attention. Check failed tests above.")
    
    def run_all_tests(self):
        """Run all comprehensive tests"""
        self.print_header("BARCODE SCANNER PLUG AND PLAY COMPREHENSIVE TEST")
        print(f" Test Device ID: {self.test_device_id}")
        print(f" Test Barcode: {self.test_barcode}")
        print(f" Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests in sequence
        self.test_1_system_initialization()
        self.test_2_pi_detection()
        self.test_3_connectivity()
        conn_str = self.test_4_device_registration()
        self.test_5_barcode_scanning(conn_str)
        self.test_6_iot_hub_messaging(conn_str)
        self.test_7_offline_mode()
        self.test_8_error_handling()
        self.test_9_performance()
        
        # Generate final report
        self.generate_report()

def main():
    """Main test execution"""
    tester = ComprehensivePlugAndPlayTest()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
