#!/usr/bin/env python3
"""
Test the complete registration flow for device registration messages
"""

import sys
import json
from datetime import datetime, timezone

# Add src directory to path
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')

def test_registration_flow():
    """Test complete registration flow"""
    device_id = "test-reg-" + str(int(datetime.now().timestamp()))
    
    print(f"🧪 Testing registration flow for device: {device_id}")
    
    try:
        # Import the registration function
        from barcode_scanner_app import confirm_registration
        
        # Test registration
        result = confirm_registration("", device_id)
        
        print("📋 Registration Result:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        
        if "✅" in result and "Registration Completed" in result:
            print(f"✅ Registration test successful for {device_id}")
            return True
        else:
            print(f"❌ Registration test failed for {device_id}")
            return False
            
    except Exception as e:
        print(f"❌ Registration test error: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Registration Flow Test")
    print("=" * 50)
    
    success = test_registration_flow()
    
    if success:
        print("\n🎉 Test Complete!")
        print("✅ Registration messages should now appear on both IoT Hub and frontend")
    else:
        print("\n❌ Test Failed!")
        print("Check the error messages above")

if __name__ == "__main__":
    main()