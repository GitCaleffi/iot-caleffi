#!/usr/bin/env python3
"""
Test script for Raspberry Pi network discovery functionality
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.network_discovery import NetworkDiscovery
from src.barcode_scanner_app import discover_raspberry_pi_devices, get_primary_raspberry_pi_ip, auto_connect_to_raspberry_pi

def test_network_discovery():
    """Test the network discovery functionality"""
    print("🔍 Testing Raspberry Pi Network Discovery")
    print("=" * 50)
    
    # Test 1: Basic network discovery
    print("\n📡 Test 1: Basic Network Discovery")
    discovery = NetworkDiscovery()
    devices = discovery.discover_raspberry_pi_devices(use_nmap=False)  # Use ARP only for faster testing
    
    if devices:
        print(f"✅ Found {len(devices)} Raspberry Pi device(s):")
        for device in devices:
            print(f"  📱 {device['ip']} - {device['mac']} ({device.get('vendor', 'Raspberry Pi')})")
    else:
        print("❌ No Raspberry Pi devices found")
    
    # Test 2: Integrated barcode scanner app functions
    print("\n🔧 Test 2: Integrated App Functions")
    
    # Test discover function
    app_devices = discover_raspberry_pi_devices()
    print(f"App discovery found {len(app_devices)} devices")
    
    # Test primary IP selection
    primary_ip = get_primary_raspberry_pi_ip()
    if primary_ip:
        print(f"🎯 Primary Raspberry Pi IP: {primary_ip}")
    else:
        print("❌ No primary IP found")
    
    # Test auto-connection
    connection_result = auto_connect_to_raspberry_pi()
    print(f"🔗 Auto-connection result: {connection_result}")
    
    # Test 3: Network subnet detection
    print("\n🌐 Test 3: Network Information")
    subnet = discovery.get_local_subnet()
    print(f"Local subnet: {subnet}")
    
    # Test 4: Show all network devices (not just Raspberry Pi)
    print("\n📋 Test 4: All Network Devices")
    all_devices = discovery.discover_devices_arp()
    print(f"Total devices found via ARP: {len(all_devices)}")
    
    for device in all_devices[:5]:  # Show first 5 devices
        pi_indicator = "🍓" if device['is_raspberry_pi'] else "💻"
        print(f"  {pi_indicator} {device['ip']} - {device['mac']} ({device.get('hostname', 'Unknown')})")
    
    if len(all_devices) > 5:
        print(f"  ... and {len(all_devices) - 5} more devices")

def test_configuration_integration():
    """Test configuration file integration"""
    print("\n⚙️ Testing Configuration Integration")
    print("=" * 40)
    
    try:
        from utils.config import load_config
        config = load_config()
        
        if config and 'raspberry_pi' in config:
            pi_config = config['raspberry_pi']
            print("📄 Raspberry Pi configuration found:")
            
            if 'auto_discovered_ip' in pi_config:
                print(f"  🔍 Auto-discovered IP: {pi_config['auto_discovered_ip']}")
            
            if 'last_discovery' in pi_config:
                print(f"  🕒 Last discovery: {pi_config['last_discovery']}")
        else:
            print("❌ No Raspberry Pi configuration found")
            
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")

def main():
    """Main test function"""
    print("🧪 Raspberry Pi Network Discovery Test Suite")
    print("=" * 60)
    
    try:
        test_network_discovery()
        test_configuration_integration()
        
        print("\n✅ All tests completed!")
        print("\n💡 Usage Tips:")
        print("1. Install nmap for more accurate discovery: sudo apt-get install nmap")
        print("2. Ensure Raspberry Pi devices are on the same network subnet")
        print("3. Check that devices have SSH (port 22) or web services (port 5000) running")
        print("4. The system will automatically save discovered IPs to configuration")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
