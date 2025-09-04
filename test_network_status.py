#!/usr/bin/env python3
"""
Test network interface status detection
"""

import sys
import os
import subprocess

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from utils.connection_manager import ConnectionManager

def test_network_status():
    """Test network interface and internet connectivity detection"""
    
    print("🔍 Testing Network Status Detection")
    print("=" * 50)
    
    # Initialize connection manager
    connection_manager = ConnectionManager()
    
    # Test network interface status
    print("📡 Checking network interfaces...")
    interface_status = connection_manager._check_network_interface()
    print(f"Network interfaces active: {'✅ YES' if interface_status else '❌ NO'}")
    
    # Test internet connectivity
    print("\n🌐 Checking internet connectivity...")
    internet_status = connection_manager.check_internet_connectivity()
    print(f"Internet connectivity: {'✅ CONNECTED' if internet_status else '❌ DISCONNECTED'}")
    
    # Show LED status
    led_status = connection_manager.led_manager.current_status
    print(f"💡 LED Status: {led_status}")
    
    # Show detailed interface info
    print("\n📋 Network Interface Details:")
    try:
        result = subprocess.run(['ip', 'addr', 'show'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if ': ' in line and ('UP' in line or 'DOWN' in line):
                    interface_name = line.split(':')[1].strip()
                    status = 'UP' if 'UP' in line else 'DOWN'
                    print(f"  {interface_name}: {status}")
                elif 'inet ' in line and not line.strip().startswith('inet 127.'):
                    ip = line.strip().split()[1]
                    print(f"    IP: {ip}")
    except Exception as e:
        print(f"  Error getting interface details: {e}")
    
    print("\n💡 Instructions:")
    print("  - If your LAN is disconnected but shows as connected,")
    print("    disconnect the ethernet cable or disable WiFi")
    print("  - Run this test again to see the status change")
    print("  - The LED should change from 'online' to 'error' when disconnected")

if __name__ == "__main__":
    test_network_status()
