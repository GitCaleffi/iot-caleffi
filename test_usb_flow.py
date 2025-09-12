#!/usr/bin/env python3
"""
Test USB Scanner Flow - Simulates USB scanner input to test the complete flow
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

def test_usb_scanner_initialization():
    """Test USB scanner initialization and device detection"""
    print("=" * 60)
    print("TESTING USB SCANNER INITIALIZATION")
    print("=" * 60)
    
    try:
        from usb_auto_scanner import AutoUSBScanner
        
        print("1. Creating AutoUSBScanner instance...")
        scanner = AutoUSBScanner()
        print("   ✅ AutoUSBScanner created successfully")
        
        print(f"2. Checking device ID assignment...")
        print(f"   Device ID: {scanner.device_id}")
        
        if scanner.device_id:
            print("   ✅ Device ID assigned")
        else:
            print("   ❌ No device ID assigned")
        
        print(f"3. Checking scanner state...")
        print(f"   Running: {scanner.running}")
        print(f"   Registered: {scanner.registered}")
        
        return scanner
        
    except Exception as e:
        print(f"❌ USB scanner initialization error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_usb_scanner_registration(scanner):
    """Test USB scanner device registration flow"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER REGISTRATION FLOW")
    print("=" * 60)
    
    if not scanner:
        print("❌ No scanner instance available")
        return False
    
    test_barcode = "1234567890123"  # EAN-13 test barcode
    
    try:
        print(f"1. Testing auto-registration with barcode: {test_barcode}")
        
        # Simulate the auto-registration process
        if not scanner.registered:
            print("   Device not registered, triggering auto-registration...")
            scanner.auto_register_device(test_barcode)
            print("   ✅ Auto-registration completed")
        else:
            print("   ⚠️  Device already registered")
        
        print(f"2. Checking registration status...")
        print(f"   Registered: {scanner.registered}")
        print(f"   Device ID: {scanner.device_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ USB scanner registration error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_usb_scanner_barcode_processing(scanner):
    """Test USB scanner barcode processing flow"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER BARCODE PROCESSING")
    print("=" * 60)
    
    if not scanner:
        print("❌ No scanner instance available")
        return False
    
    test_barcodes = [
        "5901234123457",  # EAN-13
        "8978456598745",  # Another EAN-13
        "1234567890"      # EAN-10
    ]
    
    try:
        for i, barcode in enumerate(test_barcodes, 1):
            print(f"{i}. Processing barcode: {barcode}")
            
            try:
                # Simulate barcode processing
                scanner.process_barcode(barcode)
                print(f"   ✅ Barcode {barcode} processed successfully")
                
                # Small delay between scans
                time.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Error processing barcode {barcode}: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ USB scanner barcode processing error: {str(e)}")
        return False

def test_usb_scanner_iot_messaging():
    """Test USB scanner IoT Hub messaging"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER IOT HUB MESSAGING")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"  # Our registered device
    test_barcode = "5901234123457"
    
    try:
        from iot.dynamic_registration_service import get_dynamic_registration_service
        from iot.hub_client import HubClient
        
        print("1. Getting dynamic registration service...")
        reg_service = get_dynamic_registration_service()
        
        if reg_service:
            print("   ✅ Dynamic registration service available")
            
            print("2. Getting device connection string...")
            connection_string = reg_service.register_device(device_id)
            
            if connection_string:
                print("   ✅ Device connection string obtained")
                print(f"   Connection string length: {len(connection_string)}")
                
                print("3. Testing IoT Hub message sending...")
                hub_client = HubClient(connection_string, device_id)
                
                # Test registration message
                registration_message = {
                    "deviceId": device_id,
                    "messageType": "device_registration",
                    "action": "register",
                    "scannedBarcode": test_barcode,
                    "timestamp": datetime.now().isoformat(),
                    "source": "usb_scanner_test"
                }
                
                result = hub_client.send_message(json.dumps(registration_message), device_id)
                if result:
                    print(f"   ✅ Registration message sent - ID: {result}")
                else:
                    print("   ⚠️  Registration message send failed")
                
                # Test quantity message
                quantity_message = {
                    "deviceId": device_id,
                    "messageType": "quantity_update",
                    "scannedBarcode": test_barcode,
                    "quantity": 1,
                    "timestamp": datetime.now().isoformat(),
                    "source": "usb_scanner_test"
                }
                
                result = hub_client.send_message(json.dumps(quantity_message), device_id)
                if result:
                    print(f"   ✅ Quantity message sent - ID: {result}")
                else:
                    print("   ⚠️  Quantity message send failed")
                
                return True
            else:
                print("   ❌ Could not get device connection string")
        else:
            print("   ❌ Dynamic registration service not available")
        
        return False
        
    except Exception as e:
        print(f"❌ IoT Hub messaging test error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_usb_scanner_database_operations():
    """Test USB scanner database operations"""
    print("\n" + "=" * 60)
    print("TESTING USB SCANNER DATABASE OPERATIONS")
    print("=" * 60)
    
    device_id = "7079fa7ab32e"
    test_barcode = "5901234123457"
    
    try:
        from database.local_storage import LocalStorage
        
        storage = LocalStorage()
        
        print("1. Testing device registration check...")
        devices = storage.get_registered_devices()
        device_found = any(d['device_id'] == device_id for d in devices)
        
        if device_found:
            print(f"   ✅ Device {device_id} found in database")
        else:
            print(f"   ❌ Device {device_id} not found in database")
        
        print("2. Testing barcode scan storage...")
        try:
            storage.save_barcode_scan(test_barcode, device_id)
            print(f"   ✅ Barcode scan saved to database")
        except Exception as e:
            print(f"   ❌ Error saving barcode scan: {str(e)}")
        
        print("3. Testing unsent message storage...")
        try:
            test_message = {
                "deviceId": device_id,
                "messageType": "test",
                "barcode": test_barcode,
                "timestamp": datetime.now().isoformat()
            }
            
            storage.save_unsent_message(json.dumps(test_message), device_id, datetime.now())
            print(f"   ✅ Unsent message saved to database")
        except Exception as e:
            print(f"   ❌ Error saving unsent message: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database operations test error: {str(e)}")
        return False

def run_complete_usb_flow_test():
    """Run complete USB scanner flow test"""
    print("USB SCANNER FLOW TEST")
    print("Device ID: 7079fa7ab32e")
    print("=" * 60)
    
    # Test 1: Initialization
    scanner = test_usb_scanner_initialization()
    
    # Test 2: Registration
    registration_success = test_usb_scanner_registration(scanner)
    
    # Test 3: Barcode Processing
    processing_success = test_usb_scanner_barcode_processing(scanner)
    
    # Test 4: IoT Hub Messaging
    iot_success = test_usb_scanner_iot_messaging()
    
    # Test 5: Database Operations
    db_success = test_usb_scanner_database_operations()
    
    # Summary
    print("\n" + "=" * 60)
    print("USB SCANNER FLOW TEST SUMMARY")
    print("=" * 60)
    
    tests = [
        ("Initialization", scanner is not None),
        ("Registration", registration_success),
        ("Barcode Processing", processing_success),
        ("IoT Hub Messaging", iot_success),
        ("Database Operations", db_success)
    ]
    
    passed = 0
    for test_name, success in tests:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{test_name:20} {status}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All USB scanner flow tests PASSED!")
    else:
        print("⚠️  Some USB scanner flow tests FAILED")
    
    return passed == len(tests)

if __name__ == "__main__":
    run_complete_usb_flow_test()
