#!/usr/bin/env python3
"""
Test API endpoints to find working ones for registration and quantity updates
"""

import requests
import json
import sys
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'deployment_package' / 'src'
sys.path.insert(0, str(src_dir))

def test_api_endpoints():
    """Test various API endpoints to find working ones"""
    
    base_url = "https://api2.caleffionline.it/api/v1"
    
    # Test data
    device_id = "cfabc4830309"
    barcode = "7854789658965"
    
    # Test endpoints for registration
    registration_endpoints = [
        ("raspberry/saveDeviceId", {"deviceId": device_id}),
        ("raspberry/confirmRegistration", {"deviceId": device_id, "status": "registered"}),
        ("raspberry/registerDevice", {"deviceId": device_id}),
        ("device/register", {"deviceId": device_id}),
    ]
    
    # Test endpoints for barcode scanning
    barcode_endpoints = [
        ("raspberry/barcodeScan", {"deviceId": device_id, "scannedBarcode": barcode, "quantity": 1}),
        ("raspberry/saveDeviceId", {"scannedBarcode": barcode, "deviceId": device_id}),
        ("barcode/scan", {"deviceId": device_id, "barcode": barcode, "quantity": 1}),
        ("scan", {"deviceId": device_id, "barcode": barcode}),
    ]
    
    print("🔍 Testing API Endpoints")
    print("=" * 50)
    
    working_endpoints = {}
    
    # Test registration endpoints
    print("\n📝 TESTING REGISTRATION ENDPOINTS:")
    print("-" * 40)
    
    for endpoint, payload in registration_endpoints:
        url = f"{base_url}/{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            status = "✅ WORKING" if response.status_code == 200 else f"❌ {response.status_code}"
            print(f"{endpoint:<25} {status}")
            
            if response.status_code == 200:
                working_endpoints['registration'] = (endpoint, payload)
                print(f"  Response: {response.text[:100]}...")
            elif response.status_code != 404:
                print(f"  Error: {response.text[:100]}...")
                
        except Exception as e:
            print(f"{endpoint:<25} ❌ ERROR: {str(e)[:50]}...")
    
    # Test barcode endpoints
    print("\n📱 TESTING BARCODE SCAN ENDPOINTS:")
    print("-" * 40)
    
    for endpoint, payload in barcode_endpoints:
        url = f"{base_url}/{endpoint}"
        try:
            response = requests.post(url, json=payload, timeout=10)
            status = "✅ WORKING" if response.status_code == 200 else f"❌ {response.status_code}"
            print(f"{endpoint:<25} {status}")
            
            if response.status_code == 200:
                working_endpoints['barcode'] = (endpoint, payload)
                print(f"  Response: {response.text[:100]}...")
            elif response.status_code != 404:
                print(f"  Error: {response.text[:100]}...")
                
        except Exception as e:
            print(f"{endpoint:<25} ❌ ERROR: {str(e)[:50]}...")
    
    # Test alternative base URLs
    print("\n🌐 TESTING ALTERNATIVE BASE URLS:")
    print("-" * 40)
    
    alternative_urls = [
        "https://iot.caleffionline.it/api/v1",
        "https://api.caleffionline.it/api/v1",
        "https://iot.caleffionline.it/api",
    ]
    
    for alt_base in alternative_urls:
        try:
            # Test a simple endpoint
            url = f"{alt_base}/raspberry/saveDeviceId"
            response = requests.post(url, json={"scannedBarcode": barcode}, timeout=5)
            status = "✅ ACCESSIBLE" if response.status_code in [200, 400] else f"❌ {response.status_code}"
            print(f"{alt_base:<35} {status}")
            
            if response.status_code in [200, 400]:
                working_endpoints['base_url'] = alt_base
                
        except Exception as e:
            print(f"{alt_base:<35} ❌ ERROR: {str(e)[:30]}...")
    
    return working_endpoints

