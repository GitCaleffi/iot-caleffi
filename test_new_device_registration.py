import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from barcode_scanner_app import process_barcode_scan
from utils.dynamic_device_manager import device_manager
from database.local_storage import LocalStorage
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_new_device_registration():
    """Test that a new device gets registered and sends IoT Hub message"""

    test_device_id = "test-new-device-12345"
    test_barcode = "8978456598745"
    
    print(f"\n🧪 Testing new device registration for device: {test_device_id}")
    print(f"📊 Testing with barcode: {test_barcode}")
    
    # Clear any existing registration for this test device
    local_db = LocalStorage()
    
    # Check if device exists in dynamic manager
    if device_manager.is_device_registered(test_device_id):
        print(f"⚠️  Device {test_device_id} already exists in dynamic manager - removing for test")
        with device_manager.lock:
            if test_device_id in device_manager.device_cache:
                del device_manager.device_cache[test_device_id]
                device_manager.save_device_config()
    
    # Check if device exists in local DB
    registered_devices = local_db.get_registered_devices()
    if registered_devices:
        for device in registered_devices:
            if device.get('device_id') == test_device_id:
                print(f"⚠️  Device {test_device_id} found in local DB - this is expected behavior")
                break
    
    print(f"\n🚀 Processing barcode scan for new device...")
    
    # Process the barcode scan - this should trigger new device registration
    result = process_barcode_scan(test_barcode, test_device_id)
    
    print(f"\n📋 Result:")
    print(result)
    
    # Verify device is now registered
    print(f"\n✅ Verification:")
    
    # Check dynamic device manager
    if device_manager.is_device_registered(test_device_id):
        print(f"✅ Device {test_device_id} is now registered in dynamic device manager")
        device_info = device_manager.get_device_info(test_device_id)
        if device_info:
            print(f"   - Registered at: {device_info.get('registered_at', 'Unknown')}")
            print(f"   - Status: {device_info.get('status', 'Unknown')}")
    else:
        print(f"❌ Device {test_device_id} is NOT registered in dynamic device manager")
    
    # Check local database
    registered_devices = local_db.get_registered_devices()
    found_in_local = False
    if registered_devices:
        for device in registered_devices:
            if device.get('device_id') == test_device_id:
                found_in_local = True
                print(f"✅ Device {test_device_id} is registered in local database")
                print(f"   - Registered at: {device.get('registered_at', 'Unknown')}")
                break
    
    if not found_in_local:
        print(f"❌ Device {test_device_id} is NOT found in local database")
    
    return result

def test_existing_device_scan():
    """Test that an existing device processes barcode normally"""
    
    # Use a device that should already be registered
    test_device_id = "817994ccfe14"  # This should be an existing device
    test_barcode = "1234567890123"
    
    print(f"\n🧪 Testing existing device barcode scan for device: {test_device_id}")
    print(f"📊 Testing with barcode: {test_barcode}")
    
    # Check if device is registered
    is_registered = device_manager.is_device_registered(test_device_id)
    print(f"📋 Device registration status: {is_registered}")
    
    print(f"\n🚀 Processing barcode scan for existing device...")
    
    # Process the barcode scan
    result = process_barcode_scan(test_barcode, test_device_id)
    
    print(f"\n📋 Result:")
    print(result)
    
    return result

if __name__ == "__main__":
    print("🔧 Device Registration Test Suite")
    print("=" * 50)
    
    try:
        # Test 1: New device registration
        print("\n" + "="*50)
        print("TEST 1: New Device Registration")
        print("="*50)
        test_new_device_registration()
        
        # Test 2: Existing device scan
        print("\n" + "="*50)
        print("TEST 2: Existing Device Scan")
        print("="*50)
        test_existing_device_scan()
        
        print("\n" + "="*50)
        print("✅ All tests completed!")
        print("="*50)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
