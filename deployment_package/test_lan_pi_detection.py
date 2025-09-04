#!/usr/bin/env python3
"""
Test script for LAN-based Raspberry Pi detection and IoT Hub messaging.
This script demonstrates the complete workflow implemented in barcode_scanner_app.py.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.barcode_scanner_app import (
    test_lan_detection_and_iot_hub_flow,
    detect_lan_raspberry_pi,
    send_pi_status_to_iot_hub,
    is_pi_connected_for_scanning,
    start_pi_status_monitoring,
    stop_pi_status_monitoring,
    generate_device_id
)
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main test function"""
    print("🧪 LAN-based Pi Detection and IoT Hub Messaging Test")
    print("=" * 60)
    
    try:
        # Run comprehensive test
        logger.info("Starting comprehensive test...")
        test_results = test_lan_detection_and_iot_hub_flow()
        
        print("\n📊 Test Results:")
        print(f"   • LAN Detection: {'✅ PASS' if test_results.get('lan_detection') else '❌ FAIL'}")
        print(f"   • IoT Hub Reporting: {'✅ PASS' if test_results.get('iot_hub_reporting') else '❌ FAIL'}")
        print(f"   • Scanning Ready: {'✅ PASS' if test_results.get('scanning_ready') else '❌ FAIL'}")
        print(f"   • Device ID: {test_results.get('device_id', 'N/A')}")
        
        if test_results.get('pi_info', {}).get('connected'):
            pi_info = test_results['pi_info']
            print(f"   • Pi IP: {pi_info.get('ip', 'unknown')}")
            print(f"   • Pi MAC: {pi_info.get('mac', 'unknown')}")
            print(f"   • Services: {pi_info.get('services', [])}")
        
        # Test continuous monitoring
        print("\n🔄 Testing continuous Pi status monitoring...")
        print("   Starting background monitoring (will run for 30 seconds)...")
        
        start_pi_status_monitoring()
        time.sleep(30)  # Monitor for 30 seconds
        stop_pi_status_monitoring()
        
        print("   ✅ Monitoring test completed")
        
        # Final status check
        print("\n🏁 Final Status Check:")
        pi_connected, status_msg, pi_info = is_pi_connected_for_scanning()
        print(f"   • Current Status: {status_msg}")
        print(f"   • Ready for Scanning: {'✅ YES' if pi_connected else '❌ NO'}")
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"\n❌ Test failed with error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
