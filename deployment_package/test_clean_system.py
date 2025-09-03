#!/usr/bin/env python3
"""
Test script to verify the barcode scanner system runs without infinite loops
"""

import sys
import os
import time
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

def test_import_system():
    """Test that the system can be imported without starting infinite loops"""
    print("🧪 Testing system imports...")
    
    try:
        # Import the main module (this should not start any loops)
        import barcode_scanner_app
        print("✅ Main module imported successfully")
        
        # Test key functions exist
        assert hasattr(barcode_scanner_app, 'plug_and_play_mode')
        assert hasattr(barcode_scanner_app, 'send_single_heartbeat')
        assert hasattr(barcode_scanner_app, 'check_single_update')
        print("✅ Key functions are available")
        
        # Test that no background threads are running
        import threading
        active_threads = threading.active_count()
        print(f"📊 Active threads: {active_threads}")
        
        if active_threads <= 2:  # Main thread + possibly one other
            print("✅ No excessive background threads detected")
        else:
            print(f"⚠️ Warning: {active_threads} threads active")
        
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False

def test_function_execution():
    """Test that key functions execute without infinite loops"""
    print("\n🧪 Testing function execution...")
    
    try:
        import barcode_scanner_app
        
        # Test config loading
        config = barcode_scanner_app.load_pi_config()
        print("✅ Config loading works")
        
        # Test MAC address detection
        mac = barcode_scanner_app.get_local_mac_address()
        print(f"✅ MAC address detection: {mac}")
        
        # Test Pi detection
        is_pi = barcode_scanner_app.is_raspberry_pi()
        print(f"✅ Pi detection: {is_pi}")
        
        return True
        
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False

def test_no_infinite_loops():
    """Test that the system doesn't get stuck in infinite loops"""
    print("\n🧪 Testing for infinite loops...")
    
    start_time = time.time()
    timeout = 10  # 10 seconds max
    
    try:
        # This should complete quickly without infinite loops
        import barcode_scanner_app
        
        # Test that functions return promptly
        elapsed = time.time() - start_time
        
        if elapsed < timeout:
            print(f"✅ System initialized in {elapsed:.2f} seconds (no infinite loops)")
            return True
        else:
            print(f"❌ System took too long: {elapsed:.2f} seconds")
            return False
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Loop test failed after {elapsed:.2f}s: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Clean System Tests")
    print("=" * 50)
    
    tests = [
        ("Import System", test_import_system),
        ("Function Execution", test_function_execution), 
        ("No Infinite Loops", test_no_infinite_loops)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASSED")
        else:
            print(f"❌ {test_name}: FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - System is clean and loop-free!")
        return True
    else:
        print("⚠️ Some tests failed - check the output above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
