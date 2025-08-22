#!/usr/bin/env python3
"""
Test script to verify offline/online connection detection logic
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from utils.connection_manager import get_connection_manager
import subprocess
import time

def test_internet_connectivity():
    """Test basic internet connectivity"""
    print("🔍 Testing Internet Connectivity...")
    
    # Method 1: Direct ping test
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
            capture_output=True, 
            timeout=5
        )
        internet_via_ping = result.returncode == 0
        print(f"  • Ping Google DNS (8.8.8.8): {'✅ Connected' if internet_via_ping else '❌ Failed'}")
    except Exception as e:
        internet_via_ping = False
        print(f"  • Ping Google DNS (8.8.8.8): ❌ Error - {e}")
    
    # Method 2: Connection Manager test
    connection_manager = get_connection_manager()
    internet_via_manager = connection_manager.check_internet_connectivity()
    print(f"  • Connection Manager: {'✅ Connected' if internet_via_manager else '❌ Failed'}")
    
    return internet_via_ping, internet_via_manager

def test_iot_hub_connectivity():
    """Test IoT Hub connectivity"""
    print("\n🔍 Testing IoT Hub Connectivity...")
    
    connection_manager = get_connection_manager()
    iot_hub_connected = connection_manager.check_iot_hub_connectivity()
    print(f"  • IoT Hub Connection: {'✅ Connected' if iot_hub_connected else '❌ Failed'}")
    
    return iot_hub_connected

def test_message_sending():
    """Test message sending logic"""
    print("\n🔍 Testing Message Sending Logic...")
    
    connection_manager = get_connection_manager()
    
    # Test with a dummy barcode
    test_device_id = "test-device-offline-check"
    test_barcode = "1234567890123"
    
    success, status_msg = connection_manager.send_message_with_retry(
        test_device_id, test_barcode, 1, "test_message"
    )
    
    print(f"  • Message Send Result: {'✅ Sent' if success else '❌ Failed/Queued'}")
    print(f"  • Status Message: {status_msg}")
    
    return success, status_msg

def test_offline_simulation():
    """Simulate offline condition by blocking network"""
    print("\n🔍 Simulating Offline Condition...")
    print("  ⚠️  To properly test offline mode, disconnect your network or block IoT Hub access")
    print("  ⚠️  Then run this test again to verify messages are saved locally")

def main():
    print("=" * 60)
    print("🧪 CONNECTION LOGIC TEST SUITE")
    print("=" * 60)
    
    # Test 1: Internet connectivity
    internet_ping, internet_manager = test_internet_connectivity()
    
    # Test 2: IoT Hub connectivity  
    iot_hub_connected = test_iot_hub_connectivity()
    
    # Test 3: Message sending
    message_success, message_status = test_message_sending()
    
    # Test 4: Offline simulation info
    test_offline_simulation()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    print(f"Internet (Ping):           {'✅ PASS' if internet_ping else '❌ FAIL'}")
    print(f"Internet (Manager):        {'✅ PASS' if internet_manager else '❌ FAIL'}")
    print(f"IoT Hub Connection:        {'✅ PASS' if iot_hub_connected else '❌ FAIL'}")
    print(f"Message Sending:           {'✅ SENT' if message_success else '📱 QUEUED'}")
    print(f"Message Status:            {message_status}")
    
    # Check for issues
    if internet_ping and internet_manager and iot_hub_connected and message_success:
        print("\n🟢 ALL SYSTEMS ONLINE - Messages will be sent to IoT Hub")
    elif not internet_ping or not internet_manager:
        print("\n🔴 INTERNET OFFLINE - Messages should be saved locally")
    elif not iot_hub_connected:
        print("\n🟡 IOT HUB OFFLINE - Messages should be saved locally")
    else:
        print("\n🟠 MIXED STATE - Check connection logic")
    
    # Get connection status
    connection_manager = get_connection_manager()
    status = connection_manager.get_connection_status()
    print(f"\nConnection Status Details:")
    for key, value in status.items():
        print(f"  • {key}: {value}")

if __name__ == "__main__":
    main()
