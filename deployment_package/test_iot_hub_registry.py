#!/usr/bin/env python3
"""
Test Azure IoT Hub Registry Manager initialization to debug the from_connection_string issue
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

import logging
from utils.config import load_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def test_registry_manager():
    """Test IoT Hub Registry Manager initialization"""
    
    print("🧪 Testing Azure IoT Hub Registry Manager initialization")
    print("=" * 60)
    
    try:
        # Load config to get connection string
        config = load_config()
        connection_string = config.get('iot_hub', {}).get('connection_string')
        
        if not connection_string:
            print("❌ No IoT Hub connection string found in config")
            return
            
        print(f"✅ Connection string loaded: {connection_string[:50]}...")
        
        # Test direct import and usage
        print("\n🔍 Testing direct import...")
        from azure.iot.hub import IoTHubRegistryManager
        print("✅ Import successful")
        
        # Check if method exists
        print(f"✅ from_connection_string method exists: {hasattr(IoTHubRegistryManager, 'from_connection_string')}")
        
        # Test method call
        print("\n🔍 Testing method call...")
        registry_manager = IoTHubRegistryManager.from_connection_string(connection_string)
        print("✅ Registry Manager created successfully")
        
        # Test connection
        print("\n🔍 Testing connection...")
        devices = registry_manager.get_devices(max_number_of_devices=1)
        print(f"✅ Connection test successful - found {len(list(devices))} devices")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_registry_manager()
