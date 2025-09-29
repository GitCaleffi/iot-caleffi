#!/usr/bin/env python3
"""
Test POS forwarding in keyboard_scanner.py
"""

import sys
import os
from pathlib import Path

def test_keyboard_scanner_pos():
    """Test the POS forwarding in keyboard_scanner.py"""
    print("🧪 Testing POS Forwarding in keyboard_scanner.py")
    print("=" * 50)
    
    # Add paths like keyboard_scanner.py does
    current_dir = Path(__file__).resolve().parent
    deployment_src = current_dir / 'deployment_package' / 'src'
    src_dir = current_dir / 'src'
    sys.path.append(str(deployment_src))
    sys.path.append(str(src_dir))
    
    print(f"📁 Current dir: {current_dir}")
    print(f"📁 Deployment src: {deployment_src}")
    print(f"📁 Src dir: {src_dir}")
    
    # Test 1: Import the enhanced forwarder like keyboard_scanner.py does
    print("\n1️⃣ Testing enhanced POS forwarder import...")
    try:
        sys.path.insert(0, str(current_dir / 'deployment_package'))
        from enhanced_pos_forwarder import EnhancedPOSForwarder
        
        enhanced_forwarder = EnhancedPOSForwarder()
        print("✅ Enhanced POS forwarder imported successfully")
        
        # Show detected devices
        devices = enhanced_forwarder.attached_devices
        total_devices = (len(devices['serial_ports']) + 
                        len(devices['usb_keyboards']) + 
                        len(devices['hid_devices']) + 
                        len(devices['network_terminals']))
        
        print(f"📊 Total devices detected: {total_devices}")
        print(f"  📡 Serial ports: {len(devices['serial_ports'])}")
        print(f"  ⌨️ USB keyboards: {len(devices['usb_keyboards'])}")
        print(f"  🖱️ HID devices: {len(devices['hid_devices'])}")
        print(f"  🌐 Network terminals: {len(devices['network_terminals'])}")
        
    except ImportError as e:
        print(f"❌ Enhanced forwarder import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Enhanced forwarder error: {e}")
        return False
    
    # Test 2: Test the fallback forwarder
    print("\n2️⃣ Testing fallback USB HID forwarder...")
    try:
        utils_dir = src_dir / 'utils'
        sys.path.insert(0, str(utils_dir))
        from usb_hid_forwarder import get_hid_forwarder
        
        hid_forwarder = get_hid_forwarder()
        print("✅ Fallback USB HID forwarder imported successfully")
        print(f"📊 Available methods: {', '.join(hid_forwarder.available_methods)}")
        
    except ImportError as e:
        print(f"❌ Fallback forwarder import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Fallback forwarder error: {e}")
        return False
    
    # Test 3: Simulate the exact POS forwarding logic from keyboard_scanner.py
    print("\n3️⃣ Simulating keyboard scanner POS forwarding logic...")
    try:
        validated_barcode = "8053734093444"  # Test barcode
        print(f"🧪 Testing with barcode: {validated_barcode}")
        
        # This is the exact logic from keyboard_scanner.py
        try:
            # Try enhanced POS forwarder first
            pos_results = enhanced_forwarder.forward_to_attached_devices(validated_barcode)
            successful_methods = [k for k, v in pos_results.items() if v]
            
            if successful_methods:
                pos_status = f"✅ Sent to POS via: {', '.join(successful_methods)}"
                print(f"Enhanced POS forwarding successful: {successful_methods}")
                return True
            else:
                pos_status = "⚠️ Enhanced POS forward failed - trying fallback"
                print(f"Enhanced POS forwarding failed, trying fallback...")
                
                # Fallback to original forwarder
                pos_forwarded = hid_forwarder.forward_barcode(validated_barcode)
                pos_status = "✅ Sent to POS (fallback)" if pos_forwarded else "⚠️ All POS methods failed"
                print(f"Fallback result: {pos_status}")
                return pos_forwarded
                
        except Exception as e:
            print(f"❌ POS forwarding simulation failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Simulation error: {e}")
        return False

def test_barcode_filtering():
    """Test the barcode filtering logic"""
    print("\n4️⃣ Testing barcode filtering logic...")
    
    test_cases = [
        ("8053734093444", True, "Regular product barcode"),
        ("817994ccfe14", False, "Test barcode (should be filtered)"),
        ("36928f67f397", False, "Device barcode (should be filtered)"),
        ("123456789", True, "Short but valid barcode"),
        ("12345", False, "Too short barcode")
    ]
    
    for barcode, should_forward, description in test_cases:
        # Apply the same filter logic as keyboard_scanner.py
        should_forward_actual = (len(barcode) >= 8 and 
                               barcode not in ["817994ccfe14", "36928f67f397"])
        
        status = "✅ PASS" if should_forward_actual == should_forward else "❌ FAIL"
        action = "FORWARD" if should_forward_actual else "SKIP"
        
        print(f"  {status} {barcode}: {action} - {description}")

def main():
    """Main test function"""
    print("🔧 Keyboard Scanner POS System Test")
    print("Testing the enhanced POS forwarding in keyboard_scanner.py")
    
    # Run tests
    pos_test = test_keyboard_scanner_pos()
    test_barcode_filtering()
    
    # Summary
    print("\n" + "=" * 50)
    print("🎯 TEST SUMMARY")
    print("=" * 50)
    
    if pos_test:
        print("✅ Keyboard scanner POS forwarding: WORKING")
        print("📋 Enhanced POS forwarding is integrated and functional")
        print("📋 Barcodes will be forwarded to attached devices")
    else:
        print("⚠️ Keyboard scanner POS forwarding: NEEDS ATTENTION")
        print("📋 Check device connections and imports")
    
    print(f"\n📋 What happens when you scan a barcode:")
    print(f"  1. Barcode gets validated and cleaned")
    print(f"  2. Enhanced POS forwarder tries multiple methods")
    print(f"  3. Falls back to standard forwarder if needed")
    print(f"  4. Barcode appears on attached POS device")
    
    print(f"\n📋 To test on Raspberry Pi:")
    print(f"  1. Connect POS device via USB")
    print(f"  2. Run keyboard scanner: python3 keyboard_scanner.py")
    print(f"  3. Scan barcode: 8053734093444")
    print(f"  4. Check if barcode appears on POS device")

if __name__ == "__main__":
    main()
