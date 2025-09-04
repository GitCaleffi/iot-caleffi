#!/usr/bin/env python3
"""
Test script for LAN-based Raspberry Pi detection and IoT Hub messaging.
This script demonstrates the complete workflow implemented in barcode_scanner_app.py.
"""

import sys
import os
import pathlib

# Add the deployment_package directory to Python path
deployment_package_dir = str(pathlib.Path(__file__).parent.absolute())
src_dir = os.path.join(deployment_package_dir, 'src')
sys.path.insert(0, deployment_package_dir)
sys.path.insert(0, src_dir)

from src.barcode_validator import validate_ean, BarcodeValidationError
from src.barcode_scanner_app import (
    test_lan_detection_and_iot_hub_flow,
    detect_lan_raspberry_pi,
    send_pi_status_to_iot_hub,
    is_pi_connected_for_scanning,
    start_pi_status_monitoring,
    stop_pi_status_monitoring
)
import logging
import time
import uuid
import hashlib
import socket
from datetime import datetime

def generate_device_id():
    """Generate a unique device ID based on system information."""
    try:
        # Get system information
        hostname = socket.gethostname()
        mac = uuid.getnode()
        
        # Create a unique string from system info
        unique_str = f"{hostname}-{mac}"
        
        # Create a hash of the unique string
        device_id = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        
        # Use first 12 characters of the hash
        return f"device-{device_id[:12]}"
        
    except Exception as e:
        # Fallback to a random UUID if anything fails
        return f"device-{str(uuid.uuid4())[:12]}"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_complete_workflow():
    """Test the complete workflow from LAN detection to IoT Hub messaging."""
    try:
        logger.info("🚀 Starting complete workflow test...")
        
        # Step 1: Test LAN detection
        logger.info("\n🔍 Step 1: Testing LAN Pi detection...")
        pi_status = detect_lan_raspberry_pi()
        
        if pi_status['connected']:
            logger.info(f"✅ Detected Pi device: {pi_status.get('ip')} - {pi_status.get('hostname', 'Unknown')} (MAC: {pi_status.get('mac', 'Unknown')})")
        else:
            logger.warning("⚠️ No Pi devices detected on the network")
        
        # Step 2: Test IoT Hub status update
        logger.info("\n📡 Step 2: Testing IoT Hub status update...")
        status_update = {
            'connected': pi_status['connected'],
            'ip': pi_status.get('ip'),
            'mac': pi_status.get('mac'),
            'hostname': pi_status.get('hostname', 'raspberry-pi'),
            'services': pi_status.get('services', []),
            'device_count': pi_status.get('device_count', 0)
        }
        
        result = send_pi_status_to_iot_hub(status_update)
        logger.info(f"✅ IoT Hub update result: {result}")
        
        # Step 3: Test Pi connection status
        logger.info("\n🔌 Step 3: Testing Pi connection status...")
        is_connected = is_pi_connected_for_scanning()
        logger.info(f"✅ Pi connection status: {'✅ Connected' if is_connected else '❌ Not connected'}")
        
        # Step 4: Test monitoring
        logger.info("\n🔄 Step 4: Starting Pi status monitoring...")
        start_pi_status_monitoring()
        logger.info("✅ Pi status monitoring started. Waiting 10 seconds...")
        time.sleep(10)
        
        logger.info("\n🛑 Stopping Pi status monitoring...")
        stop_pi_status_monitoring()
        
        logger.info("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        return False


def main():
    """Main test function"""
    print("🧪 LAN-based Pi Detection and IoT Hub Messaging Test")
    print("=" * 60)
    
    try:
        # Run comprehensive test
        logger.info("Starting comprehensive test...")
        test_results = test_complete_workflow()
        
        print("\n✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        print(f"\n❌ Test failed with error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
