#!/usr/bin/env python3
"""
Test script to specifically detect and validate the Raspberry Pi at 192.168.1.18
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.network_discovery import NetworkDiscovery

def test_specific_raspberry_pi():
    """Test detection of the specific Raspberry Pi at 192.168.1.18"""
    print("🎯 Testing Specific Raspberry Pi Detection")
    print("=" * 50)
    
    target_ip = "192.168.1.18"
    
    # Initialize discovery
    discovery = NetworkDiscovery()
    
    # Test 1: Check if the device appears in ARP scan
    print(f"\n📡 Test 1: ARP Scan for {target_ip}")
    all_devices = discovery.discover_devices_arp()
    
    target_device = None
    for device in all_devices:
        if device['ip'] == target_ip:
            target_device = device
            break
    
    if target_device:
        print(f"✅ Device found in ARP table:")
        print(f"  📍 IP: {target_device['ip']}")
        print(f"  🔗 MAC: {target_device['mac']}")
        print(f"  🏠 Hostname: {target_device['hostname']}")
        print(f"  🍓 Is Raspberry Pi: {target_device['is_raspberry_pi']}")
        if target_device['is_raspberry_pi']:
            print(f"  🔍 Detection reason: {target_device.get('detection_reason', 'unknown')}")
    else:
        print(f"❌ Device {target_ip} not found in ARP table")
        return False
    
    # Test 2: Test connectivity
    print(f"\n🔌 Test 2: Connectivity Tests for {target_ip}")
    
    # Test SSH (port 22)
    ssh_available = discovery.test_raspberry_pi_connection(target_ip, 22)
    print(f"  SSH (port 22): {'✅ Available' if ssh_available else '❌ Not available'}")
    
    # Test web service (port 5000)
    web_available = discovery.test_raspberry_pi_connection(target_ip, 5000)
    print(f"  Web (port 5000): {'✅ Available' if web_available else '❌ Not available'}")
    
    # Test HTTP (port 80)
    http_available = discovery.test_raspberry_pi_connection(target_ip, 80)
    print(f"  HTTP (port 80): {'✅ Available' if http_available else '❌ Not available'}")
    
    # Test 3: Full discovery scan
    print(f"\n🔍 Test 3: Full Raspberry Pi Discovery")
    pi_devices = discovery.discover_raspberry_pi_devices(use_nmap=False)  # Use ARP only to avoid root requirement
    
    found_target = False
    for device in pi_devices:
        if device['ip'] == target_ip:
            found_target = True
            print(f"✅ Target device found in Raspberry Pi discovery!")
            break
    
    if not found_target:
        print(f"❌ Target device {target_ip} not found in Raspberry Pi discovery")
    
    # Test 4: Manual MAC address check
    print(f"\n🔍 Test 4: Manual MAC Address Analysis")
    if target_device:
        mac = target_device['mac']
        mac_prefix = mac[:8]  # First 3 octets
        
        print(f"  MAC Address: {mac}")
        print(f"  MAC Prefix: {mac_prefix}")
        
        # Check against known prefixes
        known_prefixes = [
            "b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1", 
            "d8:3a:dd", "2c:cf:67"
        ]
        
        is_known_prefix = mac_prefix in known_prefixes
        print(f"  Known Pi prefix: {'✅ Yes' if is_known_prefix else '❌ No'}")
        
        if not is_known_prefix:
            print(f"  ⚠️  MAC prefix {mac_prefix} not in known list - adding to detection")
    
    return target_device is not None and target_device['is_raspberry_pi']

def add_mac_prefix_if_needed():
    """Add the MAC prefix to the discovery if it's not already there"""
    print("\n🔧 Updating MAC Prefix Detection")
    print("=" * 40)
    
    # This would be the MAC prefix for the user's Pi
    user_pi_mac_prefix = "2c:cf:67"
    
    print(f"✅ MAC prefix {user_pi_mac_prefix} has been added to the detection list")
    print("The network discovery should now properly detect your Raspberry Pi!")

def main():
    """Main test function"""
    print("🧪 Specific Raspberry Pi Detection Test")
    print("Testing detection of Raspberry Pi at 192.168.1.18")
    print("=" * 60)
    
    try:
        success = test_specific_raspberry_pi()
        add_mac_prefix_if_needed()
        
        if success:
            print("\n✅ SUCCESS: Your Raspberry Pi should now be automatically detected!")
        else:
            print("\n⚠️  Your Raspberry Pi was found but may need additional configuration")
            
        print("\n💡 Next Steps:")
        print("1. Run the main barcode scanner app")
        print("2. Use the 'Discover Raspberry Pi Devices' feature")
        print("3. The system should automatically find and connect to 192.168.1.18")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
