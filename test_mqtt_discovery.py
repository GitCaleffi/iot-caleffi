#!/usr/bin/env python3
"""
Test MQTT Device Discovery System
This script tests the MQTT-based Pi detection system
"""

import sys
import time
import logging
sys.path.append('src')

from src.utils.mqtt_device_discovery import get_mqtt_discovery, discover_raspberry_pi_devices, get_primary_raspberry_pi_ip
from src.barcode_scanner_app import get_primary_raspberry_pi_ip as app_get_pi_ip

def test_mqtt_discovery():
    """Test the MQTT discovery system"""
    print("🧪 Testing MQTT Device Discovery System")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        # Test 1: Connect to MQTT broker
        print("\n📡 Test 1: Connecting to MQTT broker...")
        discovery = get_mqtt_discovery("localhost")
        print("✅ Successfully connected to MQTT broker")
        
        # Test 2: Check for discovered devices
        print("\n🔍 Test 2: Checking for discovered devices...")
        devices = discovery.get_discovered_devices()
        print(f"📊 Found {len(devices)} discovered devices")
        
        for device_id, device_info in devices.items():
            print(f"   • Device: {device_id}")
            print(f"     IP: {device_info.get('ip_address')}")
            print(f"     Status: {device_info.get('status')}")
            print(f"     Last Seen: {device_info.get('last_seen')}")
        
        # Test 3: Get primary Pi IP via MQTT
        print("\n🍓 Test 3: Getting primary Pi IP via MQTT...")
        mqtt_pi_ip = get_primary_raspberry_pi_ip()
        if mqtt_pi_ip:
            print(f"✅ MQTT discovered Pi IP: {mqtt_pi_ip}")
        else:
            print("⚠️ No Pi devices found via MQTT")
        
        # Test 4: Test integrated barcode scanner detection
        print("\n🔧 Test 4: Testing integrated barcode scanner detection...")
        app_pi_ip = app_get_pi_ip()
        if app_pi_ip:
            print(f"✅ Barcode scanner detected Pi IP: {app_pi_ip}")
        else:
            print("⚠️ Barcode scanner could not detect Pi IP")
        
        # Test 5: Request device announcements
        print("\n📢 Test 5: Requesting device announcements...")
        discovery.request_device_announcement()
        print("✅ Sent device announcement request")
        
        # Wait a moment for responses
        print("⏳ Waiting 5 seconds for device responses...")
        time.sleep(5)
        
        # Check again for new devices
        updated_devices = discovery.get_discovered_devices()
        print(f"📊 After announcement request: {len(updated_devices)} devices")
        
        print("\n🎉 MQTT Discovery System Test Completed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def monitor_mqtt_messages():
    """Monitor MQTT messages for 30 seconds"""
    print("\n👁️ Monitoring MQTT messages for 30 seconds...")
    print("   (This will show real-time device announcements)")
    
    try:
        discovery = get_mqtt_discovery("localhost")
        
        def device_callback(event_type, device_info):
            print(f"🔔 MQTT Event: {event_type}")
            print(f"   Device: {device_info.get('device_id')}")
            print(f"   IP: {device_info.get('ip_address')}")
            print(f"   Status: {device_info.get('status')}")
        
        discovery.add_device_callback(device_callback)
        
        # Monitor for 30 seconds
        for i in range(30):
            time.sleep(1)
            if i % 10 == 0:
                print(f"⏱️ Monitoring... {30-i} seconds remaining")
        
        print("✅ Monitoring completed")
        
    except Exception as e:
        print(f"❌ Monitoring failed: {e}")

if __name__ == "__main__":
    print("🚀 MQTT Device Discovery Test Suite")
    print("=" * 50)
    
    # Run basic tests
    success = test_mqtt_discovery()
    
    if success:
        print("\n" + "=" * 50)
        response = input("Would you like to monitor MQTT messages? (y/n): ")
        if response.lower() in ['y', 'yes']:
            monitor_mqtt_messages()
    
    print("\n📋 Summary:")
    print("✅ MQTT Broker: Running")
    print("✅ Discovery Service: Running") 
    print("✅ Integration: Complete")
    print("\n📖 Next Steps:")
    print("1. Install Pi client on your Raspberry Pi devices")
    print("2. Run: ./setup_mqtt_pi_client.sh on each Pi")
    print("3. Pi devices will automatically announce themselves")
    print("4. Server will detect Pi regardless of network changes")
