#!/usr/bin/env python3
"""
Test script with debug logging enabled
"""
import sys
import os
import logging

# Set up debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.connection_manager import ConnectionManager
import time

def test_connection_with_debug():
    print("Testing ConnectionManager with debug logging...")
    
    # Create connection manager instance
    cm = ConnectionManager()
    
    # Force clear cache by setting last check to 0
    cm.last_connection_check = 0
    cm.is_connected_to_internet = False
    
    print(f"Initial state: is_connected_to_internet = {cm.is_connected_to_internet}")
    print(f"Last connection check: {cm.last_connection_check}")
    print(f"Connection check interval: {cm.connection_check_interval}")
    
    # Test internet connectivity
    print("\nTesting internet connectivity...")
    result = cm.check_internet_connectivity()
    print(f"Internet connectivity result: {result}")
    print(f"Updated state: is_connected_to_internet = {cm.is_connected_to_internet}")
    print(f"Last connection check: {cm.last_connection_check}")
    
    return result

if __name__ == "__main__":
    result = test_connection_with_debug()
    print(f"\nFinal Result: {'✅ Connected' if result else '❌ Offline'}")
