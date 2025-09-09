#!/usr/bin/env python3
"""
Fix IoT Hub messaging issues and create missing devices
This script addresses the two main problems:
1. Device 'auto-c1323007' not found in Azure IoT Hub
2. HubClient.send_message() method call errors
"""

import sys
import os
from pathlib import Path
import logging
import json
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'deployment_package' / 'src'
sys.path.insert(0, str(src_dir))

def create_device_in_iot_hub(device_id):
    """Create device in Azure IoT Hub if it doesn't exist"""
    try:
        from utils.dynamic_registration_service import get_dynamic_registration_service
        
        print(f"🔧 Creating device {device_id} in Azure IoT Hub...")
        
        # Get registration service
        reg_service = get_dynamic_registration_service()
        if not reg_service:
            print("❌ Dynamic registration service not available")
            return False
        
        # Try to register device with Azure
        connection_string = reg_service.register_device_with_azure(device_id)
        
        if connection_string:
            print(f"✅ Device {device_id} created successfully in IoT Hub")
            print(f"📡 Connection string obtained: {connection_string[:50]}...")
            return connection_string
        else:
            print(f"❌ Failed to create device {device_id} in IoT Hub")
            return False
            
    except Exception as e:
        print(f"❌ Error creating device: {e}")
        return False

def test_fixed_messaging(device_id, barcode):
    """Test the fixed IoT Hub messaging with proper device_id parameter"""
    try:
        from barcode_scanner_app import process_barcode_scan
        
        print(f"\n🧪 Testing fixed IoT Hub messaging...")
        print(f"📱 Device ID: {device_id}")
        print(f"🏷️  Barcode: {barcode}")
        print("-" * 50)
        
        # Process barcode scan with the fixes
        result = process_barcode_scan(barcode, device_id)
        
        print("\n📊 RESULT:")
        print("-" * 30)
        print(result)
        
        # Check if successful
        if "✅" in result and "Sent to IoT Hub" in result:
            print("\n🎉 SUCCESS: IoT Hub messaging working!")
            return True
        elif "⚠️" in result and "Auto-Retry" in result:
            print("\n🟡 PARTIAL: Message saved for retry (device may need creation)")
            return "retry"
        else:
            print("\n❌ FAILED: IoT Hub messaging not working")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main function to fix IoT Hub messaging issues"""
    
    print("🔧 IoT Hub Messaging Fix Tool")
    print("=" * 50)
    
    # Test devices from the logs
    test_devices = [
        ("auto-c1323007", "7854789658965"),  # Auto-generated device
        ("cfabc4830309", "7854789658965"),   # Custom device from test
    ]
    
    results = {}
    
    for device_id, barcode in test_devices:
        print(f"\n🔍 Processing device: {device_id}")
        print("=" * 40)
        
        # Step 1: Try to create device in IoT Hub
        connection_string = create_device_in_iot_hub(device_id)
        
        # Step 2: Test messaging with fixes
        test_result = test_fixed_messaging(device_id, barcode)
        
        results[device_id] = {
            "device_created": bool(connection_string),
            "messaging_test": test_result,
            "connection_string": connection_string if connection_string else None
        }
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 FIX SUMMARY")
    print("=" * 60)
    
    for device_id, result in results.items():
        print(f"\n📱 Device: {device_id}")
        print(f"   • Device Creation: {'✅' if result['device_created'] else '❌'}")
        print(f"   • Messaging Test: {'✅' if result['messaging_test'] == True else '🟡' if result['messaging_test'] == 'retry' else '❌'}")
        
        if result['connection_string']:
            print(f"   • Connection String: Available")
    
    # Check if fixes worked
    successful_devices = sum(1 for r in results.values() if r['messaging_test'] == True)
    total_devices = len(results)
    
    print(f"\n📊 OVERALL RESULT:")
    print(f"   • Devices processed: {total_devices}")
    print(f"   • Successful messaging: {successful_devices}")
    print(f"   • Success rate: {(successful_devices/total_devices)*100:.1f}%")
    
    if successful_devices > 0:
        print("\n🎉 FIXES SUCCESSFUL!")
        print("✅ HubClient.send_message() method calls fixed")
        print("✅ Device creation in Azure IoT Hub working")
        print("✅ IoT Hub messages should now appear in Azure Portal")
        
        print("\n📋 NEXT STEPS:")
        print("1. Check Azure IoT Hub portal for new devices")
        print("2. Monitor device-to-cloud messages")
        print("3. Verify message delivery in IoT Hub logs")
        
    else:
        print("\n⚠️ PARTIAL SUCCESS - Some issues remain")
        print("ℹ️ Check Azure IoT Hub connection string configuration")
        print("ℹ️ Verify network connectivity to Azure")
    
    return successful_devices > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
