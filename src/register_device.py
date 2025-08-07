#!/usr/bin/env python3
"""
Commercial Scale Device Registration for Barcode Scanner System
Supports plug-and-play registration using barcodes only
Designed for 1000+ device deployment
"""

from azure.iot.hub import IoTHubRegistryManager
from azure.iot.hub.models import DeviceCapabilities, AuthenticationMechanism, SymmetricKey, Device
import json
import argparse
import sys
from pathlib import Path
from utils.dynamic_registration_service import DynamicRegistrationService
from utils.barcode_device_mapper import barcode_mapper

# IoT Hub owner connection string
IOTHUB_CONNECTION_STRING = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="

# Legacy device IDs (for backward compatibility)
LEGACY_DEVICE_IDS = [
    "694833b1b872",
    "c798aec00f22",
    "423399a34af8"
]

# Sample barcodes for testing commercial deployment
SAMPLE_BARCODES = [
    "1234567890123",  # EAN-13
    "123456789012",   # UPC-A
    "12345678",       # EAN-8
    "12345678901234"  # GTIN-14
]

def register_single_device(registry_manager, device_id):
    """Register a single device and return its connection string"""
    try:
        # Validate device ID format
        if not device_id or not isinstance(device_id, str):
            raise ValueError(f"Invalid device ID format: {device_id}")

        # Check if device exists with better error handling
        try:
            device = registry_manager.get_device(device_id)
            print(f"Device {device_id} already exists")
        except Exception as e:
            print(f"Creating new device {device_id}...")
            # Create device with SAS authentication
            try:
                # Generate a secure primary key (base64 encoded)
                import base64
                import os
                # Generate a random 32-byte key and encode it as base64
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')  # Also generate secondary key
                status = "enabled"
                
                # Use create_device_with_sas method
                device = registry_manager.create_device_with_sas(device_id, primary_key, secondary_key, status)
                print(f"Device {device_id} created successfully")
            except Exception as create_error:
                print(f"Detailed error creating device: {str(create_error)}")
                raise

        # Verify device was created/exists and has authentication
        if not device or not device.authentication or not device.authentication.symmetric_key:
            raise ValueError(f"Device {device_id} creation failed or missing authentication")

        # Get the primary key with verification
        primary_key = device.authentication.symmetric_key.primary_key
        if not primary_key:
            raise ValueError(f"No primary key generated for device {device_id}")
        
        # Create and verify connection string
        connection_string = f"HostName=CaleffiIoT.azure-devices.net;DeviceId={device_id};SharedAccessKey={primary_key}"
        return connection_string

    except Exception as ex:
        print(f"Detailed error registering device {device_id}: {str(ex)}")
        print(f"Error type: {type(ex).__name__}")
        return None

def update_config_file(devices_info):
    """Update config.json with device information"""
    config_path = Path(__file__).parent.parent / 'config.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Update or create devices section
        if 'iot_hub' not in config:
            config['iot_hub'] = {}
        if 'devices' not in config['iot_hub']:
            config['iot_hub']['devices'] = {}

        # Update each device
        for device_id, conn_string in devices_info.items():
            if conn_string:  # Only update if registration was successful
                config['iot_hub']['devices'][device_id] = {
                    "connection_string": conn_string,
                    "deviceId": device_id
                }

        # Write updated config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"\nConfig file updated successfully: {config_path}")

    except Exception as e:
        print(f"Error updating config file: {e}")

def register_barcode_devices(barcodes: list) -> dict:
    """Register devices using barcodes for commercial deployment"""
    print(f"Registering {len(barcodes)} devices using barcode-based system...")
    
    try:
        # Initialize dynamic registration service
        registration_service = DynamicRegistrationService(IOTHUB_CONNECTION_STRING)
        
        results = {}
        successful_registrations = 0
        
        for barcode in barcodes:
            print(f"\nProcessing barcode: {barcode}")
            
            # Register device for barcode
            result = registration_service.register_barcode_device(barcode)
            results[barcode] = result
            
            if result["success"]:
                successful_registrations += 1
                print(f"✓ SUCCESS: {result['message']}")
                print(f"  Device ID: {result['device_id']}")
            else:
                print(f"✗ FAILED: {result['message']}")
        
        # Print summary
        print(f"\n{'='*50}")
        print("COMMERCIAL REGISTRATION SUMMARY")
        print(f"{'='*50}")
        print(f"Total barcodes processed: {len(barcodes)}")
        print(f"Successful registrations: {successful_registrations}")
        print(f"Failed registrations: {len(barcodes) - successful_registrations}")
        print(f"Success rate: {(successful_registrations/len(barcodes)*100):.1f}%")
        
        # Show mapping statistics
        stats = barcode_mapper.get_mapping_stats()
        print(f"\nSystem Statistics:")
        print(f"Total device mappings: {stats.get('total_mappings', 0)}")
        print(f"Azure registered devices: {stats.get('registered_devices', 0)}")
        print(f"Pending registrations: {stats.get('pending_registrations', 0)}")
        
        return results
        
    except Exception as e:
        print(f"Error in barcode device registration: {e}")
        return {}

