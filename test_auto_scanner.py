#!/usr/bin/env python3
"""
Test script to verify automatic USB scanner functionality
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.append(str(Path(__file__).resolve().parent / 'src'))

def test_components():
    """Test all required components"""
    print("🔍 Testing Automatic USB Scanner Components")
    print("=" * 50)
    
    # Test 1: Check evdev availability
    print("\n1. Testing USB scanner support...")
    try:
        import evdev
        print("   ✅ evdev module available")
        
        # List available devices
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        print(f"   📱 Found {len(devices)} input devices")
        
        scanner_found = False
        for device in devices:
            device_name = device.name.lower()
            if any(keyword in device_name for keyword in ['barcode', 'scanner', 'hid']):
                print(f"   ✅ Potential scanner: {device.name}")
                scanner_found = True
                
        if not scanner_found:
            print("   ⚠️ No USB scanner detected (connect scanner and retry)")
    except ImportError:
        print("   ❌ evdev not installed - run: pip install evdev")
        
    # Test 2: Check database
    print("\n2. Testing local database...")
    try:
        from database.local_storage import LocalStorage
        db = LocalStorage()
        device_id = db.get_device_id()
        if device_id:
            print(f"   ✅ Device registered: {device_id}")
        else:
            print("   ℹ️ No device registered (will auto-register on first scan)")
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        
    # Test 3: Check API connectivity
    print("\n3. Testing API connectivity...")
    try:
        from api.api_client import ApiClient
        api = ApiClient()
        if api.is_online():
            print("   ✅ API is reachable")
        else:
            print("   ⚠️ API offline (will queue messages)")
    except Exception as e:
        print(f"   ❌ API error: {e}")
        
    # Test 4: Check IoT Hub configuration
    print("\n4. Testing IoT Hub configuration...")
    try:
        from utils.config import load_config
        config = load_config()
        if config and "iot_hub" in config:
            print("   ✅ IoT Hub configured")
            devices = config.get("iot_hub", {}).get("devices", {})
            print(f"   📱 {len(devices)} devices in config")
            
            # Check for the problematic device
            if "29f002cd1ead" in devices:
                device_config = devices["29f002cd1ead"]
                if "YOUR_DEVICE_SPECIFIC_KEY_HERE" in device_config.get("connection_string", ""):
                    print("   ⚠️ Device 29f002cd1ead has placeholder key - needs fixing")
                else:
                    print("   ✅ Device 29f002cd1ead properly configured")
        else:
            print("   ❌ IoT Hub not configured")
    except Exception as e:
        print(f"   ❌ Config error: {e}")
        
    # Test 5: Check Azure IoT SDK
    print("\n5. Testing Azure IoT SDK...")
    try:
        from azure.iot.device import IoTHubDeviceClient
        print("   ✅ Azure IoT Device SDK available")
        
        try:
            from azure.iot.hub import IoTHubRegistryManager
            print("   ✅ Azure IoT Hub SDK available (for registration)")
        except ImportError:
            print("   ⚠️ Azure IoT Hub SDK not available (install: pip install azure-iot-hub)")
    except ImportError:
        print("   ❌ Azure IoT Device SDK not installed - run: pip install azure-iot-device")
        
    # Test 6: Test automatic scanner module
    print("\n6. Testing automatic scanner module...")
    try:
        from usb_auto_scanner import AutoUSBScanner
        scanner = AutoUSBScanner()
        print("   ✅ AutoUSBScanner module loaded")
        
        # Check if scanner can be detected
        device = scanner.find_usb_scanner()
        if device:
            print(f"   ✅ Scanner detected: {device.name}")
        else:
            print("   ℹ️ No scanner connected")
    except Exception as e:
        print(f"   ❌ Scanner module error: {e}")
        
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print("   • Connect USB scanner and run: ./start_auto_usb_scanner.sh")
    print("   • Or test manually: python3 src/usb_auto_scanner.py")
    print("   • For service mode: sudo ./start_auto_usb_scanner.sh")

if __name__ == "__main__":
    test_components()