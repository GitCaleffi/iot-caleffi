#!/usr/bin/env python3
"""
Test script to simulate and verify offline mode behavior
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from utils.connection_manager import ConnectionManager
from database.local_storage import LocalStorage
import time

class OfflineSimulator:
    """Simulate offline conditions for testing"""
    
    def __init__(self):
        self.connection_manager = get_connection_manager()
        self.local_db = LocalStorage()
        
    def force_offline_mode(self):
        """Force the connection manager into offline mode"""
        print("🔴 Forcing offline mode...")
        
        # Override connection status to simulate offline
        self.connection_manager.is_connected_to_internet = False
        self.connection_manager.is_connected_to_iot_hub = False
        
        print("  • Internet status: OFFLINE")
        print("  • IoT Hub status: OFFLINE")
        
    def force_online_mode(self):
        """Force the connection manager back to online mode"""
        print("🟢 Forcing online mode...")
        
        # Reset connection status
        self.connection_manager.is_connected_to_internet = True
        self.connection_manager.is_connected_to_iot_hub = True
        self.connection_manager.last_connection_check = 0  # Force recheck
        
        print("  • Internet status: ONLINE")
        print("  • IoT Hub status: ONLINE")
        
    def test_offline_message_handling(self):
        """Test message handling in offline mode"""
        print("\n🧪 Testing Offline Message Handling...")
        
        # Get initial unsent count
        initial_unsent = self.local_db.get_unsent_scans()
        initial_count = len(initial_unsent) if initial_unsent else 0
        print(f"  • Initial unsent messages: {initial_count}")
        
        # Force offline mode
        self.force_offline_mode()
        
        # Try to send a message
        test_device_id = "test-offline-device"
        test_barcode = "9876543210987"
        
        success, status_msg = self.connection_manager.send_message_with_retry(
            test_device_id, test_barcode, 1, "offline_test"
        )
        
        print(f"  • Message send result: {'✅ SENT' if success else '📱 QUEUED'}")
        print(f"  • Status message: {status_msg}")
        
        # Check if message was saved locally
        after_unsent = self.local_db.get_unsent_scans()
        after_count = len(after_unsent) if after_unsent else 0
        print(f"  • Unsent messages after offline test: {after_count}")
        
        if after_count > initial_count:
            print("  ✅ SUCCESS: Message was saved locally when offline")
            return True
        else:
            print("  ❌ FAILURE: Message was NOT saved locally when offline")
            return False
            
    def test_online_message_handling(self):
        """Test message handling in online mode"""
        print("\n🧪 Testing Online Message Handling...")
        
        # Force online mode
        self.force_online_mode()
        
        # Try to send a message
        test_device_id = "test-online-device"
        test_barcode = "1111222233334"
        
        success, status_msg = self.connection_manager.send_message_with_retry(
            test_device_id, test_barcode, 1, "online_test"
        )
        
        print(f"  • Message send result: {'✅ SENT' if success else '📱 QUEUED'}")
        print(f"  • Status message: {status_msg}")
        
        if success:
            print("  ✅ SUCCESS: Message was sent to IoT Hub when online")
            return True
        else:
            print("  ❌ FAILURE: Message was NOT sent to IoT Hub when online")
            return False

def main():
    print("=" * 60)
    print("🧪 OFFLINE/ONLINE MODE SIMULATION TEST")
    print("=" * 60)
    
    simulator = OfflineSimulator()
    
    # Test 1: Offline message handling
    offline_success = simulator.test_offline_message_handling()
    
    # Wait a moment
    time.sleep(2)
    
    # Test 2: Online message handling
    online_success = simulator.test_online_message_handling()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SIMULATION TEST RESULTS")
    print("=" * 60)
    print(f"Offline Mode Test:    {'✅ PASS' if offline_success else '❌ FAIL'}")
    print(f"Online Mode Test:     {'✅ PASS' if online_success else '❌ FAIL'}")
    
    if offline_success and online_success:
        print("\n🟢 ALL TESTS PASSED - Offline/Online logic working correctly")
    else:
        print("\n🔴 SOME TESTS FAILED - Offline/Online logic needs fixing")
        
    # Show current connection status
    connection_manager = get_connection_manager()
    status = connection_manager.get_connection_status()
    print(f"\nFinal Connection Status:")
    for key, value in status.items():
        print(f"  • {key}: {value}")

if __name__ == "__main__":
    main()
