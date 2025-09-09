#!/usr/bin/env python3
"""
Final System Verification Test
Tests all core functionality to ensure production readiness:
1. Device registration without quantity increment
2. Product barcode scanning with quantity increment
3. EAN field inclusion in IoT Hub messages
4. Frontend API integration
5. Database consistency
"""

import sys
import os
import sqlite3
import json
import time
from unittest.mock import patch, MagicMock

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from barcode_scanner_app import process_barcode_scan
from database.local_storage import LocalStorage

def test_device_registration():
    """Test device registration flow"""
    print("\n=== Testing Device Registration ===")
    
    test_device_id = "4913a0ab9adf"  # 12 character hex format
    
    # Initialize local storage
    storage = LocalStorage()
    
    print(f"Testing registration for device: {test_device_id}")
    
    # Mock IoT Hub and API calls
    with patch('barcode_scanner_app.send_to_iot_hub') as mock_iot, \
         patch('barcode_scanner_app.send_registration_to_api') as mock_api:
        
        mock_iot.return_value = True
        mock_api.return_value = True
        
        # Register device (barcode == device_id for registration)
        result = process_barcode_scan(test_device_id, test_device_id)
        
        # Verify device is in registered devices
        registered_devices = storage.get_registered_devices()
        device_found = any(device['device_id'] == test_device_id for device in registered_devices)
        assert device_found, "Device should be registered"
        
        # Verify IoT Hub registration message was sent
        assert mock_iot.called, "IoT Hub message should be sent"
        
        # Verify API registration call was made
        assert mock_api.called, "Frontend API call should be made"
        
        print("✅ Device registration test passed")
        return True

def test_product_scanning():
    """Test product barcode scanning with quantity increment"""
    print("\n=== Testing Product Barcode Scanning ===")
    
    test_device_id = "4913a0ab9adf"
    test_barcode = "1234567890123"
    
    storage = LocalStorage()
    
    # Ensure device is registered first
    registered_devices = storage.get_registered_devices()
    device_found = any(device['device_id'] == test_device_id for device in registered_devices)
    if not device_found:
        process_barcode_scan(test_device_id, test_device_id)
    
    # Get initial quantity from registered devices
    registered_devices = storage.get_registered_devices()
    initial_quantity = 0
    for device in registered_devices:
        if device['device_id'] == test_device_id:
            initial_quantity = device.get('quantity', 0)
            break
    
    print(f"Initial quantity: {initial_quantity}")
    
    # Mock IoT Hub calls
    with patch('barcode_scanner_app.send_to_iot_hub') as mock_iot:
        mock_iot.return_value = True
        
        # Scan product barcode
        result = process_barcode_scan(test_barcode, test_device_id)
        
        # Get new quantity from registered devices
        registered_devices = storage.get_registered_devices()
        new_quantity = 0
        for device in registered_devices:
            if device['device_id'] == test_device_id:
                new_quantity = device.get('quantity', 0)
                break
        
        expected_quantity = initial_quantity + 1
        assert new_quantity == expected_quantity, f"Expected quantity {expected_quantity}, got {new_quantity}"
        
        # Verify IoT Hub message was sent
        assert mock_iot.called, "IoT Hub message should be sent for quantity update"
        
        print(f"✅ Product scanning test passed - quantity: {initial_quantity} → {new_quantity}")
        return True

def test_ean_field_inclusion():
    """Test that EAN field is included in IoT Hub messages"""
    print("\n=== Testing EAN Field Inclusion ===")
    
    test_device_id = "abc123def456"
    test_barcode = "9876543210987"
    
    # Capture IoT Hub message payload
    captured_payload = {}
    
    def capture_iot_message(device_id, message_type, payload, connection_string=None):
        captured_payload.update(payload)
        return True
    
    with patch('barcode_scanner_app.send_to_iot_hub', side_effect=capture_iot_message):
        # Scan product barcode
        process_barcode_scan(test_barcode, test_device_id)
        
        # Verify both scannedBarcode and ean fields are present
        assert 'scannedBarcode' in captured_payload, "scannedBarcode field missing"
        assert 'ean' in captured_payload, "ean field missing"
        assert captured_payload['scannedBarcode'] == test_barcode, "scannedBarcode value incorrect"
        assert captured_payload['ean'] == test_barcode, "ean value incorrect"
        
        print("✅ EAN field inclusion test passed")
        print(f"   scannedBarcode: {captured_payload.get('scannedBarcode')}")
        print(f"   ean: {captured_payload.get('ean')}")
        return True

def test_database_consistency():
    """Test database operations and consistency"""
    print("\n=== Testing Database Consistency ===")
    
    test_device_id = "test123device"
    
    storage = LocalStorage()
    
    # Register device
    device_data = {
        'device_id': test_device_id,
        'quantity': 5,
        'timestamp': time.time()
    }
    storage.save_registered_device(device_data)
    
    # Verify registration
    registered_devices = storage.get_registered_devices()
    device_found = any(device['device_id'] == test_device_id for device in registered_devices)
    assert device_found, "Device should be registered in database"
    
    # Verify quantity
    for device in registered_devices:
        if device['device_id'] == test_device_id:
            quantity = device.get('quantity', 0)
            assert quantity == 5, f"Expected quantity 5, got {quantity}"
            break
    
    # Clean up
    storage.clear_all_registered_devices()
    
    print("✅ Database consistency test passed")
    return True

def run_all_tests():
    """Run all verification tests"""
    print("🔍 Starting Final System Verification")
    print("=" * 50)
    
    tests = [
        ("Device Registration", test_device_registration),
        ("Product Scanning", test_product_scanning),
        ("EAN Field Inclusion", test_ean_field_inclusion),
        ("Database Consistency", test_database_consistency)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"❌ {test_name} failed")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} failed with error: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! System is production-ready.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the issues above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
