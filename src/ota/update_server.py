#!/usr/bin/env python3

import os
import json
import hashlib
import datetime
import shutil
import zipfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Optional
from datetime import timezone, datetime as dt

# Add project root to Python path
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.config import load_config

app = FastAPI(title="Raspberry Pi OTA Update Server", 
              description="Server for managing Over-the-Air updates for Raspberry Pi devices")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory structure
UPDATES_DIR = project_root / "updates"
DEVICES_DIR = project_root / "devices"

# Ensure directories exist
UPDATES_DIR.mkdir(exist_ok=True)
DEVICES_DIR.mkdir(exist_ok=True)

# Device ID from memory
DEFAULT_DEVICE_ID = "694833b1b872"

def get_update_info(update_id):
    """Get information about a specific update"""
    update_path = UPDATES_DIR / update_id
    if not update_path.exists():
        return None
    
    info_file = update_path / "info.json"
    if not info_file.exists():
        return None
    
    with open(info_file, "r") as f:
        return json.load(f)

def get_device_info(device_id):
    """Get information about a specific device"""
    device_file = DEVICES_DIR / f"{device_id}.json"
    if not device_file.exists():
        # Create a new device file with default settings
        device_info = {
            "device_id": device_id,
            "current_version": None,
            "last_check": None,
            "last_update": None,
            "status": "registered"
        }
        with open(device_file, "w") as f:
            json.dump(device_info, f, indent=2)
        return device_info
    
    with open(device_file, "r") as f:
        return json.load(f)

def get_current_time_iso():
    """Get current time in ISO format with timezone"""
    # Use the current time with timezone information and format it exactly as required
    # Format: 2025-05-09T10:34:17.353Z
    return dt.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z'

def update_device_info(device_id, updates):
    """Update device information"""
    device_info = get_device_info(device_id)
    device_info.update(updates)
    device_info["last_check"] = get_current_time_iso()
    
    with open(DEVICES_DIR / f"{device_id}.json", "w") as f:
        json.dump(device_info, f, indent=2)
    
    return device_info

def calculate_file_hash(file_path):
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

@app.get("/")
async def root():
    return {"message": "Raspberry Pi OTA Update Server", "status": "running"}

@app.post("/updates/create")
async def create_update(
    background_tasks: BackgroundTasks,
    version: str,
    description: str,
    update_file: UploadFile = File(...)
):
    """Create a new update package"""
    # Generate a unique update ID
    update_id = f"update_{version.replace('.', '_')}_{dt.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    update_dir = UPDATES_DIR / update_id
    update_dir.mkdir(exist_ok=True)
    
    # Save the uploaded file
    file_path = update_dir / update_file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(update_file.file, f)
    
    # Calculate file hash
    file_hash = calculate_file_hash(file_path)
    
    # Create update info
    update_info = {
        "update_id": update_id,
        "version": version,
        "description": description,
        "filename": update_file.filename,
        "file_hash": file_hash,
        "created_at": get_current_time_iso(),
        "size_bytes": os.path.getsize(file_path)
    }
    
    # Save update info
    with open(update_dir / "info.json", "w") as f:
        json.dump(update_info, f, indent=2)
    
    return update_info

@app.get("/updates/list")
async def list_updates():
    """List all available updates"""
    updates = []
    for update_dir in UPDATES_DIR.iterdir():
        if update_dir.is_dir():
            info_file = update_dir / "info.json"
            if info_file.exists():
                with open(info_file, "r") as f:
                    updates.append(json.load(f))
    
    # Sort by creation date (newest first)
    updates.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return updates

@app.get("/updates/{update_id}")
async def get_update(update_id: str):
    """Get information about a specific update"""
    update_info = get_update_info(update_id)
    if not update_info:
        raise HTTPException(status_code=404, detail="Update not found")
    return update_info

@app.get("/updates/{update_id}/download")
async def download_update(update_id: str):
    """Download a specific update package"""
    update_info = get_update_info(update_id)
    if not update_info:
        raise HTTPException(status_code=404, detail="Update not found")
    
    file_path = UPDATES_DIR / update_id / update_info["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Update file not found")
    
    return FileResponse(
        path=file_path,
        filename=update_info["filename"],
        media_type="application/octet-stream"
    )

@app.get("/devices/list")
async def list_devices():
    """List all registered devices"""
    devices = []
    for device_file in DEVICES_DIR.iterdir():
        if device_file.is_file() and device_file.suffix == ".json":
            with open(device_file, "r") as f:
                devices.append(json.load(f))
    return devices

@app.get("/devices/{device_id}")
async def get_device(device_id: str):
    """Get information about a specific device"""
    device_info = get_device_info(device_id)
    return device_info

@app.post("/devices/{device_id}/check")
async def check_for_updates(device_id: str, current_version: Optional[str] = None):
    """Check if updates are available for a device"""
    # Update device info
    updates = {"last_check": get_current_time_iso()}
    if current_version:
        updates["current_version"] = current_version
    
    device_info = update_device_info(device_id, updates)
    
    # Get latest update
    all_updates = await list_updates()
    if not all_updates:
        return {"device_id": device_id, "has_update": False}
    
    latest_update = all_updates[0]
    
    # Check if device needs update
    has_update = True
    if device_info.get("current_version") == latest_update.get("version"):
        has_update = False
    
    return {
        "device_id": device_id,
        "current_version": device_info.get("current_version"),
        "latest_version": latest_update.get("version"),
        "has_update": has_update,
        "update_id": latest_update.get("update_id") if has_update else None
    }

@app.post("/devices/{device_id}/update_status")
async def update_status(device_id: str, version: str, status: str):
    """Update the status of a device after applying an update"""
    updates = {
        "current_version": version,
        "last_update": get_current_time_iso(),
        "status": status
    }
    
    device_info = update_device_info(device_id, updates)
    return device_info

def main():
    """Run the update server"""
    config = load_config()
    host = config.get("ota_server", {}).get("host", "0.0.0.0")
    port = config.get("ota_server", {}).get("port", 8000)
    
    print(f"Starting OTA Update Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
