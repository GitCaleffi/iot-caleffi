#!/usr/bin/env python3

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from tabulate import tabulate

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.config import load_config

# Device ID from memory
DEFAULT_DEVICE_ID = "694833b1b872"

def get_server_url():
    """Get the OTA server URL from config"""
    config = load_config()
    return config.get("ota_server", {}).get("url", "http://localhost:8000")

def list_devices(server_url=None):
    """List all registered devices"""
    if server_url is None:
        server_url = get_server_url()
    
    url = f"{server_url}/devices/list"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            devices = response.json()
            
            if not devices:
                print("No devices registered")
                return []
            
            # Format for display
            table_data = []
            for device in devices:
                table_data.append([
                    device.get("device_id"),
                    device.get("current_version", "N/A"),
                    device.get("last_update", "Never"),
                    device.get("last_check", "Never"),
                    device.get("status", "Unknown")
                ])
            
            headers = ["Device ID", "Version", "Last Update", "Last Check", "Status"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            
            return devices
        else:
            print(f"Failed to list devices: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error listing devices: {e}")
        return []

def list_updates(server_url=None):
    """List all available updates"""
    if server_url is None:
        server_url = get_server_url()
    
    url = f"{server_url}/updates/list"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            updates = response.json()
            
            if not updates:
                print("No updates available")
                return []
            
            # Format for display
            table_data = []
            for update in updates:
                table_data.append([
                    update.get("update_id"),
                    update.get("version"),
                    update.get("created_at", "Unknown"),
                    update.get("description", ""),
                    f"{update.get('size_bytes', 0) / 1024:.1f} KB"
                ])
            
            headers = ["Update ID", "Version", "Created At", "Description", "Size"]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
            
            return updates
        else:
            print(f"Failed to list updates: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Error listing updates: {e}")
        return []

def check_device_updates(device_id=None, server_url=None):
    """Check if updates are available for a specific device"""
    if device_id is None:
        device_id = DEFAULT_DEVICE_ID
    
    if server_url is None:
        server_url = get_server_url()
    
    url = f"{server_url}/devices/{device_id}/check"
    
    try:
        response = requests.post(url)
        
        if response.status_code == 200:
            update_info = response.json()
            
            print(f"Device ID: {update_info.get('device_id')}")
            print(f"Current Version: {update_info.get('current_version', 'Unknown')}")
            print(f"Latest Version: {update_info.get('latest_version', 'Unknown')}")
            print(f"Update Available: {'Yes' if update_info.get('has_update', False) else 'No'}")
            
            if update_info.get("has_update", False):
                print(f"Update ID: {update_info.get('update_id')}")
            
            return update_info
        else:
            print(f"Failed to check device updates: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error checking device updates: {e}")
        return None

def register_device(device_id=None, server_url=None):
    """Register a new device with the OTA server"""
    if device_id is None:
        device_id = DEFAULT_DEVICE_ID
    
    if server_url is None:
        server_url = get_server_url()
    
    # Just getting device info will register it if it doesn't exist
    url = f"{server_url}/devices/{device_id}"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            device_info = response.json()
            print(f"Device registered successfully: {device_id}")
            print(f"Status: {device_info.get('status', 'Unknown')}")
            return device_info
        else:
            print(f"Failed to register device: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error registering device: {e}")
        return None

def update_config(server_url=None):
    """Update the config.json file with OTA server settings"""
    if server_url is None:
        server_url = get_server_url()
    
    config_path = project_root / "config.json"
    
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        
        # Update or add OTA server settings
        if "ota_server" not in config:
            config["ota_server"] = {}
        
        config["ota_server"]["url"] = server_url
        config["ota_server"]["host"] = "0.0.0.0"
        config["ota_server"]["port"] = 8000
        
        # Add app version if not present
        if "app_version" not in config:
            config["app_version"] = "1.0.0"
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        print(f"Config updated with OTA server settings: {server_url}")
        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage OTA updates and devices")
    parser.add_argument("--server-url", help="URL of the OTA update server")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List devices command
    list_devices_parser = subparsers.add_parser("list-devices", help="List all registered devices")
    
    # List updates command
    list_updates_parser = subparsers.add_parser("list-updates", help="List all available updates")
    
    # Check device updates command
    check_updates_parser = subparsers.add_parser("check-updates", help="Check if updates are available for a device")
    check_updates_parser.add_argument("--device-id", help="Device ID to check")
    
    # Register device command
    register_device_parser = subparsers.add_parser("register-device", help="Register a device with the OTA server")
    register_device_parser.add_argument("--device-id", help="Device ID to register")
    
    # Update config command
    update_config_parser = subparsers.add_parser("update-config", help="Update the config.json file with OTA server settings")
    
    args = parser.parse_args()
    
    server_url = args.server_url
    
    if args.command == "list-devices":
        list_devices(server_url)
    elif args.command == "list-updates":
        list_updates(server_url)
    elif args.command == "check-updates":
        check_device_updates(args.device_id, server_url)
    elif args.command == "register-device":
        register_device(args.device_id, server_url)
    elif args.command == "update-config":
        update_config(server_url)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
