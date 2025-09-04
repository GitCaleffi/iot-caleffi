#!/usr/bin/env python3
"""
Test web interface Pi Status display
"""

import sys
import os

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

def test_web_status():
    """Test the web interface status display"""
    
    print("🧪 Testing Web Interface Pi Status Display")
    print("=" * 50)
    
    # Import the function that generates the status
    from deployment_package.barcode_scanner_app import generate_registration_token
    
    print("📡 Calling generate_registration_token() to check Pi Status...")
    
    try:
        # Call the function that generates the status message
        status_message = generate_registration_token()
        
        print("\n📋 Current Status Message:")
        print("-" * 30)
        print(status_message)
        print("-" * 30)
        
        # Check what status is displayed
        if "Pi Status:** Connected ✅" in status_message:
            print("\n✅ Status: Pi shows as CONNECTED")
        elif "Pi Status:** Internet OK, IoT Hub Issues ⚠️" in status_message:
            print("\n⚠️ Status: Pi shows INTERNET OK but IoT HUB ISSUES")
        elif "Pi Status:** Disconnected ❌" in status_message:
            print("\n❌ Status: Pi shows as DISCONNECTED")
        else:
            print("\n❓ Status: Unknown status format")
            
        print("\n💡 This status should now accurately reflect:")
        print("   - Internet connectivity")
        print("   - IoT Hub accessibility")
        print("   - Network interface status")
        
    except Exception as e:
        print(f"❌ Error testing web status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_web_status()
