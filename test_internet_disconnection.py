#!/usr/bin/env python3
"""
Test script to demonstrate internet disconnection monitoring and LED control
"""

import sys
import os
import time
import logging

# Add the deployment package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'deployment_package', 'src'))

from utils.connection_manager import ConnectionManager
from utils.led_status_manager import LEDStatusManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_internet_disconnection():
    """Test internet disconnection monitoring and LED control"""
    
    logger.info("🧪 Starting Dynamic Internet Disconnection Test")
    
    # Initialize connection manager (includes LED manager and continuous monitoring)
    connection_manager = ConnectionManager()
    
    logger.info("✅ Connection manager initialized with continuous monitoring")
    logger.info("🔍 Monitoring internet connectivity every 5 seconds...")
    
    try:
        # Monitor for 30 seconds to show dynamic behavior
        for i in range(6):  # 6 iterations = 30 seconds
            time.sleep(5)
            
            # Get current status
            is_connected = connection_manager.is_connected_to_internet
            led_status = connection_manager.led_manager.current_status
            
            logger.info(f"📊 Check {i+1}/6 - Internet: {'✅' if is_connected else '❌'} | LED: {led_status}")
            
            if not is_connected:
                logger.info("🔴 DISCONNECTED! Red LED should be blinking")
                logger.info("📨 Alert messages are being queued")
            else:
                logger.info("🟢 CONNECTED! Green LED should be on")
        
        logger.info("💡 Test Instructions:")
        logger.info("   1. Keep this script running")
        logger.info("   2. Disconnect WiFi/Ethernet during the test")
        logger.info("   3. Watch LED status change to 'error' (red blinking)")
        logger.info("   4. Reconnect internet and see status change back to 'online'")
        
    except KeyboardInterrupt:
        logger.info("🛑 Test stopped by user")
    finally:
        # Clean shutdown
        connection_manager.stop_monitoring()
        logger.info("🧪 Test completed")

if __name__ == "__main__":
    test_internet_disconnection()
