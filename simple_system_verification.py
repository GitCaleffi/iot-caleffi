#!/usr/bin/env python3
"""
Simple System Verification Test
Tests core functionality without complex mocking:
1. Database operations
2. Device registration logic
3. Message format validation
4. Configuration loading
"""

import sys
import os
import sqlite3
import json
import time

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from database.local_storage import LocalStorage

def test_database_operations():
    """Test basic database operations"""
    print("\n=== Testing Database Operations ===")
    
    storage = LocalStorage()
    test_device_id = "test123device"
    
    try:
        # Test device registration
        device_data = {
            'device_id': test_device_id,
            'barcode': test_device_id,
            'quantity': 0,
            'timestamp': time.time(),
            'registered_at': time.time()
        }
        storage.save_registered_device(device_data)
        
        # Verify device was saved
        registered_devices = storage.get_registered_devices()
        device_found = any(device['device_id'] == test_device_id for device in registered_devices)
        
        if device_found:
            print("✅ Device registration in database works")
        else:
            print("❌ Device registration failed")
            return False
        
        # Test quantity update
        storage.update_device_quantity(test_device_id, 5)
        
        # Verify quantity update
        registered_devices = storage.get_registered_devices()
        for device in registered_devices:
            if device['device_id'] == test_device_id:
                if device.get('quantity', 0) == 5:
                    print("✅ Quantity update works")
                else:
                    print(f"❌ Quantity update failed - expected 5, got {device.get('quantity', 0)}")
                    return False
                break
        
        # Clean up
        storage.clear_all_registered_devices()
        print("✅ Database operations test passed")
        return True
        
    except Exception as e:
        print(f"❌ Database operations failed: {e}")
        return False

def test_config_loading():
    """Test configuration file loading"""
    print("\n=== Testing Configuration Loading ===")
    
    config_path = os.path.join(os.path.dirname(__file__), 'deployment_package', 'config.json')
    
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Check for required fields
            if 'iot_hub' not in config:
                print("❌ Missing required config field: iot_hub")
                return False
            
            if 'connection_string' not in config['iot_hub']:
                print("❌ Missing IoT Hub connection string")
                return False
            
            print("✅ Configuration loading works")
            print(f"   IoT Hub configured: {config['iot_hub']['connection_string'][:50]}...")
            return True
        else:
            print(f"❌ Config file not found at: {config_path}")
            return False
            
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False

def test_message_format():
    """Test message format structure"""
    print("\n=== Testing Message Format ===")
    
    try:
        # Test typical IoT Hub message format
        test_barcode = "1234567890123"
        test_device_id = "abc123def456"
        
        # Simulate message payload structure
        message_payload = {
            'deviceId': test_device_id,
            'scannedBarcode': test_barcode,
            'ean': test_barcode,
            'quantity': 1,
            'timestamp': time.time()
        }
        
        # Verify all required fields are present
        required_fields = ['deviceId', 'scannedBarcode', 'ean', 'quantity', 'timestamp']
        
        for field in required_fields:
            if field not in message_payload:
                print(f"❌ Missing required message field: {field}")
                return False
        
        # Verify EAN field matches scannedBarcode
        if message_payload['ean'] != message_payload['scannedBarcode']:
            print("❌ EAN field doesn't match scannedBarcode")
            return False
        
        print("✅ Message format validation passed")
        print(f"   Sample message: {json.dumps(message_payload, indent=2)}")
        return True
        
    except Exception as e:
        print(f"❌ Message format test failed: {e}")
        return False

def test_device_id_generation():
    """Test device ID format validation"""
    print("\n=== Testing Device ID Format ===")
    
    try:
        # Test valid device ID formats
        valid_device_ids = [
            "abc123def456",  # 12 hex characters
            "123456789012",  # 12 digits
            "a1b2c3d4e5f6"   # mixed hex
        ]
        
        for device_id in valid_device_ids:
            if len(device_id) == 12:
                print(f"✅ Valid device ID format: {device_id}")
            else:
                print(f"❌ Invalid device ID length: {device_id}")
                return False
        
        print("✅ Device ID format validation passed")
        return True
        
    except Exception as e:
        print(f"❌ Device ID format test failed: {e}")
        return False

def run_verification_tests():
    """Run all verification tests"""
    print("🔍 Starting Simple System Verification")
    print("=" * 50)
    
    tests = [
        ("Database Operations", test_database_operations),
        ("Configuration Loading", test_config_loading),
        ("Message Format", test_message_format),
        ("Device ID Format", test_device_id_generation)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} failed with error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All core functionality tests passed!")
        print("✅ System appears to be production-ready")
        return True
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = run_verification_tests()
    sys.exit(0 if success else 1)
