#!/usr/bin/env python3

import os
import sys
import json
import zipfile
import argparse
import requests
from pathlib import Path
import datetime
from datetime import timezone

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.config import load_config

def create_update_package(version, description, output_dir=None):
    """Create an update package from the current codebase"""
    if output_dir is None:
        output_dir = project_root / "updates"
        output_dir.mkdir(exist_ok=True)
    
    # Create a timestamp for the package name
    timestamp = datetime.datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    package_name = f"update_{version.replace('.', '_')}_{timestamp}.zip"
    package_path = output_dir / package_name
    
    # Create the zip file
    with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add source files
        src_dir = project_root / "src"
        for root, _, files in os.walk(src_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_root)
                zipf.write(file_path, arcname)
        
        # Add config files (excluding credentials)
        config_file = project_root / "config.json"
        if config_file.exists():
            # Load config but remove sensitive information
            with open(config_file, "r") as f:
                config = json.load(f)
            
            # Remove connection strings or other sensitive data
            if "iot_hub" in config:
                if "connection_string" in config["iot_hub"]:
                    config["iot_hub"]["connection_string"] = ""
            
            # Add app version to config
            config["app_version"] = version
            
            # Write modified config to zip
            with zipf.open("config.json", "w") as f:
                f.write(json.dumps(config, indent=2).encode("utf-8"))
        
        # Add requirements.txt
        req_file = project_root / "requirements.txt"
        if req_file.exists():
            zipf.write(req_file, "requirements.txt")
    
    print(f"Update package created: {package_path}")
    return package_path

def upload_to_server(package_path, version, description, server_url=None):
    """Upload the update package to the OTA server"""
    config = load_config()
    if server_url is None:
        server_url = config.get("ota_server", {}).get("url", "http://localhost:8000")
    
    url = f"{server_url}/updates/create"
    
    try:
        with open(package_path, "rb") as f:
            files = {"update_file": (package_path.name, f)}
            data = {"version": version, "description": description}
            
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                print(f"Update uploaded successfully: {response.json()}")
                return response.json()
            else:
                print(f"Failed to upload update: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"Error uploading update: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Create and upload an OTA update package")
    parser.add_argument("version", help="Version number for the update (e.g., 1.0.0)")
    parser.add_argument("description", help="Description of the update")
    parser.add_argument("--output-dir", help="Directory to save the update package")
    parser.add_argument("--server-url", help="URL of the OTA update server")
    parser.add_argument("--no-upload", action="store_true", help="Don't upload the package to the server")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    # Create the update package
    package_path = create_update_package(args.version, args.description, output_dir)
    
    # Upload to server if requested
    if not args.no_upload:
        upload_to_server(package_path, args.version, args.description, args.server_url)

if __name__ == "__main__":
    main()
