#!/usr/bin/env python3
"""
Test script to verify the complete flow of Pi connection detection and heartbeat functionality
"""
import sys
import os
import logging
import time

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from src.utils.connection_manager import ConnectionManager
from src.utils.config import load_config

def test_complete_flow():
    """Test the complete flow of Pi connection detection and heartbeat functionality"""
    print("Testing Complete Pi Connection Detection and Heartbeat Flow...")
    
    # Load configuration
    config = load_config()
    print(f"Configuration loaded: {config.get('raspberry_pi', {})}")
    
    # Create connection manager
    conn_manager = ConnectionManager()
    
    # Wait a moment for auto-refresh to run
    print("\n=== Waiting for auto-refresh to update connection status ===")
    time.sleep(6)  # Wait for auto-refresh (5 seconds interval + 1 second buffer)
    
    # Test connection status after auto-refresh
    print("\n=== Connection Status After Auto-Refresh ===")
    connection_status = conn_manager.get_connection_status()
    print(f"Connection status: {connection_status}")
    
    # Force a refresh to ensure we have current status
    print("\n=== Forcing Connection Status Refresh ===")
    conn_manager.check_internet_connectivity()
    conn_manager.check_iot_hub_connectivity()
    pi_available = conn_manager.check_raspberry_pi_availability(force_check=True)
    
    print(f"Pi available: {pi_available}")
    
    # Get updated connection status
    connection_status = conn_manager.get_connection_status()
    print(f"Updated connection status: {connection_status}")
    
    # Test Pi status update sending
    print("\n=== Testing Pi Status Update Sending ===")
    # This should have been triggered by the state change detection in check_raspberry_pi_availability
    
    # Check unsent messages for Pi status updates
    from database.local_storage import LocalStorage
    local_db = LocalStorage()
    unsent_messages = local_db.get_unsent_scans()
    print(f"Total unsent messages: {len(unsent_messages) if unsent_messages else 0}")
    
    # Look for Pi status messages
    pi_status_messages = [msg for msg in unsent_messages if msg.get('device_id') == 'live-server-pi-status']
    print(f"Pi status messages: {len(pi_status_messages)}")
    
    if pi_status_messages:
        print("Recent Pi status messages:")
        for i, msg in enumerate(pi_status_messages[-3:]):  # Show last 3
            print(f"  {i+1}. {msg}")
    
    # Test manual Pi status update
    print("\n=== Testing Manual Pi Status Update ===")
    conn_manager._send_pi_status_update(pi_available)
    
    # Check if new message was added
    unsent_messages_after = local_db.get_unsent_scans()
    new_pi_messages = [msg for msg in unsent_messages_after if msg.get('device_id') == 'live-server-pi-status']
    print(f"Pi status messages after manual update: {len(new_pi_messages)}")
    
    print("\n=== Summary ===")
    internet_status = "✅ Connected" if connection_status.get('internet_connected') else "❌ Disconnected"
    iot_hub_status = "✅ Connected" if connection_status.get('iot_hub_connected') else "❌ Disconnected"
    pi_status = "✅ Available" if pi_available else "❌ Unavailable"
    
    print(f"Internet: {internet_status}")
    print(f"IoT Hub: {iot_hub_status}")
    print(f"Raspberry Pi: {pi_status}")
    print(f"Unsent messages: {connection_status.get('unsent_messages_count', 0)}")
    
    if pi_available:
        print("\n🎉 SUCCESS: Raspberry Pi is properly detected and heartbeat functionality is working!")
    else:
        print("\n⚠️  WARNING: Raspberry Pi not detected. Check network configuration.")
    
    print("\nTest completed!")

if __name__ == "__main__":
    test_complete_flow()