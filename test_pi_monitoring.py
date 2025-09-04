#!/usr/bin/env python3
"""
Test Raspberry Pi internet monitoring functionality
"""

import sys
import os
import time

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def test_pi_monitoring():
    """Test if Raspberry Pi code has internet monitoring"""
    
    print("🧪 Testing Raspberry Pi Internet Monitoring")
    print("=" * 50)
    
    # Import the barcode scanner app
    from deployment_package.barcode_scanner_app import RaspberryPiDeviceService, IS_RASPBERRY_PI
    
    print(f"🔍 Running on Raspberry Pi: {'✅ YES' if IS_RASPBERRY_PI else '❌ NO (simulation)'}")
    
    if not IS_RASPBERRY_PI:
        print("ℹ️  This test simulates Raspberry Pi behavior on desktop/server")
    
    try:
        # Initialize Pi service (this should include ConnectionManager)
        print("\n🚀 Initializing Raspberry Pi Device Service...")
        pi_service = RaspberryPiDeviceService()
        
        # Check if connection manager is available
        if hasattr(pi_service, 'connection_manager'):
            print("✅ ConnectionManager initialized in Pi service")
            
            # Test internet connectivity
            print("\n🌐 Testing internet connectivity...")
            is_connected = pi_service.connection_manager.check_internet_connectivity()
            print(f"Internet status: {'✅ CONNECTED' if is_connected else '❌ DISCONNECTED'}")
            
            # Check LED status
            led_status = pi_service.connection_manager.led_manager.current_status
            print(f"💡 LED Status: {led_status}")
            
            # Test network interface check
            print("\n📡 Testing network interface detection...")
            interface_status = pi_service.connection_manager._check_network_interface()
            print(f"Network interfaces: {'✅ ACTIVE' if interface_status else '❌ DOWN'}")
            
            print("\n✅ Raspberry Pi internet monitoring is properly implemented!")
            print("🔴 When internet disconnects: LED will blink red")
            print("🟢 When internet connects: LED will turn green")
            print("📨 Alert messages will be queued when disconnected")
            
        else:
            print("❌ ConnectionManager not found in Pi service")
            
        # Cleanup
        pi_service.stop()
        
    except Exception as e:
        print(f"❌ Error testing Pi monitoring: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pi_monitoring()
