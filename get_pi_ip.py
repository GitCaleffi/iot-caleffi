#!/usr/bin/env python3
"""
Simple utility to get Raspberry Pi IP address with guaranteed fallback
"""

import sys
import os
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from src.barcode_scanner_app import get_primary_raspberry_pi_ip, get_known_raspberry_pi_ip, get_static_raspberry_pi_ip, auto_connect_to_raspberry_pi

def main():
    """Get Raspberry Pi IP address with multiple fallback methods"""
    print("🍓 Raspberry Pi IP Address Detector")
    print("=" * 40)
    
    # Method 1: Try full discovery
    print("\n🔍 Method 1: Full Network Discovery")
    try:
        primary_ip = get_primary_raspberry_pi_ip()
        if primary_ip:
            print(f"✅ Primary IP found: {primary_ip}")
            return primary_ip
        else:
            print("❌ Full discovery failed")
    except Exception as e:
        print(f"❌ Full discovery error: {e}")
    
    # Method 2: Try known IP with validation
    print("\n🎯 Method 2: Known IP with Validation")
    try:
        known_ip = get_known_raspberry_pi_ip()
        if known_ip:
            print(f"✅ Known IP confirmed: {known_ip}")
            return known_ip
        else:
            print("❌ Known IP validation failed")
    except Exception as e:
        print(f"❌ Known IP validation error: {e}")
    
    # Method 3: Static IP (guaranteed)
    print("\n📍 Method 3: Static IP (Guaranteed)")
    try:
        static_ip = get_static_raspberry_pi_ip()
        print(f"✅ Static IP: {static_ip}")
        return static_ip
    except Exception as e:
        print(f"❌ Static IP error: {e}")
        return None
    
def test_auto_connection():
    """Test the auto-connection functionality"""
    print("\n🔗 Testing Auto-Connection")
    print("=" * 30)
    
    try:
        result = auto_connect_to_raspberry_pi()
        if result['success']:
            print(f"✅ Auto-connection successful!")
            print(f"   IP: {result['ip']}")
            print(f"   Message: {result['message']}")
        else:
            print(f"❌ Auto-connection failed:")
            print(f"   Message: {result['message']}")
        
        return result
    except Exception as e:
        print(f"❌ Auto-connection error: {e}")
        return None

if __name__ == "__main__":
    # Get the Pi IP
    pi_ip = main()
    
    if pi_ip:
        print(f"\n🎉 RESULT: Your Raspberry Pi IP is {pi_ip}")
        
        # Test auto-connection
        test_auto_connection()
        
        print(f"\n💡 Usage in your code:")
        print(f"   from barcode_scanner_app import get_primary_raspberry_pi_ip")
        print(f"   pi_ip = get_primary_raspberry_pi_ip()  # Returns: '{pi_ip}'")
        
    else:
        print("\n❌ Could not determine Raspberry Pi IP address")
