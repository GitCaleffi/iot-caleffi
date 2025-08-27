#!/usr/bin/env python3
"""
Test script for the optimized fast barcode scanner system
Tests automatic configuration, device detection, and API speed
"""
import sys
import time
import asyncio
import logging
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))

def test_fast_config_manager():
    """Test automatic config detection and loading"""
    print("🔧 Testing Fast Config Manager...")
    
    try:
        from utils.fast_config_manager import get_fast_config_manager, get_config, get_device_status
        
        # Test config manager initialization
        config_manager = get_fast_config_manager()
        print(f"✅ Config auto-detected: {config_manager.is_auto_detected()}")
        print(f"✅ Config path: {config_manager.get_config_path()}")
        
        # Test config loading speed
        start_time = time.time()
        config = get_config()
        load_time = (time.time() - start_time) * 1000
        print(f"⚡ Config loaded in {load_time:.1f}ms")
        
        # Test device status detection
        start_time = time.time()
        device_status = get_device_status()
        status_time = (time.time() - start_time) * 1000
        print(f"📱 Device status ({device_status}) detected in {status_time:.1f}ms")
        
        # Test performance settings
        performance = config.get("performance", {})
        print(f"🚀 Fast mode: {performance.get('fast_mode', False)}")
        print(f"⚡ Parallel processing: {performance.get('parallel_processing', False)}")
        print(f"🗄️ Cache duration: {performance.get('cache_duration', 0)}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Fast Config Manager test failed: {e}")
        return False

def test_fast_api_handler():
    """Test fast API handler performance"""
    print("\n🚀 Testing Fast API Handler...")
    
    try:
        from utils.fast_api_handler import get_fast_api_handler
        
        # Initialize handler
        api_handler = get_fast_api_handler()
        print("✅ Fast API Handler initialized")
        
        # Test system status
        start_time = time.time()
        status = api_handler.get_system_status_fast()
        status_time = (time.time() - start_time) * 1000
        print(f"📊 System status retrieved in {status_time:.1f}ms")
        
        # Display status
        print(f"✅ Config auto-detected: {status.get('config_auto_detected', False)}")
        print(f"📱 Device connected: {status.get('device_connected', False)}")
        print(f"⚡ Fast mode enabled: {status.get('fast_mode_enabled', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Fast API Handler test failed: {e}")
        return False

async def test_fast_barcode_processing():
    """Test fast barcode processing speed"""
    print("\n⚡ Testing Fast Barcode Processing...")
    
    try:
        from utils.fast_api_handler import get_fast_api_handler
        
        api_handler = get_fast_api_handler()
        
        # Test barcodes
        test_barcodes = [
            ("1234567890123", "test-device-001"),
            ("9876543210987", "test-device-002"),
            ("abc123def456", "test-device-003")
        ]
        
        total_time = 0
        successful_tests = 0
        
        for barcode, device_id in test_barcodes:
            print(f"🔍 Testing barcode: {barcode}")
            
            start_time = time.time()
            result = await api_handler.process_barcode_fast(barcode, device_id)
            processing_time = (time.time() - start_time) * 1000
            total_time += processing_time
            
            if result.get("success"):
                successful_tests += 1
                print(f"✅ Processed in {processing_time:.1f}ms")
                print(f"   Device connected: {result.get('device_connected', False)}")
                print(f"   IoT Hub: {result.get('iot_hub_result', {}).get('success', False)}")
                print(f"   API: {result.get('api_result', {}).get('success', False)}")
            else:
                print(f"⚠️ Failed in {processing_time:.1f}ms: {result.get('message', 'Unknown error')}")
        
        avg_time = total_time / len(test_barcodes)
        print(f"\n📊 Performance Summary:")
        print(f"   Successful tests: {successful_tests}/{len(test_barcodes)}")
        print(f"   Average processing time: {avg_time:.1f}ms")
        print(f"   Total time: {total_time:.1f}ms")
        
        return successful_tests > 0
        
    except Exception as e:
        print(f"❌ Fast barcode processing test failed: {e}")
        return False

def test_automatic_features():
    """Test automatic configuration features"""
    print("\n🤖 Testing Automatic Features...")
    
    try:
        # Test automatic device ID generation
        from utils.dynamic_device_id import generate_dynamic_device_id
        device_id = generate_dynamic_device_id()
        print(f"🔧 Auto-generated device ID: {device_id}")
        
        # Test automatic config updates
        from utils.fast_config_manager import get_fast_config_manager
        config_manager = get_fast_config_manager()
        
        # Test config update
        updates = {
            "performance": {
                "last_test": time.time(),
                "test_status": "passed"
            }
        }
        
        update_success = config_manager.update_config(updates)
        print(f"📝 Config update: {'✅ Success' if update_success else '❌ Failed'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Automatic features test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Fast Barcode Scanner System Tests")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.WARNING)  # Reduce noise during testing
    
    test_results = []
    
    # Run tests
    test_results.append(("Fast Config Manager", test_fast_config_manager()))
    test_results.append(("Fast API Handler", test_fast_api_handler()))
    
    # Run async test
    try:
        result = asyncio.run(test_fast_barcode_processing())
        test_results.append(("Fast Barcode Processing", result))
    except Exception as e:
        print(f"❌ Async test failed: {e}")
        test_results.append(("Fast Barcode Processing", False))
    
    test_results.append(("Automatic Features", test_automatic_features()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for fast operation.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
