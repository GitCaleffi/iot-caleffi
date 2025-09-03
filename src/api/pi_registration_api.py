
import os
import sys
import json
import hashlib
import zipfile
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file
import logging

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database.local_storage import LocalStorage
from src.iot.dynamic_registration_service import get_dynamic_registration_service

# Configure logging
logger = logging.getLogger(__name__)

# Create Blueprint
pi_api = Blueprint('pi_api', __name__)

# Initialize services
storage = LocalStorage()
registration_service = get_dynamic_registration_service()

@pi_api.route('/api/register_device', methods=['POST'])
def register_device():
    """Register a new Raspberry Pi device"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        device_id = data.get('device_id')
        if not device_id:
            return jsonify({"error": "device_id is required"}), 400
        
        logger.info(f"📝 Registering Pi device: {device_id}")
        
        # Check if device already registered
        existing_devices = storage.get_registered_devices()
        device_exists = any(device['device_id'] == device_id for device in existing_devices)
        
        if device_exists:
            logger.info(f"🔄 Device {device_id} already registered, updating info")
        else:
            logger.info(f"🆕 New device registration: {device_id}")
        
        # Generate IoT Hub connection string
        connection_string = None
        try:
            connection_string = registration_service.register_device_with_azure(device_id)
            logger.info(f"✅ IoT Hub connection string generated for {device_id}")
        except Exception as e:
            logger.error(f"❌ IoT Hub registration failed for {device_id}: {e}")
            # Continue without IoT Hub - device can still function locally
        
        # Save device registration
        registration_data = {
            "device_id": device_id,
            "device_type": data.get("device_type", "raspberry_pi"),
            "registration_date": datetime.now().isoformat(),
            "system_info": data.get("system_info", {}),
            "auto_registered": data.get("auto_registered", True),
            "client_version": data.get("client_version", "1.0.0"),
            "last_seen": datetime.now().isoformat(),
            "status": "active"
        }
        
        # Save to database
        storage.save_device_registration(
            device_id=device_id,
            registration_date=datetime.now(),
            additional_data=registration_data
        )
        
        # Prepare response
        response_data = {
            "status": "success",
            "message": "Device registered successfully" if not device_exists else "Device updated successfully",
            "device_id": device_id,
            "registration_date": registration_data["registration_date"],
            "connection_string": connection_string,
            "server_info": {
                "server_url": request.host_url.rstrip('/'),
                "api_version": "1.0",
                "update_interval": 3600,  # Check for updates every hour
                "heartbeat_interval": 30   # Send heartbeat every 30 seconds
            }
        }
        
        logger.info(f"✅ Device {device_id} registration completed")
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"❌ Device registration error: {e}")
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

@pi_api.route('/api/ota/check_update', methods=['GET'])
def check_update():
    """Check if updates are available for a device"""
    try:
        device_id = request.args.get('device_id')
        current_version = request.args.get('current_version', '0.0.0')
        
        if not device_id:
            return jsonify({"error": "device_id is required"}), 400
        
        logger.info(f"🔍 Checking updates for device {device_id}, current version: {current_version}")
        
        # Get latest version info (this would typically come from a database or config)
        latest_version = "1.1.0"  # This should be dynamic
        
        # Compare versions
        has_update = _compare_versions(current_version, latest_version)
        
        if has_update:
            update_info = {
                "has_update": True,
                "latest_version": latest_version,
                "current_version": current_version,
                "update_id": f"update_{latest_version}_{device_id}",
                "release_notes": "Bug fixes and performance improvements",
                "update_size": "2.5 MB",
                "mandatory": False,
                "download_url": f"/api/ota/download_update?update_id=update_{latest_version}_{device_id}"
            }
            logger.info(f"📦 Update available for {device_id}: {current_version} -> {latest_version}")
        else:
            update_info = {
                "has_update": False,
                "latest_version": latest_version,
                "current_version": current_version,
                "message": "Device is up to date"
            }
            logger.info(f"✅ Device {device_id} is up to date")
        
        return jsonify(update_info), 200
        
    except Exception as e:
        logger.error(f"❌ Update check error: {e}")
        return jsonify({"error": f"Update check failed: {str(e)}"}), 500

@pi_api.route('/api/ota/download_update', methods=['GET'])
def download_update():
    """Download update package for a device"""
    try:
        update_id = request.args.get('update_id')
        
        if not update_id:
            return jsonify({"error": "update_id is required"}), 400
        
        logger.info(f"📥 Download request for update: {update_id}")
        
        # Create update package
        update_file = _create_update_package(update_id)
        
        if not update_file or not os.path.exists(update_file):
            return jsonify({"error": "Update package not found"}), 404
        
        logger.info(f"✅ Serving update package: {update_file}")
        
        return send_file(
            update_file,
            as_attachment=True,
            download_name=f"{update_id}.zip",
            mimetype='application/zip'
        )
        
    except Exception as e:
        logger.error(f"❌ Update download error: {e}")
        return jsonify({"error": f"Download failed: {str(e)}"}), 500

@pi_api.route('/api/ota/update_status', methods=['POST'])
def update_status():
    """Receive update status from Pi device"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        device_id = data.get('device_id')
        version = data.get('version')
        status = data.get('status')  # success, failed, in_progress
        
        if not all([device_id, version, status]):
            return jsonify({"error": "device_id, version, and status are required"}), 400
        
        logger.info(f"📊 Update status from {device_id}: {version} - {status}")
        
        # Save update status to database
        update_record = {
            "device_id": device_id,
            "version": version,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "reported_at": data.get('timestamp')
        }
        
        # This would typically be saved to a dedicated updates table
        # For now, we'll log it
        logger.info(f"💾 Update record: {update_record}")
        
        return jsonify({"status": "received", "message": "Update status recorded"}), 200
        
    except Exception as e:
        logger.error(f"❌ Update status error: {e}")
        return jsonify({"error": f"Status update failed: {str(e)}"}), 500

