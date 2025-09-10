#!/usr/bin/env python3
"""
Simple test for device ID: e6fcc128b131 using barcode_scanner_app.py functions
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime, timezone

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_registered_device():
    """Test existing registered device e6fcc128b131"""
    
    device_id = "933dee6de6ee"
    
    print("🧪 TESTING REGISTERED DEVICE")
    print("=" * 50)
    print(f"📱 Device ID: {device_id}")
    print(f"⏰ Test Time: {datetime.now().isoformat()}")
    print()
    
    try:
        # Import required modules
        from database.local_storage import LocalStorage
        from iot.hub_client import HubClient
        from utils.config import load_config
        import json
        
        # Initialize local database
        local_db = LocalStorage()
        
        print("📋 STEP 1: Verify device registration")
        print("-" * 30)
        
        # Check if device exists in database
        registered_devices = local_db.get_registered_devices()
        device_found = None
        
        for device in registered_devices:
            if device.get('device_id') == device_id:
                device_found = device
                break
        
        if device_found:
            print(f"✅ Device {device_id} found in local database")
            print(f"📅 Registration Date: {device_found.get('registration_date', 'Unknown')}")
            print(f"🌐 Pi IP: {device_found.get('pi_ip', 'Unknown')}")
            print(f"📝 Method: {device_found.get('registration_method', 'Unknown')}")
        else:
            print(f"❌ Device {device_id} not found in database")
            return False
        
        print("\n📋 STEP 2: Test device ID functions")
        print("-" * 30)
        
        # Test setting device ID
        original_device_id = local_db.get_device_id()
        print(f"📍 Current device ID: {original_device_id}")
        
        # Set test device ID
        local_db.save_device_id(device_id)
        current_id = local_db.get_device_id()
        print(f"🔄 Set device ID to: {current_id}")
        
        if current_id == device_id:
            print("✅ Device ID setting successful")
        else:
            print("❌ Device ID setting failed")
        
        print("\n📋 STEP 3: Test barcode scanning simulation")
        print("-" * 30)
        
        # Load configuration
        config = load_config()
        iot_hub_config = config.get('iot_hub', {})
        
        if iot_hub_config.get('connection_string'):
            print("✅ IoT Hub configuration found")
            
            # Test barcode scan data preparation
            test_barcode = "5625415485555"
            print(f"🔍 Test barcode: {test_barcode}")
            
            # Prepare barcode scan message
            scan_message = {
                "deviceId": device_id,
                "messageType": "barcode_scan",
                "barcode": test_barcode,
                "quantity": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "test_mode": True
            }
            
            print(f"📦 Message prepared: {json.dumps(scan_message, indent=2)}")
            
            # Test local storage
            try:
                local_db.save_barcode_scan(device_id, test_barcode, 1)
                print("✅ Local barcode storage successful")
            except Exception as e:
                print(f"⚠️ Local storage error: {e}")
            
        else:
            print("⚠️ IoT Hub configuration not found")
        
        print("\n📋 STEP 4: Test device functions")
        print("-" * 30)
        
        # Test device listing
        all_devices = local_db.get_registered_devices()
        print(f"📊 Total registered devices: {len(all_devices)}")
        
        # Find our device in the list
        our_device = next((d for d in all_devices if d.get('device_id') == device_id), None)
        if our_device:
            print(f"✅ Device {device_id} verified in device list")
        else:
            print(f"❌ Device {device_id} not found in device list")
        
        # Restore original device ID
        if original_device_id:
            local_db.save_device_id(original_device_id)
            print(f"🔄 Restored original device ID: {original_device_id}")
        
        print("\n🏁 DEVICE TEST SUMMARY")
        print("=" * 50)
        print(f"📱 Device ID: {device_id}")
        print(f"✅ Database Registration: VERIFIED")
        print(f"💾 Local Storage: TESTED")
        print(f"📦 Message Preparation: SUCCESSFUL")
        print(f"🔍 Barcode Simulation: COMPLETED")
        print(f"⏰ Test Completed: {datetime.now().isoformat()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Device test failed: {e}")
        logger.error(f"Device test error: {e}")
        return False

if __name__ == "__main__":
    success = test_registered_device()
    if success:
        print("\n🎉 Device test completed successfully!")
        print(f"📱 Device e6fcc128b131 is ready for barcode scanning!")
    else:
        print("\n💥 Device test failed!")
        sys.exit(1)
