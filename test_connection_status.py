#!/usr/bin/env python3
"""
Test script to verify connection manager Pi status reporting
"""
import sys
import os
import logging
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.utils.connection_manager import ConnectionManager
from src.utils.config import load_config

def test_connection_status():
    """Test connection manager Pi status reporting"""
    print("Testing Connection Manager Pi Status Reporting...")
    
    # Load configuration
    config = load_config()
    print(f"Configuration loaded: {config.get('raspberry_pi', {})}")
    
    # Create connection manager
    conn_manager = ConnectionManager()
    
    # Test initial status
    print("\n=== Initial Status Check ===")
    pi_available = conn_manager.check_raspberry_pi_availability()
    print(f"Pi available: {pi_available}")
    
    # Test connection status
    connection_status = conn_manager.get_connection_status()
    print(f"Connection status: {connection_status}")
    
    # Force a refresh and check again
    print("\n=== Forcing Refresh ===")
    pi_available = conn_manager.check_raspberry_pi_availability(force_check=True)
    print(f"Pi available (forced check): {pi_available}")
    
    connection_status = conn_manager.get_connection_status()
    print(f"Connection status after refresh: {connection_status}")
    
    # Check if configured IP is being used properly
    if config and config.get("raspberry_pi", {}).get("auto_detected_ip"):
        configured_ip = config["raspberry_pi"]["auto_detected_ip"]
        print(f"\n=== Testing Configured Pi IP ({configured_ip}) ===")
        connectivity = conn_manager._test_real_pi_connectivity(configured_ip)
        print(f"Configured Pi connectivity: {connectivity}")
        
        # Test LAN check specifically
        lan_check = conn_manager._fallback_lan_pi_check()
        print(f"Fallback LAN check result: {lan_check}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_connection_status()