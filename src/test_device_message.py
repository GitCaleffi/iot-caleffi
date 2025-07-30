#!/usr/bin/env python3

import os
import sys
import json
import argparse
from pathlib import Path
import time

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from utils.config import load_config
from iot.hub_client import HubClient

def test_device_message(device_id=None, barcode=None):
    """Test sending a message from a specific device to IoT Hub"""
    hub_client = None
    try:
        print("\n=== IoT Hub Device Message Test ===")
        
        # Load configuration
        print("\nLoading configuration...")
        config = load_config()
        if not config:
            raise Exception("Failed to load configuration")
        
        # Get all available devices
        devices = config["iot_hub"].get("devices", {})
        if not devices:
            raise Exception("No devices found in configuration")
        
        # List available devices if no device_id specified
        if not device_id:
            print("\nAvailable devices:")
            for idx, (dev_id, _) in enumerate(devices.items(), 1):
                print(f"{idx}. {dev_id}")
            
            # Prompt for device selection
            selection = input("\nSelect device number (or enter device ID): ")
            try:
                # Try to parse as index
                idx = int(selection) - 1
                if 0 <= idx < len(devices):
                    device_id = list(devices.keys())[idx]
                else:
                    # Try as direct device ID
                    if selection in devices:
                        device_id = selection
                    else:
                        raise Exception(f"Invalid selection: {selection}")
            except ValueError:
                # Not a number, try as direct device ID
                if selection in devices:
                    device_id = selection
                else:
                    raise Exception(f"Invalid device ID: {selection}")
        
        # Verify device exists
        if device_id not in devices:
            raise Exception(f"Device ID '{device_id}' not found in configuration")
        
        # Get device connection string
        device_info = devices[device_id]
        connection_string = device_info.get("connection_string")
        if not connection_string:
            raise Exception(f"No connection string found for device {device_id}")
        
        # Create IoT Hub client for this device
        print(f"\nCreating IoT Hub client for device: {device_id}")
        hub_client = HubClient(connection_string)
        
        # Check initial status
        print("\nInitial Status:")
        initial_status = hub_client.get_status()
        print(f"Connected: {initial_status['connected']}")
        print(f"deviceId: {initial_status['deviceId']}")
        print(f"Messages sent: {initial_status['messages_sent']}")
        print(f"Last message time: {initial_status['last_message_time'] or 'None'}")
        
        # Connect and test connection
        print("\nTesting connection...")
        if not hub_client.test_connection():
            raise Exception("Connection test failed")
        
        # Get test barcode if not provided
        if not barcode:
            barcode = input("\nEnter barcode to send (default: 1234567890): ").strip()
            if not barcode:
                barcode = "1234567890"  # Default 10-digit integer barcode
        
        # Validate barcode format
        try:
            int(barcode)  # Should be numeric
            if len(barcode) != 10:
                print(f"Warning: Barcode length is {len(barcode)}, expected 10 digits")
        except ValueError:
            print(f"Warning: Barcode '{barcode}' is not numeric")
        
        # Prepare and send message
        print(f"\nPreparing test message...")
        print(f"deviceId: {device_id}")
        print(f"scannedBarcode: {barcode}")
        
        # Send message and wait a bit
        print("\nSending message...")
        success = hub_client.send_message(barcode, device_id)
        
        if success:
            print("\n✓ Message sent successfully!")
        else:
            print("\n✗ Failed to send message")
        
        time.sleep(2)  # Wait for message to be processed
        
        # Check final status
        print("\nFinal Status:")
        final_status = hub_client.get_status()
        print(f"Connected: {final_status['connected']}")
        print(f"deviceId: {final_status['deviceId']}")
        print(f"Messages sent: {final_status['messages_sent']}")
        print(f"Last message time: {final_status['last_message_time'] or 'None'}")
        
        # Display message payload format
        print("\nMessage Payload Format:")
        print("-" * 40)
        payload_example = {
            "scannedBarcode": barcode,
            "deviceId": device_id,
            "timestamp": hub_client.last_message_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z' if hub_client.last_message_time else "YYYY-MM-DDTHH:MM:SS.mmmZ"
        }
        print(json.dumps(payload_example, indent=2))
        print("-" * 40)
        
        return success
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print(traceback.format_exc())
        return False
    
    finally:
        # Disconnect client if it exists
        if hub_client:
            print("\nDisconnecting from IoT Hub...")
            hub_client.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Test sending a message from a specific device to IoT Hub")
    parser.add_argument("--device", help="Device ID to use for sending the message")
    parser.add_argument("--barcode", help="Barcode to send (default: 1234567890)")
    
    args = parser.parse_args()
    
    success = test_device_message(args.device, args.barcode)
    
    if success:
        print("\nTest completed successfully!")
    else:
        print("\nTest failed.")
        sys.exit(1)

if __name__ == "__main__":
    import traceback
    main()
