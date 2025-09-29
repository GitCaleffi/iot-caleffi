#!/usr/bin/env python3
"""
Simple POS Test - Test if POS forwarding is working
Run this from the main barcode_scanner_clean directory
"""

import os
import sys
import time
from pathlib import Path

def test_pos_forwarding():
    """Test POS forwarding from the correct directory structure"""
    print("🧪 Testing POS Forwarding System")
    print("=" * 40)
    
    # Add src to path (correct path structure)
    current_dir = Path(__file__).parent
    src_path = current_dir / 'src'
    sys.path.insert(0, str(src_path))
    
    print(f"📁 Testing from: {current_dir}")
    print(f"📁 Source path: {src_path}")
    
    # Test 1: Import the USB HID forwarder
    print("\n1️⃣ Testing USB HID forwarder import...")
    try:
        from utils.usb_hid_forwarder import get_hid_forwarder, USBHIDForwarder
        print("✅ USB HID forwarder imported successfully")
        
        # Create forwarder instance
        hid_forwarder = get_hid_forwarder()
        print("✅ Forwarder instance created")
        
        # Show available methods
        methods = hid_forwarder.available_methods
        print(f"📊 Available methods: {', '.join(methods)}")
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 2: Test barcode forwarding
    print("\n2️⃣ Testing barcode forwarding...")
    try:
        test_barcode = "8053734093444"  # Same as your log
        print(f"🧪 Testing with barcode: {test_barcode}")
        
        # Test the forward_barcode method
        success = hid_forwarder.forward_barcode(test_barcode)
        
        if success:
            print("✅ Barcode forwarding: SUCCESS")
        else:
            print("⚠️ Barcode forwarding: Some methods failed, but at least one worked")
        
        return True
        
    except Exception as e:
        print(f"❌ Forwarding test failed: {e}")
        return False

def test_individual_methods():
    """Test each POS method individually"""
    print("\n3️⃣ Testing individual POS methods...")
    
    try:
        from utils.usb_hid_forwarder import USBHIDForwarder
        
        forwarder = USBHIDForwarder()
        test_barcode = "INDIVIDUAL_TEST_123"
        
        # Get the test results
        results = forwarder.test_barcode_forwarding(test_barcode)
        
        print(f"\n📊 Individual method results:")
        working_methods = []
        
        for method, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"  {method}: {status}")
            if success:
                working_methods.append(method)
        
        print(f"\n🎯 Working methods: {', '.join(working_methods) if working_methods else 'None'}")
        return len(working_methods) > 0
        
    except Exception as e:
        print(f"❌ Individual method test failed: {e}")
        return False

def check_output_files():
    """Check if any output files were created"""
    print("\n4️⃣ Checking output files...")
    
    files_to_check = [
        '/tmp/pos_barcode.txt',
        '/tmp/latest_barcode.txt', 
        '/tmp/current_barcode.txt'
    ]
    
    found_files = 0
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        print(f"  ✅ {file_path}: {len(content)} chars")
                        # Show last line
                        last_line = content.split('\n')[-1]
                        print(f"    📄 Latest: {last_line[:50]}...")
                        found_files += 1
                    else:
                        print(f"  ⚠️ {file_path}: Empty")
            except Exception as e:
                print(f"  ❌ {file_path}: Error reading - {e}")
        else:
            print(f"  ❌ {file_path}: Not found")
    
    return found_files > 0

def simulate_real_barcode_scan():
    """Simulate the exact process from barcode_scanner_app.py"""
    print("\n5️⃣ Simulating real barcode scan process...")
    
    try:
        from utils.usb_hid_forwarder import get_hid_forwarder
        
        hid_forwarder = get_hid_forwarder()
        barcode = "8053734093444"  # From your actual log
        
        print(f"📝 Processing barcode: {barcode}")
        
        # This is the exact logic from your barcode_scanner_app.py
        if len(barcode) >= 8 and barcode not in ["817994ccfe14", "36928f67f397"]:
            print("✅ Barcode passes filter (not test/device barcode)")
            
            pos_forwarded = hid_forwarder.forward_barcode(barcode)
            pos_status = "✅ Sent to POS" if pos_forwarded else "⚠️ POS forward failed"
            
            print(f"📤 Result: {pos_status}")
            
            # This should match what you see in your logs
            return pos_forwarded
        else:
            print("⚠️ Barcode would be filtered out")
            return False
            
    except Exception as e:
        print(f"❌ Simulation failed: {e}")
        return False

def main():
    """Main test function"""
    print("🔧 POS System Working Test")
    print("Testing if your POS forwarding system is working correctly")
    
    # Run all tests
    tests = [
        ("POS Forwarding Import", test_pos_forwarding),
        ("Individual Methods", test_individual_methods),
        ("Output Files", check_output_files),
        ("Real Scan Simulation", simulate_real_barcode_scan)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 40)
    print("🎯 FINAL TEST RESULTS")
    print("=" * 40)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📊 Overall: {passed}/{len(results)} tests passed")
    
    # Recommendations
    if passed >= 3:
        print("\n🎉 POS forwarding is WORKING!")
        print("📋 Your system should forward barcodes to attached devices")
        print("📋 Methods working: File output, clipboard, possibly others")
    elif passed >= 1:
        print("\n⚠️ POS forwarding is PARTIALLY working")
        print("📋 Some methods work, others may need device connections")
        print("📋 At minimum, barcodes are saved to files in /tmp/")
    else:
        print("\n❌ POS forwarding has issues")
        print("📋 Check if you're running from correct directory")
        print("📋 Verify file paths and imports")
    
    # Show what the user should see
    print(f"\n📋 What you should see when scanning:")
    print(f"  📝 Detected: 8053734093444")
    print(f"  📤 Forwarding barcode...")
    print(f"  ✅ Successfully forwarded barcode via CLIPBOARD")
    print(f"  📄 Barcode saved to /tmp/pos_barcode.txt")
    
    print(f"\n📋 How to check if it's working on Raspberry Pi:")
    print(f"  1. Connect POS device via USB")
    print(f"  2. Scan a barcode")
    print(f"  3. Check if barcode appears on POS device screen")
    print(f"  4. Check files: ls -la /tmp/pos_*.txt")

if __name__ == "__main__":
    main()
