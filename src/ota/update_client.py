#!/usr/bin/env python3

import os
import sys
import json
import time
import hashlib
import requests
import zipfile
import shutil
import subprocess
import logging
from pathlib import Path
import tempfile

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / "ota_update.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OTA_Client")

# Device ID from memory
DEVICE_ID = "694833b1b872"

class OTAUpdateClient:
    def __init__(self):
        self.config = load_config()
        self.device_id = DEVICE_ID
        self.server_url = self.config.get("ota_server", {}).get("url", "http://localhost:8000")
        self.current_version = self.config.get("app_version", "0.0.0")
        self.update_dir = project_root / "update_temp"
        self.update_dir.mkdir(exist_ok=True)
        
        # Ensure we have a backup directory
        self.backup_dir = project_root / "backup"
        self.backup_dir.mkdir(exist_ok=True)
        
        logger.info(f"OTA Update Client initialized for device {self.device_id}")
        logger.info(f"Current version: {self.current_version}")
        logger.info(f"Update server: {self.server_url}")
    
    def check_for_updates(self):
        """Check if updates are available from the server"""
        try:
            url = f"{self.server_url}/devices/{self.device_id}/check"
            response = requests.post(url, params={"current_version": self.current_version})
            
            if response.status_code == 200:
                update_info = response.json()
                logger.info(f"Update check result: {update_info}")
                
                if update_info.get("has_update", False):
                    logger.info(f"Update available: {update_info.get('latest_version')}")
                    return update_info
                else:
                    logger.info("No updates available")
                    return None
            else:
                logger.error(f"Failed to check for updates: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return None
    
    def download_update(self, update_id):
        """Download an update package from the server"""
        try:
            # Get update info
            url = f"{self.server_url}/updates/{update_id}"
            response = requests.get(url)
            
            if response.status_code != 200:
                logger.error(f"Failed to get update info: {response.status_code} - {response.text}")
                return None
            
            update_info = response.json()
            logger.info(f"Downloading update: {update_info.get('version')}")
            
            # Download update file
            download_url = f"{self.server_url}/updates/{update_id}/download"
            response = requests.get(download_url, stream=True)
            
            if response.status_code != 200:
                logger.error(f"Failed to download update: {response.status_code} - {response.text}")
                return None
            
            # Save update file
            update_file_path = self.update_dir / update_info.get("filename")
            with open(update_file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Update downloaded to {update_file_path}")
            
            # Verify file hash
            file_hash = self._calculate_file_hash(update_file_path)
            if file_hash != update_info.get("file_hash"):
                logger.error(f"Hash verification failed: {file_hash} != {update_info.get('file_hash')}")
                return None
            
            logger.info("Hash verification successful")
            return update_info, update_file_path
        except Exception as e:
            logger.error(f"Error downloading update: {e}")
            return None
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _create_backup(self):
        """Create a backup of the current application"""
        try:
            timestamp = time.strftime("%Y%m%d%H%M%S")
            backup_path = self.backup_dir / f"backup_{timestamp}.zip"
            
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add source files
                src_dir = project_root / "src"
                for root, _, files in os.walk(src_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, project_root)
                        zipf.write(file_path, arcname)
                
                # Add config files
                for config_file in ["config.json", "credentials.json", "requirements.txt"]:
                    file_path = project_root / config_file
                    if file_path.exists():
                        zipf.write(file_path, config_file)
            
            logger.info(f"Backup created at {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            return None
    
    def _extract_update(self, update_file_path):
        """Extract update package to temporary directory"""
        try:
            extract_dir = self.update_dir / "extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir()
            
            with zipfile.ZipFile(update_file_path, "r") as zipf:
                zipf.extractall(extract_dir)
            
            logger.info(f"Update extracted to {extract_dir}")
            return extract_dir
        except Exception as e:
            logger.error(f"Error extracting update: {e}")
            return None
    
    def _install_requirements(self, requirements_path):
        """Install Python requirements"""
        try:
            if not requirements_path.exists():
                logger.warning("No requirements.txt found in update")
                return True
            
            logger.info("Installing requirements...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to install requirements: {result.stderr}")
                return False
            
            logger.info("Requirements installed successfully")
            return True
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return False
    
    def _apply_update(self, extract_dir):
        """Apply the extracted update to the application"""
        try:
            # Install requirements first if present
            requirements_path = extract_dir / "requirements.txt"
            if requirements_path.exists():
                if not self._install_requirements(requirements_path):
                    return False
            
            # Copy files from extract directory to project root
            for item in extract_dir.iterdir():
                if item.name == "requirements.txt":
                    continue  # Already handled
                
                dest_path = project_root / item.name
                if item.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item, dest_path)
                else:
                    shutil.copy2(item, dest_path)
            
            logger.info("Update applied successfully")
            return True
        except Exception as e:
            logger.error(f"Error applying update: {e}")
            return False
    
    def _update_version(self, version):
        """Update the application version in config"""
        try:
            config_path = project_root / "config.json"
            with open(config_path, "r") as f:
                config = json.load(f)
            
            config["app_version"] = version
            
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            # Update in-memory config
            self.config["app_version"] = version
            self.current_version = version
            
            logger.info(f"Version updated to {version}")
            return True
        except Exception as e:
            logger.error(f"Error updating version: {e}")
            return False
    
    def _notify_server(self, update_info, status):
        """Notify the server about update status"""
        try:
            url = f"{self.server_url}/devices/{self.device_id}/update_status"
            data = {
                "version": update_info.get("version"),
                "status": status
            }
            
            response = requests.post(url, json=data)
            
            if response.status_code == 200:
                logger.info(f"Server notified of update status: {status}")
                return True
            else:
                logger.error(f"Failed to notify server: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error notifying server: {e}")
            return False
    
    def _cleanup(self):
        """Clean up temporary files"""
        try:
            if self.update_dir.exists():
                shutil.rmtree(self.update_dir)
            self.update_dir.mkdir(exist_ok=True)
            
            logger.info("Cleanup completed")
            return True
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return False
    
    def _restore_backup(self, backup_path):
        """Restore from backup in case of failure"""
        try:
            logger.info(f"Restoring from backup: {backup_path}")
            
            # Extract backup to temporary directory
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(backup_path, "r") as zipf:
                zipf.extractall(extract_dir)
            
            # Copy files from extract directory to project root
            for item_name in os.listdir(extract_dir):
                item = Path(extract_dir) / item_name
                dest_path = project_root / item_name
                
                if item.is_dir():
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(item, dest_path)
                else:
                    shutil.copy2(item, dest_path)
            
            # Clean up
            shutil.rmtree(extract_dir)
            
            logger.info("Backup restored successfully")
            return True
        except Exception as e:
            logger.error(f"Error restoring backup: {e}")
            return False
    
    def apply_update(self):
        """Check for and apply updates if available"""
        try:
            # Check for updates
            update_info = self.check_for_updates()
            if not update_info or not update_info.get("has_update", False):
                return False
            
            # Download update
            download_result = self.download_update(update_info.get("update_id"))
            if not download_result:
                return False
            
            update_info, update_file_path = download_result
            
            # Create backup
            backup_path = self._create_backup()
            if not backup_path:
                return False
            
            # Extract update
            extract_dir = self._extract_update(update_file_path)
            if not extract_dir:
                return False
            
            # Apply update
            if not self._apply_update(extract_dir):
                logger.error("Failed to apply update, restoring from backup")
                self._restore_backup(backup_path)
                self._notify_server(update_info, "failed")
                return False
            
            # Update version
            if not self._update_version(update_info.get("version")):
                logger.error("Failed to update version, but update was applied")
            
            # Notify server
            self._notify_server(update_info, "success")
            
            # Clean up
            self._cleanup()
            
            logger.info(f"Update to version {update_info.get('version')} completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error during update process: {e}")
            return False

def main():
    """Run the OTA update client"""
    client = OTAUpdateClient()
    
    if client.apply_update():
        logger.info("Update process completed successfully")
        print("Update process completed successfully")
        # Restart the application
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        logger.info("No updates applied")
        print("No updates applied")

if __name__ == "__main__":
    main()
