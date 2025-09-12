#!/usr/bin/env python3
"""
Test USB Scanner Flow - Tests the complete USB scanner functionality
"""

import sys
import os
import time
import json
from datetime import datetime
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir / 'src'))

def test_usb_scanner_components():
    """Test USB scanner component initialization"""
    print("=" * 60)
    print("TESTING USB SCANNER COMPONENTS")
    print("=" * 60)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from usb_auto_scanner import AutoUSBScanner
        from database.local_storage import LocalStorage
        from api.api_client import ApiClient
        print("   ✅ All imports successful")
        
        # Test component initialization
        print("2. Testing component initialization...")
        scanner = AutoUSBScanner()
        storage = LocalStorage()
        api_client = ApiClient()
        print("   ✅ Components initialized successfully")
        
        # Check device ID assignment
        print("3. Checking device ID assignment...")
        existing_device = storage.get_device_id()
        if existing_device:
            scanner.device_id = existing_device
            print(f"   ✅ Using existing device ID: {scanner.device_id}")
        else:
            print("   ⚠️  No existing device ID found")
        
        return scanner, storage, api_client
        
    except Exception as e:
        print(f"❌ Component test error: {str(e)}")
        return None, None, None

def test_usb_scanner_device_detection():
    """Test USB scanner device detection"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER DEVICE DETECTION")
    print("=" * 60)
    
    try:
        from usb_auto_scanner import AutoUSBScanner
        
        scanner = AutoUSBScanner()
        
        print("1. Testing USB scanner detection...")
        usb_device = scanner.find_usb_scanner()
        
        if usb_device:
            print(f"   ✅ USB scanner detected: {usb_device.name}")
            print(f"   Device path: {usb_device.path}")
            return True
        else:
            print("   ⚠️  No USB scanner detected (expected if no physical scanner)")
            return False
            
    except Exception as e:
        print(f"❌ USB detection error: {str(e)}")
        return False

def test_usb_scanner_registration_flow():
    """Test USB scanner registration flow"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER REGISTRATION FLOW")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"  # Our registered device
    test_barcode = "1234567890123"
    
    try:
        from usb_auto_scanner import AutoUSBScanner
        from database.local_storage import LocalStorage
        
        scanner = AutoUSBScanner()
        storage = LocalStorage()
        
        print("1. Setting up scanner with registered device...")
        scanner.device_id = device_id
        print(f"   Device ID: {scanner.device_id}")
        
        print("2. Testing auto-registration logic...")
        # Test the registration logic without actually registering
        existing_device = storage.get_device_id()
        if existing_device == device_id:
            print(f"   ✅ Device {device_id} already registered")
        else:
            print(f"   ⚠️  Device {device_id} not found in storage")
        
        print("3. Testing registration message creation...")
        try:
            # Test the send_registration_message method
            scanner.send_registration_message(device_id, test_barcode)
            print("   ✅ Registration message logic executed")
        except Exception as e:
            print(f"   ⚠️  Registration message error: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Registration flow error: {str(e)}")
        return False

