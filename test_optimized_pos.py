#!/usr/bin/env python3
"""
Test the optimized POS forwarder integration
"""

import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from optimized_pos_forwarder import OptimizedPOSForwarder

def test_optimized_forwarder():
    """Test the optimized POS forwarder"""
    print("🧪 Testing Optimized POS Forwarder")
    print("=" * 40)
    
    # Create forwarder instance
    forwarder = OptimizedPOSForwarder()
    
    # Test with a sample barcode
    test_barcode = "1234567890123"
    print(f"📦 Testing with barcode: {test_barcode}")
    
    # Forward to working devices
    results = forwarder.forward_to_working_devices(test_barcode)
    
    # Show results
    print(f"\n📊 Test Results:")
    total_devices = len(results)
    successful = sum(1 for success in results.values() if success)
    failed = total_devices - successful
    
    print(f"  Total devices tested: {total_devices}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    
    if successful > 0:
        print(f"\n✅ POS forwarding is working! Successfully sent to {successful} device(s)")
        working_devices = [device for device, success in results.items() if success]
        print(f"Working devices: {', '.join(working_devices)}")
    else:
        print(f"\n⚠️ No devices are working for POS forwarding")
    
    return successful > 0

if __name__ == "__main__":
    success = test_optimized_forwarder()
    sys.exit(0 if success else 1)
