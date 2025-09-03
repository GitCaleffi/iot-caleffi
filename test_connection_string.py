#!/usr/bin/env python3
"""
Test script to verify IoT Hub connection string functionality
"""

import sys
import json
import base64
import logging
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'deployment_package' / 'src'
sys.path.append(str(src_dir))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_connection_string_format(connection_string):
    """Test if connection string has valid format"""
    logger.info("🔍 Testing connection string format...")
    
    try:
        # Parse connection string
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        
        # Check required parts
        required_parts = ['HostName', 'SharedAccessKeyName', 'SharedAccessKey']
        missing_parts = [part for part in required_parts if part not in parts]
        
        if missing_parts:
            logger.error(f"❌ Missing required parts: {missing_parts}")
            return False
        
        logger.info(f"✅ HostName: {parts['HostName']}")
        logger.info(f"✅ SharedAccessKeyName: {parts['SharedAccessKeyName']}")
        
        # Test base64 decoding of SharedAccessKey
        try:
            key = parts['SharedAccessKey']
            logger.info(f"🔑 SharedAccessKey length: {len(key)} characters")
            
            # Try to decode base64
            decoded = base64.b64decode(key)
            logger.info(f"✅ Base64 decoding successful: {len(decoded)} bytes")
            
        except Exception as e:
            logger.error(f"❌ Base64 decoding failed: {e}")
            return False
        
        logger.info("✅ Connection string format is valid")
        return True
        
    except Exception as e:
        logger.error(f"❌ Connection string parsing failed: {e}")
        return False

def test_azure_iot_hub_connection(connection_string):
    """Test actual connection to Azure IoT Hub"""
    logger.info("🔗 Testing Azure IoT Hub connection...")
    
    try:
        from azure.iot.hub import IoTHubRegistryManager
        
        # Initialize registry manager
        registry_manager = IoTHubRegistryManager(connection_string)
        
        # Try to get device statistics (lightweight operation)
        stats = registry_manager.get_service_statistics()
        logger.info(f"✅ IoT Hub connection successful!")
        logger.info(f"📊 Connected devices: {stats.connected_device_count}")
        logger.info(f"📊 Total devices: {stats.total_device_count}")
        
        return True
        
    except ImportError:
        logger.warning("⚠️ Azure IoT Hub SDK not installed. Install with: pip install azure-iot-hub")
        return None
    except Exception as e:
        logger.error(f"❌ IoT Hub connection failed: {e}")
        return False

def test_device_registration(connection_string):
    """Test device registration functionality"""
    logger.info("🔧 Testing device registration...")
    
    try:
        from utils.dynamic_registration_service import DynamicRegistrationService
        
        # Initialize registration service
        config = {"iot_hub": {"connection_string": connection_string}}
        registration_service = DynamicRegistrationService(config)
        
        # Test device registration
        test_device_id = "test-connection-device"
        device_connection_string = registration_service.register_device_with_azure(test_device_id)
        
        if device_connection_string:
            logger.info(f"✅ Device registration successful for: {test_device_id}")
            logger.info(f"🔗 Device connection string generated")
            return True
        else:
            logger.error("❌ Device registration failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Device registration test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting IoT Hub connection string test...")
    
    # Load connection string from config
    try:
        config_path = current_dir / 'deployment_package' / 'src' / 'config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        connection_string = config['iot_hub']['connection_string']
        logger.info(f"📄 Loaded connection string from: {config_path}")
        
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
        return
    
    # Run tests
    tests = [
        ("Connection String Format", lambda: test_connection_string_format(connection_string)),
        ("Azure IoT Hub Connection", lambda: test_azure_iot_hub_connection(connection_string)),
        ("Device Registration", lambda: test_device_registration(connection_string))
    ]
    
    results = {}
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running test: {test_name}")
        logger.info(f"{'='*50}")
        
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"❌ Test {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("📊 TEST SUMMARY")
    logger.info(f"{'='*50}")
    
    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️ SKIP"
        
        logger.info(f"{status} {test_name}")
    
    # Overall result
    passed_tests = sum(1 for r in results.values() if r is True)
    total_tests = len([r for r in results.values() if r is not None])
    
    if passed_tests == total_tests:
        logger.info("\n🎉 ALL TESTS PASSED! Connection string is working correctly.")
    else:
        logger.info(f"\n⚠️ {passed_tests}/{total_tests} tests passed. Some issues detected.")

if __name__ == "__main__":
    main()
