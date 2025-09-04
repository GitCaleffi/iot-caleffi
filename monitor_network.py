#!/usr/bin/env python3
"""
Real-time network status monitoring
"""

import sys
import os
import time
import signal

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from utils.connection_manager import ConnectionManager

def signal_handler(sig, frame):
    print('\n🛑 Monitoring stopped by user')
    sys.exit(0)

def monitor_network():
    """Monitor network status in real-time"""
    
    print("🔍 Real-time Network Status Monitor")
    print("=" * 50)
    print("💡 Disconnect your LAN cable or WiFi to see status change")
    print("⏹️  Press Ctrl+C to stop monitoring")
    print("-" * 50)
    
    # Set up signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize connection manager
    connection_manager = ConnectionManager()
    
    previous_interface_status = None
    previous_internet_status = None
    previous_led_status = None
    
    check_count = 0
    
    while True:
        try:
            check_count += 1
            
            # Check network interface status
            interface_status = connection_manager._check_network_interface()
            
            # Check internet connectivity (this also updates LED)
            internet_status = connection_manager.is_connected_to_internet
            
            # Get LED status
            led_status = connection_manager.led_manager.current_status
            
            # Only print if status changed or every 10 checks
            status_changed = (
                interface_status != previous_interface_status or
                internet_status != previous_internet_status or
                led_status != previous_led_status
            )
            
            if status_changed or check_count % 10 == 0:
                timestamp = time.strftime("%H:%M:%S")
                interface_icon = "✅" if interface_status else "❌"
                internet_icon = "✅" if internet_status else "❌"
                
                led_icon = {
                    'online': '🟢',
                    'offline': '🔴',
                    'error': '🔴',
                    'connecting': '🟡'
                }.get(led_status, '⚪')
                
                print(f"[{timestamp}] Interface: {interface_icon} | Internet: {internet_icon} | LED: {led_icon} {led_status}")
                
                if status_changed:
                    if not interface_status:
                        print("  🔌 Network interface is DOWN - cable disconnected or WiFi disabled")
                    elif not internet_status:
                        print("  🌐 Network interface UP but no internet connectivity")
                    elif internet_status:
                        print("  ✅ Full connectivity restored")
            
            # Store previous states
            previous_interface_status = interface_status
            previous_internet_status = internet_status
            previous_led_status = led_status
            
            # Wait 2 seconds before next check
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error during monitoring: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitor_network()
