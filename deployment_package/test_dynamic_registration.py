#!/usr/bin/env python3
"""
Test the dynamic registration service to reproduce the IoTHubRegistryManager error
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logging
from utils.dynamic_registration_service import DynamicRegistrationService
from utils.config import load_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_dynamic_registration():
    """Test dynamic registration service initialization"""
    
    print("🧪 Testing Dynamic Registration Service")
    print("=" * 60)
    
    try:
        # Load config and initialize the service
        config = load_config()
        service = DynamicRegistrationService(config)
        
        if service.registry_manager:
            print("✅ Dynamic Registration Service initialized successfully")
            
            # Test device registration
            test_device_id = "test-device-" + str(int(time.time()))
            print(f"🔍 Testing device registration for: {test_device_id}")
            
            connection_string = service.register_device_with_azure(test_device_id)
            
            if connection_string:
                print("✅ Device registration successful")
                print(f"📱 Connection string: {connection_string[:50]}...")
            else:
                print("❌ Device registration failed")
                
        else:
            print("❌ Dynamic Registration Service failed to initialize")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import time
    test_dynamic_registration()
