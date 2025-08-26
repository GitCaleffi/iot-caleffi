#!/usr/bin/env python3
"""
Test script for IoT Hub-based Pi detection
Tests both Device Twin reported properties and connection state methods
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from utils.iot_hub_pi_detection import IoTHubPiDetection
from utils.config import load_config

def test_iot_hub_pi_detection():
    """Test IoT Hub Pi detection functionality"""
    print("🧪 Testing IoT Hub-based Pi Detection System")
    print("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        iot_hub_config = config.get("iot_hub", {})
        owner_connection_string = iot_hub_config.get("connection_string")
        
        if not owner_connection_string:
            print("❌ No IoT Hub owner connection string found in config.json")
            print("💡 Please add your IoT Hub owner connection string to config.json")
            return False
        
        print(f"✅ Found IoT Hub connection string in config")
        
        # Initialize IoT Hub Pi detection
        pi_detection = IoTHubPiDetection(owner_connection_string)
        
        # Test device IDs (add your actual Pi device IDs here)
        test_device_ids = [
            "pi-5284d8ff",
            "live-server-pi", 
            "raspberry-pi-main"
        ]
        
        print(f"\n🔍 Testing Pi detection for devices: {test_device_ids}")
        print("-" * 40)
        
        # Test individual device connection states
        print("\n1️⃣ Testing Device Connection States:")
        for device_id in test_device_ids:
            is_connected, message = pi_detection.check_device_connection_state(device_id)
            status_icon = "✅" if is_connected else "❌"
            print(f"   {status_icon} {device_id}: {message}")
        
        # Test individual device twin status
        print("\n2️⃣ Testing Device Twin Reported Properties:")
        for device_id in test_device_ids:
            is_online, twin_info = pi_detection.check_device_twin_status(device_id)
            status_icon = "✅" if is_online else "❌"
            print(f"   {status_icon} {device_id}:")
            print(f"      Status: {twin_info.get('status', 'unknown')}")
            print(f"      Last seen: {twin_info.get('last_seen', 'unknown')}")
            if 'age_minutes' in twin_info:
                print(f"      Age: {twin_info['age_minutes']:.1f} minutes")
            if 'device_info' in twin_info:
                device_info = twin_info['device_info']
                if device_info.get('ip_address'):
                    print(f"      IP: {device_info['ip_address']}")
                if device_info.get('hostname'):
                    print(f"      Hostname: {device_info['hostname']}")
        
        # Test overall Pi availability
        print("\n3️⃣ Testing Overall Pi Availability:")
        any_available, detailed_status = pi_detection.check_pi_availability(test_device_ids)
        
        if any_available:
            print("✅ Pi devices are available!")
            available_devices = detailed_status["summary"]["available_devices"]
            print(f"   Available devices: {available_devices}")
        else:
            print("❌ No Pi devices are currently available")
        
        print(f"\n📊 Summary:")
        summary = detailed_status["summary"]
        print(f"   Total devices checked: {summary['total_devices']}")
        print(f"   Connected devices: {summary['connected_devices']}")
        print(f"   Online devices: {summary['online_devices']}")
        print(f"   Available devices: {len(summary['available_devices'])}")
        
        # Test IP address retrieval
        print("\n4️⃣ Testing IP Address Retrieval from Device Twin:")
        for device_id in test_device_ids:
            ip_address = pi_detection.get_device_ip_from_twin(device_id)
            if ip_address:
                print(f"   ✅ {device_id}: {ip_address}")
            else:
                print(f"   ❌ {device_id}: No IP address available")
        
        print("\n" + "=" * 50)
        print("🎉 IoT Hub Pi detection test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_iot_hub_pi_detection()
    sys.exit(0 if success else 1)
