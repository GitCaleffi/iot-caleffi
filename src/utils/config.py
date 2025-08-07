import os
from pathlib import Path
import json

def validate_connection_string(connection_string):
    """Validate IoT Hub connection string format - supports both device and owner connection strings"""
    if not connection_string:
        print("Connection string is empty")
        return False

    # Required parts for device connection string
    device_required_parts = [
        'HostName',
        'DeviceId',
        'SharedAccessKey'
    ]
    
    # Required parts for IoT Hub owner connection string (for commercial deployment)
    owner_required_parts = [
        'HostName',
        'SharedAccessKeyName',
        'SharedAccessKey'
    ]
    
    try:
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        
        # Check if it's a device connection string
        device_valid = all(key in parts for key in device_required_parts)
        
        # Check if it's an IoT Hub owner connection string
        owner_valid = all(key in parts for key in owner_required_parts)
        
        if device_valid:
            print("✓ Valid device connection string")
            return True
        elif owner_valid:
            print("✓ Valid IoT Hub owner connection string (commercial deployment)")
            return True
        else:
            print(f"Invalid connection string format.")
            print(f"For device connection: Required parts: {device_required_parts}")
            print(f"For owner connection: Required parts: {owner_required_parts}")
            print(f"Found parts: {list(parts.keys())}")
            return False
            
    except Exception as e:
        print(f"Error parsing connection string: {e}")
        return False

def get_config_path():
    """Get the path to the config.json file"""
    current_dir = Path(__file__).resolve()
    project_root = current_dir.parent.parent.parent
    return project_root / 'config.json'

def save_config(config):
    """Save configuration to config.json file"""
    try:
        config_path = get_config_path()
        
        # Create backup of existing config
        if config_path.exists():
            backup_path = config_path.with_suffix('.json.bak')
            try:
                with open(config_path, 'r') as src, open(backup_path, 'w') as dst:
                    dst.write(src.read())
                print(f"Backup created at: {backup_path}")
            except Exception as e:
                print(f"Warning: Failed to create backup: {e}")
        
        # Write new config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to: {config_path}")
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

def load_config():
    """Load configuration from config file first, then override with environment variables if present"""
    try:
        # Default configuration
        config = {
            "iot_hub": {
                "connection_string": None,
                "deviceId": None
            },
            "barcode_scanner": {
                "scanner_type": "Handreader",
                "scan_timeout": 5000
            }
        }

        # Get the config path
        config_path = get_config_path()

        print(f"Looking for config file at: {config_path}")
        
        # Load from config file first
        if config_path.exists():
            print(f"Loading config from: {config_path}")
            try:
                with open(config_path, 'r') as f:
                    file_config = json.load(f)
                    # Merge all configuration sections
                    for section, values in file_config.items():
                        if section in config:
                            config[section].update(values)
                        else:
                            config[section] = values
            except json.JSONDecodeError as e:
                print(f"Error reading config file: {e}")
                return None
        else:
            print(f"Config file not found at: {config_path}")

        # Override with environment variables if they exist
        env_conn_str = os.getenv("IOTHUB_CONNECTION_STRING")
        if env_conn_str and env_conn_str.strip():
            config["iot_hub"]["connection_string"] = env_conn_str

        env_device_id = os.getenv("DEVICE_ID")
        if env_device_id and env_device_id.strip():
            config["iot_hub"]["deviceId"] = env_device_id

        # Validate the final configuration
        if not config["iot_hub"]["connection_string"]:
            print("No connection string found in config file or environment variables")
            return None

        if not validate_connection_string(config["iot_hub"]["connection_string"]):
            print("Invalid connection string format")
            return None

        # For commercial deployment, device ID is optional (generated from barcodes)
        # Check if this is an IoT Hub owner connection string (has SharedAccessKeyName)
        parts = dict(part.split('=', 1) for part in config["iot_hub"]["connection_string"].split(';'))
        is_owner_connection = 'SharedAccessKeyName' in parts
        
        if not is_owner_connection and not config["iot_hub"]["deviceId"]:
            print("No device ID found for device connection string")
            return None
        elif is_owner_connection:
            print("✓ Commercial deployment mode - device IDs will be generated from barcodes")
            # Set a placeholder device ID for owner connections
            config["iot_hub"]["deviceId"] = "auto-generated-from-barcode"

        return config

    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None