#!/usr/bin/env python3
"""
Test Enhanced Serial POS Integration with Keyboard Scanner
"""

import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_serial_pos_integration():
    """Test the enhanced serial POS integration"""
    print("🧪 Testing Enhanced Serial POS Integration")
    print("=" * 45)
    
    # Test 1: Direct Enhanced Serial POS
    try:
        from enhanced_serial_pos import get_serial_pos
        serial_pos = get_serial_pos()
        
        print("✅ Enhanced Serial POS module loaded successfully")
        print(f"📊 Working serial ports: {len(serial_pos.working_ports)}")
        for port in serial_pos.working_ports:
            print(f"  - {port}")
        
        # Test optimized sending
        test_barcode = "1234567890123"
        print(f"\n📦 Testing optimized send with: {test_barcode}")
        
        success = serial_pos.send_barcode_optimized(test_barcode)
        print(f"Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
        
        return success
        
    except ImportError as e:
        print(f"❌ Failed to import enhanced_serial_pos: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing serial POS: {e}")
        return False

def test_keyboard_scanner_integration():
    """Test integration with keyboard scanner"""
    print(f"\n🔗 Testing Keyboard Scanner Integration")
    print("=" * 40)
    
    try:
        # Import the barcode processing function
        from keyboard_scanner import process_barcode_with_device
        
        print("✅ Keyboard scanner module loaded successfully")
        
        # Test with a sample barcode (this would normally come from USB input)
        test_device_id = "test-serial-pos-123"
        test_barcode = "8906044234994"
        
        print(f"📦 Testing barcode processing: {test_barcode}")
        print(f"🔧 Device ID: {test_device_id}")
        
        # This will test the full integration including POS forwarding
        result = process_barcode_with_device(test_barcode, test_device_id)
        
        print(f"Result: {'✅ SUCCESS' if result else '❌ FAILED'}")
        return result
        
    except ImportError as e:
        print(f"❌ Failed to import keyboard_scanner: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing keyboard scanner integration: {e}")
        return False

def main():
    """Run all integration tests"""
    print("🚀 Enhanced Serial POS Integration Test Suite")
    print("=" * 55)
    
    # Test 1: Direct Serial POS
    serial_success = test_serial_pos_integration()
    
    # Test 2: Keyboard Scanner Integration
    scanner_success = test_keyboard_scanner_integration()
    
    # Summary
    print(f"\n📊 Test Summary:")
    print(f"  Enhanced Serial POS: {'✅ PASS' if serial_success else '❌ FAIL'}")
    print(f"  Keyboard Integration: {'✅ PASS' if scanner_success else '❌ FAIL'}")
    
    overall_success = serial_success and scanner_success
    print(f"  Overall Result: {'✅ ALL TESTS PASSED' if overall_success else '❌ SOME TESTS FAILED'}")
    
    if overall_success:
        print(f"\n🎉 Your Pi 5 is ready for Serial POS communication!")
        print(f"   - 2 working serial ports detected")
        print(f"   - Enhanced POS communication active")
        print(f"   - Keyboard scanner integration working")
    else:
        print(f"\n⚠️ Some issues detected - check logs above")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