@pi_api.route('/api/pi_devices', methods=['GET'])
def list_pi_devices():
    """List all registered Pi devices"""
    try:
        devices = storage.get_registered_devices()
        
        # Filter for Pi devices and add status info
        pi_devices = []
        for device in devices:
            if device.get('device_id', '').startswith('pi-'):
                device_info = {
                    "device_id": device['device_id'],
                    "registration_date": device['registration_date'],
                    "last_seen": device.get('last_seen', device['registration_date']),
                    "status": device.get('status', 'unknown'),
                    "client_version": device.get('client_version', 'unknown'),
                    "system_info": device.get('system_info', {})
                }
                pi_devices.append(device_info)
        
        logger.info(f"📋 Listed {len(pi_devices)} Pi devices")
        
        return jsonify({
            "devices": pi_devices,
            "total_count": len(pi_devices),
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Device listing error: {e}")
        return jsonify({"error": f"Device listing failed: {str(e)}"}), 500

@pi_api.route('/api/pi_device/<device_id>', methods=['GET'])
def get_pi_device(device_id):
    """Get detailed information about a specific Pi device"""
    try:
        devices = storage.get_registered_devices()
        device = next((d for d in devices if d['device_id'] == device_id), None)
        
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        logger.info(f"📱 Device info requested for: {device_id}")
        
        return jsonify(device), 200
        
    except Exception as e:
        logger.error(f"❌ Device info error: {e}")
        return jsonify({"error": f"Device info failed: {str(e)}"}), 500

@pi_api.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for Pi discovery"""
    return jsonify({
        "status": "healthy",
        "service": "barcode_scanner_server",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200

def _compare_versions(current, latest):
    """Compare version strings to determine if update is needed"""
    try:
        current_parts = [int(x) for x in current.split('.')]
        latest_parts = [int(x) for x in latest.split('.')]
        
        # Pad shorter version with zeros
        max_len = max(len(current_parts), len(latest_parts))
        current_parts.extend([0] * (max_len - len(current_parts)))
        latest_parts.extend([0] * (max_len - len(latest_parts)))
        
        return latest_parts > current_parts
        
    except Exception as e:
        logger.warning(f"⚠️ Version comparison error: {e}")
        return False

def _create_update_package(update_id):
    """Create update package zip file"""
    try:
        # Create temporary update package
        temp_dir = tempfile.mkdtemp()
        update_file = os.path.join(temp_dir, f"{update_id}.zip")
        
        with zipfile.ZipFile(update_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add the current pi_auto_client.py as the update
            client_file = project_root / "pi_auto_client.py"
            if client_file.exists():
                zipf.write(client_file, "pi_auto_client.py")
            
            # Add any additional update files here
            # For example: configuration updates, new dependencies, etc.
            
            # Add update metadata
            update_info = {
                "version": "1.1.0",
                "update_id": update_id,
                "created_at": datetime.now().isoformat(),
                "files": ["pi_auto_client.py"],
                "changelog": [
                    "Improved barcode scanning performance",
                    "Enhanced error handling",
                    "Better network connectivity detection"
                ]
            }
            
            zipf.writestr("update_info.json", json.dumps(update_info, indent=2))
        
        # Calculate file hash
        file_hash = _calculate_file_hash(update_file)
        
        # Store hash for verification (in real implementation, save to database)
        logger.info(f"📦 Update package created: {update_file} (hash: {file_hash[:16]}...)")
        
        return update_file
        
    except Exception as e:
        logger.error(f"❌ Update package creation error: {e}")
        return None

def _calculate_file_hash(file_path):
    """Calculate SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# Error handlers
@pi_api.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@pi_api.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500
