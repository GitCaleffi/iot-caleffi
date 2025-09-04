#!/usr/bin/env python3
"""
Automated Test Suite for Plug-and-Play Barcode Scanner System
Provides comprehensive automated testing for all system components
"""

import os
import sys
import time
import json
import sqlite3
import threading
import subprocess
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

try:
    from database.db_manager import DatabaseManager
    from utils.connection_manager import ConnectionManager
    from barcode_scanner_app import (
        check_ethernet_connection, 
        get_auto_device_id,
        is_device_registered,
        process_barcode_automatically,
        auto_register_device
    )
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

class TestResults:
    """Track test results and generate reports"""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.failures = []
        self.start_time = time.time()
    
    def add_result(self, test_name, passed, error_msg=None):
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            print(f"✅ {test_name}")
        else:
            self.tests_failed += 1
            self.failures.append((test_name, error_msg))
            print(f"❌ {test_name}: {error_msg}")
    
    def print_summary(self):
        duration = time.time() - self.start_time
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Tests Run: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        
        if self.failures:
            print(f"\n❌ FAILURES:")
            for test_name, error in self.failures:
                print(f"  - {test_name}: {error}")
        
        return self.tests_failed == 0

class AutomatedTestSuite:
    """Main test suite for barcode scanner system"""
    
    def __init__(self):
        self.results = TestResults()
        self.test_db_path = "test_barcode_scanner.db"
        self.backup_db_path = None
        
    def setup_test_environment(self):
        """Setup isolated test environment"""
        print("🔧 Setting up test environment...")
        
        # Backup existing database if it exists
        if os.path.exists("deployment_package/barcode_scanner.db"):
            self.backup_db_path = f"barcode_scanner_backup_{int(time.time())}.db"
            os.rename("deployment_package/barcode_scanner.db", self.backup_db_path)
            print(f"📦 Backed up existing database to {self.backup_db_path}")
        
        # Create test database
        try:
            db = DatabaseManager()
            print("✅ Test database initialized")
        except Exception as e:
            print(f"❌ Failed to initialize test database: {e}")
            return False
        
        return True
    
    def cleanup_test_environment(self):
        """Cleanup test environment and restore backups"""
        print("🧹 Cleaning up test environment...")
        
        # Remove test database
        if os.path.exists("deployment_package/barcode_scanner.db"):
            os.remove("deployment_package/barcode_scanner.db")
        
        # Restore backup if it exists
        if self.backup_db_path and os.path.exists(self.backup_db_path):
            os.rename(self.backup_db_path, "deployment_package/barcode_scanner.db")
            print(f"📦 Restored database from backup")
    
    def test_database_operations(self):
        """Test database connectivity and operations"""
        print("\n📊 Testing Database Operations...")
        
        try:
            db = DatabaseManager()
            
            # Test connection
            tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
            self.results.add_result("Database Connection", len(tables) > 0)
            
            # Test insert operation
            test_barcode = "TEST123456789"
            db.execute_query(
                "INSERT INTO barcode_scans (barcode, device_id, timestamp) VALUES (?, ?, ?)",
                (test_barcode, "TEST_DEVICE", datetime.now().isoformat())
            )
            
            # Test select operation
            result = db.fetch_all("SELECT * FROM barcode_scans WHERE barcode = ?", (test_barcode,))
            self.results.add_result("Database Insert/Select", len(result) == 1)
            
            # Test delete operation
            db.execute_query("DELETE FROM barcode_scans WHERE barcode = ?", (test_barcode,))
            result = db.fetch_all("SELECT * FROM barcode_scans WHERE barcode = ?", (test_barcode,))
            self.results.add_result("Database Delete", len(result) == 0)
            
        except Exception as e:
            self.results.add_result("Database Operations", False, str(e))
    
    def test_connection_manager(self):
        """Test connection manager functionality"""
        print("\n🌐 Testing Connection Manager...")
        
        try:
            cm = ConnectionManager()
            
            # Test initialization
            self.results.add_result("Connection Manager Init", cm is not None)
            
            # Test internet connectivity check
            internet_status = cm.check_internet_connectivity()
            self.results.add_result("Internet Connectivity Check", 
                                  isinstance(internet_status, bool))
            
            # Test LAN Pi check
            lan_status = cm.check_lan_pi_connection()
            self.results.add_result("LAN Pi Connection Check", 
                                  isinstance(lan_status, bool))
            
            # Test network discovery
            devices = cm.discover_network_devices()
            self.results.add_result("Network Device Discovery", 
                                  isinstance(devices, list))
            
        except Exception as e:
            self.results.add_result("Connection Manager", False, str(e))
    
    def test_device_id_generation(self):
        """Test automatic device ID generation"""
        print("\n🆔 Testing Device ID Generation...")
        
        try:
            device_id = get_auto_device_id()
            
            # Test device ID is generated
            self.results.add_result("Device ID Generation", 
                                  device_id is not None and len(device_id) > 0)
            
            # Test device ID consistency
            device_id2 = get_auto_device_id()
            self.results.add_result("Device ID Consistency", device_id == device_id2)
            
        except Exception as e:
            self.results.add_result("Device ID Generation", False, str(e))
    
    def test_ethernet_detection(self):
        """Test ethernet connection detection"""
        print("\n🔌 Testing Ethernet Detection...")
        
        try:
            # Test ethernet check function
            ethernet_status = check_ethernet_connection()
            self.results.add_result("Ethernet Detection Function", 
                                  isinstance(ethernet_status, bool))
            
            # Test with mocked network interface
            with patch('subprocess.run') as mock_run:
                # Mock successful ethernet detection
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>"
                
                ethernet_status = check_ethernet_connection()
                self.results.add_result("Mocked Ethernet Detection (Connected)", 
                                      ethernet_status == True)
                
                # Mock no ethernet detection
                mock_run.return_value.stdout = ""
                ethernet_status = check_ethernet_connection()
                self.results.add_result("Mocked Ethernet Detection (Disconnected)", 
                                      ethernet_status == False)
            
        except Exception as e:
            self.results.add_result("Ethernet Detection", False, str(e))
    
    def test_device_registration(self):
        """Test device registration functionality"""
        print("\n📝 Testing Device Registration...")
        
        try:
            test_device_id = "TEST_DEVICE_" + str(int(time.time()))
            
            # Test initial registration status
            is_registered = is_device_registered(test_device_id)
            self.results.add_result("Initial Registration Check", is_registered == False)
            
            # Test device registration
            with patch('src.barcode_scanner_app.check_ethernet_connection', return_value=True):
                with patch('src.barcode_scanner_app.ConnectionManager') as mock_cm:
                    mock_cm.return_value.check_internet_connectivity.return_value = True
                    
                    registration_success = auto_register_device(test_device_id, "TEST123456")
                    self.results.add_result("Device Auto-Registration", registration_success)
            
            # Test registration status after registration
            is_registered_after = is_device_registered(test_device_id)
            self.results.add_result("Post-Registration Check", is_registered_after == True)
            
        except Exception as e:
            self.results.add_result("Device Registration", False, str(e))
    
    def test_barcode_processing(self):
        """Test barcode processing functionality"""
        print("\n📊 Testing Barcode Processing...")
        
        try:
            test_device_id = "TEST_DEVICE_BARCODE"
            test_barcode = "1234567890123"
            
            # Ensure device is registered
            db = DatabaseManager()
            db.execute_query(
                "INSERT OR REPLACE INTO device_registrations (device_id, registration_date, status) VALUES (?, ?, ?)",
                (test_device_id, datetime.now().isoformat(), "active")
            )
            
            # Test barcode processing with mocked connection
            with patch('src.barcode_scanner_app.check_ethernet_connection', return_value=True):
                with patch('src.barcode_scanner_app.ConnectionManager') as mock_cm:
                    mock_cm.return_value.check_internet_connectivity.return_value = True
                    
                    # Mock API calls to prevent actual network requests
                    with patch('requests.post') as mock_post:
                        mock_post.return_value.status_code = 200
                        mock_post.return_value.json.return_value = {"success": True}
                        
                        result = process_barcode_automatically(test_barcode, test_device_id)
                        self.results.add_result("Barcode Processing (Online)", "✅" in result)
            
            # Test barcode processing offline
            with patch('src.barcode_scanner_app.check_ethernet_connection', return_value=False):
                result = process_barcode_automatically(test_barcode, test_device_id)
                self.results.add_result("Barcode Processing (Offline)", "saved locally" in result.lower())
            
        except Exception as e:
            self.results.add_result("Barcode Processing", False, str(e))
    
    def test_unsent_message_handling(self):
        """Test unsent message storage and processing"""
        print("\n📤 Testing Unsent Message Handling...")
        
        try:
            db = DatabaseManager()
            
            # Add test unsent message
            test_message = {
                "barcode": "TEST987654321",
                "device_id": "TEST_DEVICE_UNSENT",
                "timestamp": datetime.now().isoformat()
            }
            
            db.execute_query(
                "INSERT INTO unsent_messages (message_data, timestamp, retry_count) VALUES (?, ?, ?)",
                (json.dumps(test_message), test_message["timestamp"], 0)
            )
            
            # Verify message was stored
            unsent = db.fetch_all("SELECT * FROM unsent_messages WHERE message_data LIKE ?", 
                                ("%TEST987654321%",))
            self.results.add_result("Unsent Message Storage", len(unsent) > 0)
            
            # Test message retrieval
            all_unsent = db.fetch_all("SELECT * FROM unsent_messages")
            self.results.add_result("Unsent Message Retrieval", len(all_unsent) >= 1)
            
            # Clean up test message
            db.execute_query("DELETE FROM unsent_messages WHERE message_data LIKE ?", 
                           ("%TEST987654321%",))
            
        except Exception as e:
            self.results.add_result("Unsent Message Handling", False, str(e))
    
    def test_concurrent_operations(self):
        """Test system behavior under concurrent access"""
        print("\n⚡ Testing Concurrent Operations...")
        
        def concurrent_db_access(thread_id, results_list):
            try:
                db = DatabaseManager()
                for i in range(5):
                    # Perform database operations
                    test_barcode = f"CONCURRENT_{thread_id}_{i}"
                    db.execute_query(
                        "INSERT INTO barcode_scans (barcode, device_id, timestamp) VALUES (?, ?, ?)",
                        (test_barcode, f"THREAD_{thread_id}", datetime.now().isoformat())
                    )
                    time.sleep(0.01)  # Small delay
                results_list.append(True)
            except Exception as e:
                results_list.append(False)
        
        try:
            # Run concurrent database operations
            threads = []
            results_list = []
            
            for i in range(3):
                thread = threading.Thread(target=concurrent_db_access, args=(i, results_list))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Check results
            success_count = sum(results_list)
            self.results.add_result("Concurrent Database Access", 
                                  success_count == len(threads))
            
            # Clean up concurrent test data
            db = DatabaseManager()
            db.execute_query("DELETE FROM barcode_scans WHERE barcode LIKE 'CONCURRENT_%'")
            
        except Exception as e:
            self.results.add_result("Concurrent Operations", False, str(e))
    
    def test_error_handling(self):
        """Test system error handling"""
        print("\n🚨 Testing Error Handling...")
        
        try:
            # Test invalid barcode handling
            result = process_barcode_automatically("", "TEST_DEVICE")
            self.results.add_result("Empty Barcode Handling", "invalid" in result.lower())
            
            # Test short barcode handling
            result = process_barcode_automatically("123", "TEST_DEVICE")
            self.results.add_result("Short Barcode Handling", "invalid" in result.lower())
            
            # Test database error handling
            try:
                db = DatabaseManager()
                # Try to query non-existent table
                db.fetch_all("SELECT * FROM non_existent_table")
                self.results.add_result("Database Error Handling", False, "Should have raised exception")
            except Exception:
                self.results.add_result("Database Error Handling", True)
            
        except Exception as e:
            self.results.add_result("Error Handling", False, str(e))
    
    def test_performance(self):
        """Test system performance"""
        print("\n🚀 Testing Performance...")
        
        try:
            # Test rapid barcode processing
            test_device_id = "PERF_TEST_DEVICE"
            test_barcodes = [f"PERF{i:010d}" for i in range(10)]
            
            # Ensure device is registered
            db = DatabaseManager()
            db.execute_query(
                "INSERT OR REPLACE INTO device_registrations (device_id, registration_date, status) VALUES (?, ?, ?)",
                (test_device_id, datetime.now().isoformat(), "active")
            )
            
            start_time = time.time()
            
            with patch('src.barcode_scanner_app.check_ethernet_connection', return_value=False):
                for barcode in test_barcodes:
                    process_barcode_automatically(barcode, test_device_id)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Should process 10 barcodes in under 5 seconds
            self.results.add_result("Performance Test (10 barcodes)", processing_time < 5.0)
            
            print(f"  📊 Processed {len(test_barcodes)} barcodes in {processing_time:.2f} seconds")
            print(f"  📊 Average: {processing_time/len(test_barcodes):.3f} seconds per barcode")
            
            # Clean up performance test data
            for barcode in test_barcodes:
                db.execute_query("DELETE FROM barcode_scans WHERE barcode = ?", (barcode,))
            
        except Exception as e:
            self.results.add_result("Performance Test", False, str(e))
    
    def run_all_tests(self):
        """Run all automated tests"""
        print("🤖 Starting Automated Test Suite for Plug-and-Play Barcode Scanner")
        print("="*70)
        
        if not self.setup_test_environment():
            print("❌ Failed to setup test environment")
            return False
        
        try:
            # Run all test categories
            self.test_database_operations()
            self.test_connection_manager()
            self.test_device_id_generation()
            self.test_ethernet_detection()
            self.test_device_registration()
            self.test_barcode_processing()
            self.test_unsent_message_handling()
            self.test_concurrent_operations()
            self.test_error_handling()
            self.test_performance()
            
        finally:
            self.cleanup_test_environment()
        
        # Print final results
        success = self.results.print_summary()
        
        if success:
            print("\n🎉 All tests passed! System is ready for deployment.")
        else:
            print("\n⚠️ Some tests failed. Please review and fix issues before deployment.")
        
        return success

def main():
    """Main entry point for automated testing"""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Automated Test Suite for Plug-and-Play Barcode Scanner")
        print("Usage: python test_automation.py [options]")
        print("Options:")
        print("  --help    Show this help message")
        print("  (no args) Run all automated tests")
        return
    
    # Change to deployment package directory
    os.chdir("deployment_package")
    
    # Run automated tests
    test_suite = AutomatedTestSuite()
    success = test_suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
