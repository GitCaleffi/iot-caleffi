import os
from pathlib import Path
import json

def validate_connection_string(connection_string):
    """Validate IoT Hub connection string format"""
    if not connection_string:
        print("Connection string is empty")
        return False

    required_parts = [
        'HostName',
        'DeviceId',
        'SharedAccessKey'
    ]
    
    try:
        parts = dict(part.split('=', 1) for part in connection_string.split(';'))
        valid = all(key in parts for key in required_parts)
        if not valid:
            print(f"Missing required parts in connection string. Required: {required_parts}")
            print(f"Found parts: {list(parts.keys())}")
        return valid
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
                    if "iot_hub" in file_config:
                        config["iot_hub"].update(file_config["iot_hub"])
                    if "barcode_scanner" in file_config:
                        config["barcode_scanner"].update(file_config["barcode_scanner"])
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

        if not config["iot_hub"]["deviceId"]:
            print("No device ID found in config file or environment variables")
            return None

        return config

    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None