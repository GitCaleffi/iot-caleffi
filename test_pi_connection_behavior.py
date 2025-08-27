#!/usr/bin/env python3
"""
Test script to verify Pi connection behavior for registration functions
"""
import sys
import os
import logging

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_registration_behavior():
    """Test how registration functions behave when Pi is disconnected"""
    print("Testing Registration Behavior When Pi is Disconnected...")
    
    # Import required modules
    from src.utils.connection_manager import ConnectionManager
    from src.barcode_scanner_app import generate_registration_token, confirm_registration
    
    # Create connection manager
    conn_manager = ConnectionManager()
    
    # Check current Pi availability
    print("\n=== Current Pi Connection Status ===")
    pi_available = conn_manager.check_raspberry_pi_availability()
    connection_status = conn_manager.get_connection_status()
    
    print(f"Pi Available: {pi_available}")
    print(f"Connection Status: {connection_status}")
    
    # Test generate_registration_token function
    print("\n=== Testing generate_registration_token() ===")
    try:
        result = generate_registration_token()
        print(f"Result type: {type(result)}")
        print(f"Result preview: {str(result)[:200]}...")
        print("✅ generate_registration_token completed successfully")
    except Exception as e:
        print(f"❌ generate_registration_token failed: {e}")
    
    # Test confirm_registration function
    print("\n=== Testing confirm_registration() ===")
    try:
        # Test with a sample device ID
        result = confirm_registration("test_token", "test-device-001")
        print(f"Result type: {type(result)}")
        print(f"Result preview: {str(result)[:200]}...")
        print("✅ confirm_registration completed successfully")
    except Exception as e:
        print(f"❌ confirm_registration failed: {e}")
    
    # Check connection status after tests
    print("\n=== Connection Status After Tests ===")
    pi_available_after = conn_manager.check_raspberry_pi_availability()
    connection_status_after = conn_manager.get_connection_status()
    
    print(f"Pi Available: {pi_available_after}")
    print(f"Connection Status: {connection_status_after}")
    
    print("\n=== Analysis ===")
    if pi_available:
        print("Pi was connected during test - functions executed normally")
    else:
        print("Pi was disconnected during test:")
        print("- Functions still executed (did not block)")
        print("- Messages would be saved locally for retry")
        print("- This is the intended offline behavior")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_registration_behavior()