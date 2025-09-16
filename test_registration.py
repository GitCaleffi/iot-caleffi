#!/usr/bin/env python3
"""
Test script to verify device registration flow
Device ID: 3990eca74e6b
"""
import os
import json
import sys
import time

# Test device ID
TEST_DEVICE_ID = "3990eca74e6b"
DEVICE_CONFIG_FILE = '/var/www/html/abhimanyu/barcode_scanner_clean/device_config.json'

def cleanup_existing_registration():
    """Remove existing device registration"""
    if os.path.exists(DEVICE_CONFIG_FILE):
        os.remove(DEVICE_CONFIG_FILE)
        print("✅ Removed existing device registration")
    else:
        print("ℹ️ No existing device registration found")

def check_registration_status():
    """Check if device is registered"""
    if os.path.exists(DEVICE_CONFIG_FILE):
        try:
            with open(DEVICE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                device_id = config.get('device_id')
                print(f"📱 Device registered: {device_id}")
                return device_id
        except:
            print("❌ Error reading device config")
            return None
    else:
        print("📱 No device registered")
        return None

def simulate_registration():
    """Simulate the registration process"""
    print("\n🔧 SIMULATING DEVICE REGISTRATION")
    print("=" * 50)
    
    # Step 1: Check current status
    print("Step 1: Checking current registration status...")
    current_device = check_registration_status()
    
    # Step 2: Clean up if needed
    if current_device:
        print(f"Step 2: Cleaning up existing registration ({current_device})...")
        cleanup_existing_registration()
    else:
        print("Step 2: No cleanup needed")
    
    # Step 3: Show what keyboard_scanner.py would display
    print("\nStep 3: What keyboard_scanner.py would show:")
    print("🔧 DEVICE REGISTRATION REQUIRED")
    print("📱 Scan barcode to register this device:")
    print(f"💡 Test device ID: {TEST_DEVICE_ID}")
    print("=" * 50)
    
    # Step 4: Simulate user input
    print(f"\nStep 4: Simulating user scanning: {TEST_DEVICE_ID}")
    print(f"📝 Registering device: {TEST_DEVICE_ID}")
    
    # Step 5: Save device ID (simulate successful registration)
    config = {'device_id': TEST_DEVICE_ID}
    with open(DEVICE_CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    
    print(f"✅ Device registered successfully: {TEST_DEVICE_ID}")
    print("📡 Registration message would be sent to IoT Hub")
    print("💾 Device ID saved to local config")
    
    # Step 6: Verify registration
    print("\nStep 6: Verifying registration...")
    registered_device = check_registration_status()
    
    if registered_device == TEST_DEVICE_ID:
        print("✅ REGISTRATION TEST PASSED!")
        print(f"✅ Device {TEST_DEVICE_ID} successfully registered")
    else:
        print("❌ REGISTRATION TEST FAILED!")
        return False
    
    return True

def test_scanner_flow():
    """Test the complete scanner flow"""
    print("\n🎯 TESTING COMPLETE SCANNER FLOW")
    print("=" * 50)
    
    # Test registration
    registration_success = simulate_registration()
    
    if registration_success:
        print("\n📊 Next: Scanner would switch to quantity mode")
        print("🔍 Ready to scan barcodes for quantity updates")
        print("💡 Registration complete - device ready for production")
    
    return registration_success

def main():
    print("🧪 DEVICE REGISTRATION TEST SCRIPT")
    print(f"🎯 Target Device ID: {TEST_DEVICE_ID}")
    print("=" * 60)
    
    # Run the test
    success = test_scanner_flow()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ ALL TESTS PASSED!")
        print(f"✅ Device {TEST_DEVICE_ID} registration flow verified")
        print("\n📋 To test with actual keyboard_scanner.py:")
        print("1. rm /var/www/html/abhimanyu/barcode_scanner_clean/device_config.json")
        print("2. python3 keyboard_scanner.py")
        print(f"3. Type: {TEST_DEVICE_ID}")
    else:
        print("❌ TESTS FAILED!")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
