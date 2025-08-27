#!/usr/bin/env python3
"""
Test script to verify Pi heartbeat functionality
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

def test_heartbeat_functionality():
    """Test Pi heartbeat functionality"""
    print("Testing Pi Heartbeat Functionality...")
    
    # Load configuration
    config = load_config()
    print(f"Configuration loaded: {config.get('raspberry_pi', {})}")
    
    # Create connection manager
    conn_manager = ConnectionManager()
    
    # Test Pi availability which should trigger heartbeat
    print("\n=== Testing Pi Availability (should trigger heartbeat) ===")
    pi_available = conn_manager.check_raspberry_pi_availability(force_check=True)
    print(f"Pi available: {pi_available}")
    
    # Test connection status
    connection_status = conn_manager.get_connection_status()
    print(f"Connection status: {connection_status}")
    
    # Wait a moment to see if heartbeat messages are processed
    print("\n=== Waiting for heartbeat processing ===")
    time.sleep(2)
    
    # Check unsent messages (should have heartbeat message)
    from database.local_storage import LocalStorage
    local_db = LocalStorage()
    unsent_messages = local_db.get_unsent_scans()
    print(f"Unsent messages count: {len(unsent_messages) if unsent_messages else 0}")
    
    if unsent_messages:
        # Show last few unsent messages
        print("Last few unsent messages:")
        for i, msg in enumerate(unsent_messages[-3:]):  # Show last 3
            print(f"  {i+1}. {msg}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_heartbeat_functionality()