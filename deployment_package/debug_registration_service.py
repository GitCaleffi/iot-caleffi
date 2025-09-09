#!/usr/bin/env python3
"""
Debug the dynamic registration service to understand why IoT Hub registration is failing
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logging
from barcode_scanner_app import get_dynamic_registration_service

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def debug_registration_service():
    """Debug dynamic registration service"""
    
    print("🔍 Debugging Dynamic Registration Service")
    print("=" * 60)
    
    try:
        # Get the registration service
        registration_service = get_dynamic_registration_service()
        
        if registration_service:
            print("✅ Dynamic registration service obtained")
            print(f"📊 Registry manager status: {registration_service.registry_manager is not None}")
            
            # Test device registration
            test_device_id = "b2fa27f0e5a1"
            print(f"\n🧪 Testing device registration for: {test_device_id}")
            
            # Try to register device
            connection_string = registration_service.register_device_with_azure(test_device_id)
            
            if connection_string:
                print("✅ Device registration successful")
                print(f"📱 Connection string: {connection_string[:50]}...")
                
                # Test getting connection string
                retrieved_conn_str = registration_service.get_device_connection_string(test_device_id)
                print(f"📱 Retrieved connection string: {retrieved_conn_str[:50] if retrieved_conn_str else 'None'}...")
                
            else:
                print("❌ Device registration failed")
                
        else:
            print("❌ Failed to get dynamic registration service")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_registration_service()