def register_legacy_devices():
    """Register legacy devices (backward compatibility)"""
    print("Registering legacy devices with Azure IoT Hub...")
    try:
        # Create IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(IOTHUB_CONNECTION_STRING)
        
        # Store device info
        devices_info = {}

        # Register each legacy device
        for device_id in LEGACY_DEVICE_IDS:
            print(f"\nProcessing legacy device: {device_id}")
            conn_string = register_single_device(registry_manager, device_id)
            devices_info[device_id] = conn_string

        # Update config file
        update_config_file(devices_info)

        # Summary
        print("\nLegacy Registration Summary:")
        for device_id, conn_string in devices_info.items():
            status = "SUCCESS" if conn_string else "FAILED"
            print(f"Device {device_id}: {status}")

    except Exception as ex:
        print(f"Error in legacy device registration: {ex}")

def test_commercial_deployment():
    """Test commercial deployment with sample barcodes"""
    print("Testing commercial deployment with sample barcodes...")
    print("This demonstrates plug-and-play functionality for 1000+ users")
    
    # Register sample barcodes
    results = register_barcode_devices(SAMPLE_BARCODES)
    
    # Test connections
    print(f"\n{'='*50}")
    print("TESTING CONNECTIONS")
    print(f"{'='*50}")
    
    from iot.barcode_hub_client import BarcodeHubClient
    
    try:
        client = BarcodeHubClient(IOTHUB_CONNECTION_STRING)
        
        for barcode in SAMPLE_BARCODES:
            if results.get(barcode, {}).get("success"):
                print(f"\nTesting connection for barcode: {barcode}")
                success = client.connect_with_barcode(barcode)
                if success:
                    print(f"✓ Connection successful for barcode {barcode}")
                    
                    # Test sending a message
                    message_success = client.send_barcode_message(barcode, {"test": True})
                    if message_success:
                        print(f"✓ Test message sent successfully for barcode {barcode}")
                    else:
                        print(f"✗ Failed to send test message for barcode {barcode}")
                else:
                    print(f"✗ Connection failed for barcode {barcode}")
        
        client.disconnect()
        
    except Exception as e:
        print(f"Error testing connections: {e}")

def show_system_status():
    """Show current system status and statistics"""
    print(f"\n{'='*50}")
    print("BARCODE SCANNER SYSTEM STATUS")
    print(f"{'='*50}")
    
    try:
        # Mapping statistics
        stats = barcode_mapper.get_mapping_stats()
        print(f"\nDevice Mapping Statistics:")
        print(f"  Total mappings: {stats.get('total_mappings', 0)}")
        print(f"  Registered devices: {stats.get('registered_devices', 0)}")
        print(f"  Pending registrations: {stats.get('pending_registrations', 0)}")
        print(f"  Recent activity (24h): {stats.get('recent_activity', 0)}")
        
        # List recent mappings
        mappings = barcode_mapper.list_all_mappings(10)
        if mappings:
            print(f"\nRecent Device Mappings (last 10):")
            for mapping in mappings:
                status = "✓" if mapping['azure_registered'] else "⏳"
                print(f"  {status} {mapping['barcode']} -> {mapping['device_id']} ({mapping['registration_status']})")
        
        # Test Azure connection
        print(f"\nAzure IoT Hub Connection Test:")
        try:
            registry_manager = IoTHubRegistryManager.from_connection_string(IOTHUB_CONNECTION_STRING)
            devices = registry_manager.get_devices(max_number_of_devices=1)
            print(f"  ✓ Azure IoT Hub connection successful")
        except Exception as e:
            print(f"  ✗ Azure IoT Hub connection failed: {e}")
            
    except Exception as e:
        print(f"Error getting system status: {e}")

def main():
    """Main function with command-line interface for commercial deployment"""
    parser = argparse.ArgumentParser(
        description="Commercial Scale Barcode Device Registration System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python register_device.py --commercial-test    # Test with sample barcodes
  python register_device.py --legacy            # Register legacy devices
  python register_device.py --barcode 1234567890123  # Register single barcode
  python register_device.py --status            # Show system status
  python register_device.py --batch-file barcodes.txt  # Register from file
        """
    )
    
    parser.add_argument('--commercial-test', action='store_true',
                       help='Test commercial deployment with sample barcodes')
    parser.add_argument('--legacy', action='store_true',
                       help='Register legacy devices (backward compatibility)')
    parser.add_argument('--barcode', type=str,
                       help='Register a single barcode')
    parser.add_argument('--batch-file', type=str,
                       help='Register barcodes from a text file (one per line)')
    parser.add_argument('--status', action='store_true',
                       help='Show system status and statistics')
    
    args = parser.parse_args()
    
    print("Commercial Scale Barcode Device Registration System")
    print("Designed for 1000+ device plug-and-play deployment")
    print(f"{'='*60}")
    
    try:
        if args.commercial_test:
            test_commercial_deployment()
        elif args.legacy:
            register_legacy_devices()
        elif args.barcode:
            print(f"Registering single barcode: {args.barcode}")
            results = register_barcode_devices([args.barcode])
            if results.get(args.barcode, {}).get("success"):
                print(f"\n✓ Barcode {args.barcode} registered successfully!")
                print("Device is now ready for plug-and-play operation.")
            else:
                print(f"\n✗ Failed to register barcode {args.barcode}")
        elif args.batch_file:
            try:
                with open(args.batch_file, 'r') as f:
                    barcodes = [line.strip() for line in f if line.strip()]
                print(f"Registering {len(barcodes)} barcodes from file: {args.batch_file}")
                register_barcode_devices(barcodes)
            except FileNotFoundError:
                print(f"Error: File {args.batch_file} not found")
                sys.exit(1)
        elif args.status:
            show_system_status()
        else:
            # Default: show help and run commercial test
            parser.print_help()
            print("\nRunning commercial deployment test by default...")
            test_commercial_deployment()
            
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
