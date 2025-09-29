#!/usr/bin/env python3
"""
Test Current POS System - Test the existing POS forwarding in barcode scanner
"""

import os
import sys
import time
from pathlib import Path

def test_current_pos_system():
    """Test the POS system that's currently integrated in barcode_scanner_app.py"""
    print("🔧 Testing Current POS System Integration")
    print("=" * 45)
    
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent / 'src'))
    
    # Test 1: Import the current USB HID forwarder
    print("1️⃣ Testing current USB HID forwarder...")
    try:
        from utils.usb_hid_forwarder import get_hid_forwarder
        
        hid_forwarder = get_hid_forwarder()
        print("✅ USB HID forwarder imported successfully")
        
        # Show available methods
        methods = hid_forwarder.available_methods
        print(f"📊 Available methods: {', '.join(methods)}")
        
        # Test with a barcode
        test_barcode = "8053734093444"  # Same as in your log
        print(f"\n🧪 Testing with barcode: {test_barcode}")
        
        success = hid_forwarder.forward_barcode(test_barcode)
        if success:
            print("✅ POS forwarding: SUCCESS")
        else:
            print("❌ POS forwarding: FAILED")
            
        return success
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_pos_methods_individually():
    """Test each POS method individually"""
    print("\n2️⃣ Testing individual POS methods...")
    
    try:
        from utils.usb_hid_forwarder import USBHIDForwarder
        
        forwarder = USBHIDForwarder()
        test_barcode = "TEST987654321"
        
        # Test each method
        methods_to_test = [
            ('USB_HID', forwarder._forward_via_usb_hid),
            ('SERIAL', forwarder._forward_via_serial),
            ('NETWORK', forwarder._forward_via_network),
            ('CLIPBOARD', forwarder._forward_via_clipboard),
            ('FILE', forwarder._forward_via_file)
        ]
        
        results = {}
        
        for method_name, method_func in methods_to_test:
            try:
                print(f"  Testing {method_name}...")
                success = method_func(test_barcode)
                results[method_name] = success
                status = "✅ SUCCESS" if success else "❌ FAILED"
                print(f"    {method_name}: {status}")
            except Exception as e:
                results[method_name] = False
                print(f"    {method_name}: ❌ ERROR - {e}")
        
        working_methods = [k for k, v in results.items() if v]
        print(f"\n📊 Working methods: {', '.join(working_methods) if working_methods else 'None'}")
        
        return len(working_methods) > 0
        
    except Exception as e:
        print(f"❌ Individual test failed: {e}")
        return False

def simulate_barcode_scan():
    """Simulate what happens when you scan a barcode"""
    print("\n3️⃣ Simulating barcode scan process...")
    
    try:
        # This simulates the exact code from your barcode_scanner_app.py
        from utils.usb_hid_forwarder import get_hid_forwarder
        
        hid_forwarder = get_hid_forwarder()
        barcode = "8053734093444"  # From your log
        
        print(f"📝 Simulating scan of barcode: {barcode}")
        
        # Only forward actual product barcodes, not test/device barcodes
        if len(barcode) >= 8 and barcode not in ["817994ccfe14", "36928f67f397"]:
            print("✅ Barcode passes filter (not test/device barcode)")
            
            pos_forwarded = hid_forwarder.forward_barcode(barcode)
            pos_status = "✅ Sent to POS" if pos_forwarded else "⚠️ POS forward failed"
            
            print(f"📤 POS forwarding result: {pos_status}")
            
            return pos_forwarded
        else:
            print("⚠️ Barcode filtered out (test/device barcode)")
            return False
            
    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        return False

def check_pos_files():
    """Check if POS forwarding created any files"""
    print("\n4️⃣ Checking for POS output files...")
    
    # Files that the POS forwarder might create
    pos_files = [
        '/tmp/pos_barcode.txt',
        '/tmp/latest_barcode.txt',
        '/tmp/current_barcode.txt',
        '/var/log/pos_barcodes.log'
    ]
    
    found_files = []
    
    for file_path in pos_files:
        if os.path.exists(file_path):
            found_files.append(file_path)
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    lines = len(content.split('\n'))
                    print(f"  ✅ {file_path} ({lines} lines)")
                    
                    # Show last few lines
                    if content.strip():
                        last_lines = content.strip().split('\n')[-2:]
                        for line in last_lines:
                            if line.strip():
                                print(f"    📄 {line[:80]}...")
            except Exception as e:
                print(f"  ⚠️ {file_path} (cannot read: {e})")
        else:
            print(f"  ❌ {file_path} (not found)")
    
    return len(found_files) > 0

def main():
    """Main test function"""
    print("🧪 Current POS System Test")
    print("This tests the POS forwarding that's already in your barcode scanner")
    
    # Run tests
    test1 = test_current_pos_system()
    test2 = test_pos_methods_individually() 
    test3 = simulate_barcode_scan()
    test4 = check_pos_files()
    
    # Summary
    print("\n" + "=" * 45)
    print("🎯 TEST SUMMARY")
    print("=" * 45)
    
    tests = [
        ("Current POS system", test1),
        ("Individual methods", test2), 
        ("Barcode scan simulation", test3),
        ("POS output files", test4)
    ]
    
    passed = 0
    for test_name, result in tests:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(tests)} tests passed")
    
    if passed >= 2:
        print("\n🎉 POS forwarding is working!")
        print("📋 Your scanned barcodes should appear on attached devices")
        print("📋 Check /tmp/ files for barcode output")
    else:
        print("\n⚠️ POS forwarding needs attention")
        print("📋 Try connecting a device via USB or serial")
        print("📋 Check system logs for errors")
    
    # Show what to do next
    print(f"\n📋 Next steps:")
    print(f"  1. Connect your POS device to Raspberry Pi")
    print(f"  2. Run the barcode scanner service")
    print(f"  3. Scan a barcode and check if it appears on attached device")
    print(f"  4. Check files in /tmp/ for barcode output")

if __name__ == "__main__":
    main()
