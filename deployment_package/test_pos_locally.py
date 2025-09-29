#!/usr/bin/env python3
"""
Local POS Forwarding Test Script
Test POS forwarding without needing to copy files to Raspberry Pi
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def test_pos_methods():
    """Test all available POS forwarding methods locally"""
    print("🧪 Testing POS Forwarding Methods Locally")
    print("=" * 50)
    
    # Test 1: Check if we can import the enhanced forwarder
    print("\n1️⃣ Testing Enhanced POS Forwarder Import...")
    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from enhanced_pos_forwarder import EnhancedPOSForwarder
        print("✅ Enhanced POS Forwarder imported successfully")
        
        # Create forwarder instance
        forwarder = EnhancedPOSForwarder()
        print(f"✅ Forwarder initialized")
        
        # Show detected devices
        devices = forwarder.attached_devices
        print(f"\n📊 Detected Devices:")
        print(f"  📡 Serial ports: {len(devices['serial_ports'])}")
        for port in devices['serial_ports']:
            print(f"    - {port}")
        print(f"  ⌨️ USB keyboards: {len(devices['usb_keyboards'])}")
        print(f"  🖱️ HID devices: {len(devices['hid_devices'])}")
        print(f"  🌐 Network terminals: {len(devices['network_terminals'])}")
        
    except ImportError as e:
        print(f"❌ Failed to import enhanced forwarder: {e}")
        return False
    except Exception as e:
        print(f"❌ Error initializing forwarder: {e}")
        return False
    
    # Test 2: Test individual forwarding methods
    print("\n2️⃣ Testing Individual POS Methods...")
    test_barcode = "TEST123456789"
    
    try:
        results = forwarder.test_all_methods(test_barcode)
        
        print(f"\n📊 Test Results for barcode: {test_barcode}")
        working_methods = []
        failed_methods = []
        
        for method, success in results.items():
            if success:
                working_methods.append(method)
                print(f"  ✅ {method}: SUCCESS")
            else:
                failed_methods.append(method)
                print(f"  ❌ {method}: FAILED")
        
        print(f"\n🎯 Summary:")
        print(f"  ✅ Working methods: {len(working_methods)}")
        print(f"  ❌ Failed methods: {len(failed_methods)}")
        
        return len(working_methods) > 0
        
    except Exception as e:
        print(f"❌ Error testing methods: {e}")
        return False

def test_standard_forwarder():
    """Test the standard USB HID forwarder"""
    print("\n3️⃣ Testing Standard USB HID Forwarder...")
    
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'src'))
        from utils.usb_hid_forwarder import USBHIDForwarder
        
        forwarder = USBHIDForwarder()
        print("✅ Standard forwarder imported successfully")
        print(f"📊 Available methods: {forwarder.available_methods}")
        
        # Test forwarding
        test_barcode = "STANDARD123456"
        results = forwarder.test_barcode_forwarding(test_barcode)
        
        working = [k for k, v in results.items() if v]
        print(f"✅ Working standard methods: {', '.join(working) if working else 'None'}")
        
        return len(working) > 0
        
    except ImportError as e:
        print(f"❌ Failed to import standard forwarder: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing standard forwarder: {e}")
        return False

def test_system_requirements():
    """Test system requirements for POS forwarding"""
    print("\n4️⃣ Testing System Requirements...")
    
    requirements = {
        'Python serial module': 'import serial',
        'Python requests module': 'import requests', 
        'xclip command': 'which xclip',
        'xsel command': 'which xsel',
        'USB devices': 'lsusb',
        'Serial devices': 'ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || echo "No serial devices"'
    }
    
    results = {}
    
    for name, test_cmd in requirements.items():
        try:
            if test_cmd.startswith('import'):
                # Python import test
                exec(test_cmd)
                results[name] = True
                print(f"  ✅ {name}: Available")
            else:
                # Shell command test
                result = subprocess.run(test_cmd, shell=True, capture_output=True, timeout=5)
                if result.returncode == 0:
                    results[name] = True
                    print(f"  ✅ {name}: Available")
                else:
                    results[name] = False
                    print(f"  ❌ {name}: Not available")
        except Exception as e:
            results[name] = False
            print(f"  ❌ {name}: Error - {e}")
    
    return results

def test_file_forwarding():
    """Test file-based forwarding (always works)"""
    print("\n5️⃣ Testing File-Based Forwarding...")
    
    try:
        test_barcode = "FILE123456789"
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Test file locations
        file_locations = [
            '/tmp/pos_barcode.txt',
            '/tmp/latest_barcode.txt',
            '/tmp/current_barcode.txt'
        ]
        
        success_count = 0
        
        for file_path in file_locations:
            try:
                with open(file_path, 'w') as f:
                    f.write(f"{timestamp}: {test_barcode}\n")
                
                # Verify file was written
                if os.path.exists(file_path):
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if test_barcode in content:
                            print(f"  ✅ {file_path}: SUCCESS")
                            success_count += 1
                        else:
                            print(f"  ❌ {file_path}: Content mismatch")
                else:
                    print(f"  ❌ {file_path}: File not created")
                    
            except Exception as e:
                print(f"  ❌ {file_path}: Error - {e}")
        
        print(f"\n📄 File forwarding: {success_count}/{len(file_locations)} locations working")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ File forwarding test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🔧 POS Forwarding System Test")
    print("=" * 40)
    print("This test checks if POS forwarding will work on your system")
    
    # Run all tests
    test_results = {}
    
    test_results['enhanced_forwarder'] = test_pos_methods()
    test_results['standard_forwarder'] = test_standard_forwarder()
    test_results['system_requirements'] = test_system_requirements()
    test_results['file_forwarding'] = test_file_forwarding()
    
    # Overall summary
    print("\n" + "=" * 50)
    print("🎯 OVERALL TEST RESULTS")
    print("=" * 50)
    
    working_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
    
    print(f"\n📊 Summary: {working_tests}/{total_tests} tests passed")
    
    if working_tests >= 2:
        print("\n🎉 POS forwarding should work on your system!")
        print("📋 Next steps:")
        print("  1. Connect your POS device via USB or serial")
        print("  2. Run the barcode scanner")
        print("  3. Scan barcodes - they should appear on attached device")
    else:
        print("\n⚠️ POS forwarding may have issues")
        print("📋 Recommendations:")
        print("  1. Install missing requirements: pip3 install pyserial requests")
        print("  2. Install clipboard tools: sudo apt-get install xclip xsel")
        print("  3. Check device connections")
    
    # Show test files created
    print(f"\n📄 Test files created in /tmp/:")
    for file_path in ['/tmp/pos_barcode.txt', '/tmp/latest_barcode.txt', '/tmp/current_barcode.txt']:
        if os.path.exists(file_path):
            print(f"  - {file_path}")

if __name__ == "__main__":
    main()