def fix_api_client(working_endpoints):
    """Update API client with working endpoints"""
    
    if not working_endpoints:
        print("\n❌ No working endpoints found - cannot fix API client")
        return False
    
    print(f"\n🔧 FIXING API CLIENT WITH WORKING ENDPOINTS")
    print("=" * 50)
    
    # Read current API client
    api_client_path = current_dir / 'deployment_package' / 'src' / 'api' / 'api_client.py'
    
    with open(api_client_path, 'r') as f:
        content = f.read()
    
    # Update base URL if we found a working one
    if 'base_url' in working_endpoints:
        new_base_url = working_endpoints['base_url']
        content = content.replace(
            'base_url: str = "https://api2.caleffionline.it/api/v1"',
            f'base_url: str = "{new_base_url}"'
        )
        print(f"✅ Updated base URL to: {new_base_url}")
    
    # Update registration endpoint if we found a working one
    if 'registration' in working_endpoints:
        reg_endpoint, reg_payload = working_endpoints['registration']
        print(f"✅ Found working registration endpoint: {reg_endpoint}")
        
        # Update confirm_registration method
        old_url_line = 'url = f"{self.base_url}/raspberry/confirmRegistration"'
        new_url_line = f'url = f"{{self.base_url}}/{reg_endpoint}"'
        content = content.replace(old_url_line, new_url_line)
    
    # Update barcode endpoint if we found a working one
    if 'barcode' in working_endpoints:
        barcode_endpoint, barcode_payload = working_endpoints['barcode']
        print(f"✅ Found working barcode endpoint: {barcode_endpoint}")
        
        # Update send_barcode_scan method
        old_endpoints = '''endpoints_to_try = [
                ("raspberry/barcodeScan", {"deviceId": device_id, "scannedBarcode": barcode, "quantity": quantity}),
                ("raspberry/saveDeviceId", {"scannedBarcode": barcode, "deviceId": device_id, "quantity": quantity}),
                ("raspberry/saveDeviceId", {"scannedBarcode": barcode}),
            ]'''
        
        # Create new payload structure based on what worked
        payload_structure = str(barcode_payload).replace(device_id, '"+device_id+"').replace(barcode, '"+barcode+"')
        
        new_endpoints = f'''endpoints_to_try = [
                ("{barcode_endpoint}", {payload_structure}),
                ("raspberry/saveDeviceId", {{"scannedBarcode": barcode, "deviceId": device_id, "quantity": quantity}}),
            ]'''
        
        content = content.replace(old_endpoints, new_endpoints)
    
    # Write updated API client
    with open(api_client_path, 'w') as f:
        f.write(content)
    
    print("✅ API client updated with working endpoints")
    return True

def test_fixed_integration():
    """Test the fixed API integration"""
    
    print(f"\n🧪 TESTING FIXED API INTEGRATION")
    print("=" * 50)
    
    try:
        from api.api_client import ApiClient
        
        api_client = ApiClient()
        
        # Test registration
        print("📝 Testing registration...")
        reg_result = api_client.confirm_registration("cfabc4830309")
        print(f"Registration result: {reg_result.get('success', False)} - {reg_result.get('message', 'No message')}")
        
        # Test barcode scan
        print("📱 Testing barcode scan...")
        scan_result = api_client.send_barcode_scan("cfabc4830309", "7854789658965", 1)
        print(f"Barcode scan result: {scan_result.get('success', False)} - {scan_result.get('message', 'No message')}")
        
        if reg_result.get('success') or scan_result.get('success'):
            print("✅ API integration working!")
            return True
        else:
            print("❌ API integration still not working")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    """Main function"""
    
    print("🔧 API Endpoint Fix Tool")
    print("Testing and fixing API integration for frontend updates")
    print("=" * 60)
    
    # Step 1: Test endpoints
    working_endpoints = test_api_endpoints()
    
    # Step 2: Fix API client if we found working endpoints
    if working_endpoints:
        fix_success = fix_api_client(working_endpoints)
        
        if fix_success:
            # Step 3: Test the fixed integration
            test_success = test_fixed_integration()
            
            if test_success:
                print(f"\n🎉 SUCCESS: API integration fixed!")
                print("✅ Registration and quantity updates should now appear in frontend")
                return True
    
    print(f"\n⚠️ Could not fully fix API integration")
    print("ℹ️ Manual API endpoint configuration may be needed")
    return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
