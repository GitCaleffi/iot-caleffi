#!/usr/bin/env python3
"""
Test script to verify message sending when system is online
"""

import sys
import os
import time
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from utils.connection_manager import get_connection_manager
from database.local_storage import LocalStorage

# Override the Raspberry Pi detection to always return True for testing
class MockNetworkDiscovery:
    def discover_raspberry_pi_devices(self, use_nmap=False):
        return [{'ip': '192.168.1.100', 'mac': '00:11:22:33:44:55', 'hostname': 'test-pi'}]
    
    def test_raspberry_pi_connection(self, ip, port):
        return True

def test_online_send():
    print("🧪 Testing Online Message Sending...")
    
    # Get connection manager and inject mock
    cm = get_connection_manager()
    cm.network_discovery = MockNetworkDiscovery()
    
    # Force online state
    cm.is_connected_to_internet = True
    cm.is_connected_to_iot_hub = True
    cm.raspberry_pi_devices_available = True
    
    # Clear any existing unsent messages
    local_db = LocalStorage()
    unsent = local_db.get_unsent_scans()
    print(f"  • Found {len(unsent)} unsent messages to process")
    
    if not unsent:
        print("  • No unsent messages to test with. Add a test message first.")
        test_message = {
            'device_id': 'test-device-001',
            'barcode': '123456789012',
            'quantity': 1,
            'timestamp': int(time.time())
        }
        local_db.save_unsent_message(
            test_message['device_id'],
            test_message['barcode'],
            test_message['quantity'],
            test_message['timestamp']
        )
        print("  • Added test message for processing")
        unsent = local_db.get_unsent_scans()
    
    # Try to process unsent messages
    print("  • Attempting to process unsent messages...")
    success_count = cm._process_unsent_messages_background()
    
    if success_count > 0:
        print(f"  ✅ SUCCESS: Sent {success_count} messages to IoT Hub")
    else:
        print("  ❌ FAILED: No messages were sent to IoT Hub")
    
    # Print final status
    print("\n📊 Final Status:")
    status = cm.get_connection_status()
    print(f"  • Internet: {'✅' if status['internet_connected'] else '❌'}")
    print(f"  • IoT Hub: {'✅' if status['iot_hub_connected'] else '❌'}")
    print(f"  • Pi Available: {'✅' if cm.raspberry_pi_devices_available else '❌'}")
    print(f"  • Unsent Messages: {status['unsent_messages_count']}")

if __name__ == "__main__":
    test_online_send()
