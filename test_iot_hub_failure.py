#!/usr/bin/env python3
"""
Test IoT Hub connection failure detection
"""

import sys
import os
import socket

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def test_iot_hub_failure():
    """Test what happens when IoT Hub is unreachable"""
    
    print("🧪 Testing IoT Hub Connection Failure Detection")
    print("=" * 50)
    
    # Import connection manager
    from utils.connection_manager import ConnectionManager
    
    # Create connection manager
    connection_manager = ConnectionManager()
    
    print("📡 Testing current IoT Hub connectivity...")
    
    # Test IoT Hub connectivity directly
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("CaleffiIoT.azure-devices.net", 443))
        sock.close()
        
        if result == 0:
            print("✅ IoT Hub is currently reachable")
        else:
            print(f"❌ IoT Hub is unreachable - connection error {result}")
            
    except Exception as e:
        print(f"❌ IoT Hub test failed: {e}")
    
    # Test the enhanced connectivity check
    print("\n🔍 Testing enhanced connectivity check...")
    internet_status = connection_manager.check_internet_connectivity()
    iot_hub_status = connection_manager.check_iot_hub_connectivity()
    
    print(f"Internet connectivity: {'✅' if internet_status else '❌'}")
    print(f"IoT Hub connectivity: {'✅' if iot_hub_status else '❌'}")
    
    # Test the web interface function
    print("\n🌐 Testing web interface status generation...")
    from deployment_package.barcode_scanner_app import generate_registration_token
    
    try:
        status_message = generate_registration_token()
        
        print("\n📋 Web Interface Status:")
        print("-" * 30)
        # Extract just the Pi Status line
        for line in status_message.split('\n'):
            if 'Pi Status:' in line:
                print(line)
                break
        print("-" * 30)
        
        # Determine what should be shown based on connectivity
        if internet_status and iot_hub_status:
            expected = "Connected ✅"
        elif internet_status:
            expected = "Internet OK, IoT Hub Issues ⚠️"
        else:
            expected = "Disconnected ❌"
            
        print(f"\n💡 Expected status: {expected}")
        
        if expected in status_message:
            print("✅ Status is correctly detected!")
        else:
            print("❌ Status detection may have issues")
            
    except Exception as e:
        print(f"❌ Error testing web interface: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_iot_hub_failure()
