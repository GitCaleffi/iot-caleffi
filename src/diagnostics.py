import os
from pathlib import Path
import sqlite3
import json
import sys
import subprocess

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Import with proper path handling
from utils.config import load_config
from database.local_storage import LocalStorage
from iot.hub_client import HubClient

def check_database():
    """Check if SQLite database is working"""
    print("\nChecking database...")
    try:
        storage = LocalStorage()
        storage.save_device_id("694833b1b872")

        storage.test_connection()
        print("✓ Database connection successful")
        
        # Check if we can read existing scans
        recent_scans = storage.get_recent_scans()
        print(f"Recent scans in database: {len(recent_scans)}")
        if recent_scans:
            print("Last scan:", recent_scans[0])
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def check_iot_hub():
    """Check IoT Hub connection"""
    print("\nChecking IoT Hub connection...")
    try:
        config = load_config()
        if not config:
            print("✗ Failed to load configuration")
            return False
        
        # Check primary device first
        primary_connection_string = config["iot_hub"]["connection_string"]
        hub_client = HubClient(primary_connection_string)
        hub_client.test_connection()
        print("✓ Primary IoT Hub connection successful")
        
        # Check IoT Hub status for primary device
        status = hub_client.get_status()
        print(f"Primary deviceId: {status['deviceId']}")
        print(f"Messages sent: {status['messages_sent']}")
        print(f"Last message time: {status['last_message_time']}")
        hub_client.disconnect()
        
        # Check all devices in the configuration
        print("\nChecking all configured devices:")
        print("-" * 40)
        
        all_devices_ok = True
        devices = config["iot_hub"].get("devices", {})
        
        for device_id, device_info in devices.items():
            try:
                print(f"\nDevice ID: {device_id}")
                device_conn_string = device_info.get("connection_string")
                
                if not device_conn_string:
                    print(f"  ✗ Missing connection string")
                    all_devices_ok = False
                    continue
                    
                # Create client for this device
                device_client = HubClient(device_conn_string)
                
                # Test connection
                try:
                    device_client.test_connection()
                    print(f"  ✓ Connection successful")
                    
                    # Get device status
                    device_status = device_client.get_status()
                    print(f"  Last activity time: {device_status['last_message_time'] or 'No activity recorded'}")
                except Exception as device_err:
                    print(f"  ✗ Connection failed: {device_err}")
                    all_devices_ok = False
                finally:
                    device_client.disconnect()
                    
            except Exception as e:
                print(f"  ✗ Error checking device {device_id}: {e}")
                all_devices_ok = False
        
        return all_devices_ok
    except Exception as e:
        print(f"✗ IoT Hub error: {e}")
        return False

def check_usb_devices():
    """Check USB devices and look for potential barcode scanners"""
    print("\nChecking USB devices...")
    try:
        # Get list of USB devices
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("Failed to list USB devices")
            
        devices = result.stdout.strip().split('\n')
        print("USB devices found:")
        for device in devices:
            print(device)
            
        # Common barcode scanner vendors (add more as needed)
        scanner_vendors = [
            "0c2e",  # Honeywell
            "05e0",  # Symbol
            "0536",  # Hand Held Products
            "1eab",  # Datalogic
            "0483",  # STMicroelectronics (some scanner chips)
        ]
        
        # Check if any known scanner vendors are present
        scanner_found = False
        for device in devices:
            device_lower = device.lower()
            for vendor in scanner_vendors:
                if vendor in device_lower or "scanner" in device_lower:
                    print(f"\n✓ Potential barcode scanner found: {device}")
                    scanner_found = True
                    break
                    
        if not scanner_found:
            print("\n! Barcode scanner not detected in USB devices")
            print("Note: The scanner may still work even if not detected.")
            print("Common reasons:")
            print("- Scanner is in HID (keyboard) mode")
            print("- Scanner vendor ID not in our database")
            print("- Scanner not properly connected")
            
    except Exception as e:
        print(f"✗ Error checking USB devices: {e}")

def check_system_status():
    """Run all diagnostic checks"""
    print("\n=== Raspberry Pi Barcode Scanner Diagnostic ===")
    
    # Check database
    db_status = check_database()
    
    # Check IoT Hub
    iot_status = check_iot_hub()
    
    # Check USB devices
    usb_status = True
    try:
        check_usb_devices()
    except Exception:
        usb_status = False
        
    print("\n=== Diagnostic Summary ===")
    print(f"Database: {'✓' if db_status else '✗'}")
    print(f"IoT Hub: {'✓' if iot_status else '✗'}")
    print(f"USB Devices: {'✓' if usb_status else '✗'}")
    
    return all([db_status, iot_status, usb_status])

if __name__ == "__main__":
    success = check_system_status()
    if success:
        print("\nAll components are working correctly!")
    else:
        print("\nSome components are not working. Please check the error messages above.")