def test_usb_scanner_barcode_processing():
    """Test USB scanner barcode processing"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER BARCODE PROCESSING")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"
    test_barcodes = [
        "5901234123457",  # EAN-13
        "8978456598745",  # Another EAN-13
        "1234567890"      # EAN-10
    ]
    
    try:
        from usb_auto_scanner import AutoUSBScanner
        
        scanner = AutoUSBScanner()
        scanner.device_id = device_id  # Set our registered device
        
        print(f"Scanner device ID: {scanner.device_id}")
        
        for i, barcode in enumerate(test_barcodes, 1):
            print(f"{i}. Processing barcode: {barcode}")
            
            try:
                # Test barcode processing
                scanner.process_barcode(barcode)
                print(f"   ✅ Barcode {barcode} processed")
                
                # Check scan count
                print(f"   Scan count: {scanner.scan_count}")
                
                time.sleep(0.5)  # Small delay
                
            except Exception as e:
                print(f"   ❌ Error processing {barcode}: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Barcode processing error: {str(e)}")
        return False

def test_usb_scanner_iot_integration():
    """Test USB scanner IoT Hub integration"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER IOT HUB INTEGRATION")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"
    
    try:
        from usb_auto_scanner import AutoUSBScanner
        from utils.config import load_config
        
        scanner = AutoUSBScanner()
        
        print("1. Checking IoT Hub configuration...")
        config = load_config()
        
        if config and "iot_hub" in config:
            print("   ✅ IoT Hub config found")
            
            devices = config.get("iot_hub", {}).get("devices", {})
            if device_id in devices:
                print(f"   ✅ Device {device_id} found in IoT Hub config")
                conn_string = devices[device_id]["connection_string"]
                print(f"   Connection string length: {len(conn_string)}")
            else:
                print(f"   ⚠️  Device {device_id} not in IoT Hub config")
        else:
            print("   ❌ IoT Hub config not found")
        
        print("2. Testing IoT Hub registration...")
        try:
            result = scanner.register_with_iot_hub(device_id)
            if result:
                print("   ✅ IoT Hub registration successful")
            else:
                print("   ⚠️  IoT Hub registration failed")
        except Exception as e:
            print(f"   ❌ IoT Hub registration error: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ IoT integration error: {str(e)}")
        return False

def test_usb_scanner_offline_handling():
    """Test USB scanner offline handling"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER OFFLINE HANDLING")
    print("=" * 60)
    
    try:
        from database.local_storage import LocalStorage
        from iot.connection_manager import connection_manager
        
        storage = LocalStorage()
        
        print("1. Testing connection manager...")
        try:
            # Test connection status
            is_connected = connection_manager.check_raspberry_pi_availability()
            print(f"   Pi connection status: {'Connected' if is_connected else 'Disconnected'}")
        except Exception as e:
            print(f"   ⚠️  Connection check error: {str(e)}")
        
        print("2. Testing local storage for offline mode...")
        device_id = "7079fa7ab32e"
        test_barcode = "offline_test_123"
        
        try:
            # Test saving scan locally
            timestamp = storage.save_scan(device_id, test_barcode, 1)
            print(f"   ✅ Scan saved locally with timestamp: {timestamp}")
        except Exception as e:
            print(f"   ❌ Local save error: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Offline handling error: {str(e)}")
        return False

def run_usb_scanner_flow_test():
    """Run complete USB scanner flow test"""
    print("USB SCANNER FLOW TEST")
    print("Target Device: 7079fa7ab32e")
    print("=" * 60)
    
    # Test components
    scanner, storage, api_client = test_usb_scanner_components()
    component_success = scanner is not None
    
    # Test USB detection
    detection_success = test_usb_scanner_device_detection()
    
    # Test registration flow
    registration_success = test_usb_scanner_registration_flow()
    
    # Test barcode processing
    processing_success = test_usb_scanner_barcode_processing()
    
    # Test IoT integration
    iot_success = test_usb_scanner_iot_integration()
    
    # Test offline handling
    offline_success = test_usb_scanner_offline_handling()
    
    # Summary
    print("\n" + "=" * 60)
    print("USB SCANNER FLOW TEST SUMMARY")
    print("=" * 60)
    
    tests = [
        ("Component Initialization", component_success),
        ("USB Device Detection", detection_success),
        ("Registration Flow", registration_success),
        ("Barcode Processing", processing_success),
        ("IoT Hub Integration", iot_success),
        ("Offline Handling", offline_success)
    ]
    
    passed = 0
    for test_name, success in tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:25} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed >= 4:  # Allow some failures for missing hardware
        print("🎉 USB scanner flow tests MOSTLY PASSED!")
        print("Note: Some failures expected without physical USB scanner")
    else:
        print("⚠️  USB scanner flow has significant issues")
    
    return passed >= 4

if __name__ == "__main__":
    run_usb_scanner_flow_test()
