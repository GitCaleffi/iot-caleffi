#!/usr/bin/env python3
"""
Test script to verify Pi device detection functionality
"""
import sys
import os
import logging

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.utils.connection_manager import ConnectionManager
from src.utils.network_discovery import NetworkDiscovery
from src.utils.config import load_config

def test_pi_detection():
    """Test Pi device detection functionality"""
    print("Testing Pi device detection...")
    
    # Load configuration
    config = load_config()
    print(f"Configuration loaded: {config.get('raspberry_pi', {})}")
    
    # Test network discovery
    print("\n=== Testing Network Discovery ===")
    discovery = NetworkDiscovery()
    discovered_devices = discovery.discover_raspberry_pi_devices()
    print(f"Discovered Pi devices: {discovered_devices}")
    
    # Test connection manager
    print("\n=== Testing Connection Manager ===")
    conn_manager = ConnectionManager()
    
    # Test Pi availability
    pi_available = conn_manager.check_raspberry_pi_availability()
    print(f"Pi available: {pi_available}")
    
    # Test device connectivity
    if config and config.get("raspberry_pi", {}).get("auto_detected_ip"):
        configured_ip = config["raspberry_pi"]["auto_detected_ip"]
        print(f"\n=== Testing Configured Pi IP ({configured_ip}) ===")
        connectivity = conn_manager._test_real_pi_connectivity(configured_ip)
        print(f"Configured Pi connectivity: {connectivity}")
    
    # Test fallback LAN check
    print("\n=== Testing Fallback LAN Check ===")
    lan_check = conn_manager._fallback_lan_pi_check()
    print(f"Fallback LAN check result: {lan_check}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_pi_detection()