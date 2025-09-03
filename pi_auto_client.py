#!/usr/bin/env python3
"""
Raspberry Pi Auto Client - Complete autonomous system for Pi devices
Handles: Auto-registration, OTA updates, barcode scanning, IoT Hub communication
Designed for plug-and-play operation with zero user configuration
"""

import os
import sys
import json
import time
import socket
import hashlib
import requests
import subprocess
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import zipfile
import shutil

# Azure IoT Hub imports
try:
    from azure.iot.device import IoTHubDeviceClient, Message
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print("⚠️ Azure IoT SDK not installed. IoT Hub features disabled.")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/pi_auto_client.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PiAutoClient")

class PiAutoClient:
    def __init__(self):
        self.device_id = self._generate_device_id()
        self.server_url = self._discover_server()
        self.connection_string = None
        self.iot_client = None
        self.running = True
        self.last_update_check = None
        self.last_heartbeat = None
        
        # Configuration
        self.config = {
            "device_id": self.device_id,
            "server_url": self.server_url,
            "update_interval": 3600,  # Check for updates every hour
            "heartbeat_interval": 30,  # Send heartbeat every 30 seconds
            "registration_retry_interval": 300,  # Retry registration every 5 minutes
            "app_version": "1.0.0"
        }
        
        logger.info(f"🚀 Pi Auto Client initialized")
        logger.info(f"📱 Device ID: {self.device_id}")
        logger.info(f"🌐 Server URL: {self.server_url}")
    
    def _generate_device_id(self):
        """Generate unique device ID based on hardware"""
        try:
            # Try to get CPU serial
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        if serial and serial != '0000000000000000':
                            return f"pi-{serial[-8:]}"
            
            # Fallback to MAC address
            mac = self._get_mac_address()
            if mac:
                return f"pi-{mac.replace(':', '')[-8:]}"
            
            # Final fallback to hostname
            hostname = socket.gethostname()
            return f"pi-{hostname}"
            
        except Exception as e:
            logger.warning(f"Could not generate device ID: {e}")
            return f"pi-{int(time.time())}"
    
    def _get_mac_address(self):
        """Get primary MAC address"""
        try:
            # Get MAC from network interface
            result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
            
            # Fallback to wlan0
            result = subprocess.run(['cat', '/sys/class/net/wlan0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
                
        except Exception as e:
            logger.warning(f"Could not get MAC address: {e}")
        
        return None
    
    def _discover_server(self):
        """Auto-discover the live server on network"""
        # Common server IPs and ports to try
        server_candidates = [
            "http://10.0.0.4:5000",  # Live server from memory
            "http://192.168.1.1:5000",
            "http://192.168.0.1:5000",
            "http://10.0.0.1:5000",
            "https://iot.caleffionline.it"  # External server
        ]
        
        for server_url in server_candidates:
            try:
                response = requests.get(f"{server_url}/api/health", timeout=5)
                if response.status_code == 200:
                    logger.info(f"✅ Server discovered at: {server_url}")
                    return server_url
            except:
                continue
        
        # Default fallback
        logger.warning("⚠️ No server discovered, using default")
        return "http://10.0.0.4:5000"
    
    def register_device(self):
        """Auto-register device with the server"""
        try:
            logger.info(f"📝 Registering device {self.device_id} with server...")
            
            # Get system information
            system_info = self._get_system_info()
            
            # Registration payload
            registration_data = {
                "device_id": self.device_id,
                "device_type": "raspberry_pi",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "system_info": system_info,
                "auto_registered": True,
                "client_version": self.config["app_version"]
            }
            
            # Register with server
            response = requests.post(
                f"{self.server_url}/api/register_device",
                json=registration_data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                self.connection_string = result.get("connection_string")
                
                logger.info("✅ Device registered successfully")
                logger.info(f"🔗 IoT Hub connection string received")
                
                # Save configuration
                self._save_config()
                
                return True
            else:
                logger.error(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            return False
    
    def _get_system_info(self):
        """Get comprehensive system information"""
        try:
            # Get IP address
            hostname = socket.gethostname()
            try:
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "unknown"
            
            # Get uptime
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
            except:
                uptime_seconds = 0
            
            # Get memory info
            try:
                with open('/proc/meminfo', 'r') as f:
                    meminfo = f.read()
                    total_mem = int([line for line in meminfo.split('\n') if 'MemTotal' in line][0].split()[1])
            except:
                total_mem = 0
            
            # Get CPU info
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpu_info = f.read()
                    cpu_model = [line for line in cpu_info.split('\n') if 'model name' in line]
                    cpu_model = cpu_model[0].split(':')[1].strip() if cpu_model else "Unknown"
            except:
                cpu_model = "Unknown"
            
            return {
                "hostname": hostname,
                "ip_address": ip_address,
                "uptime_seconds": uptime_seconds,
                "total_memory_kb": total_mem,
                "cpu_model": cpu_model,
                "mac_address": self._get_mac_address(),
                "services": ["barcode_scanner", "iot_client", "auto_updater"],
                "os_info": self._get_os_info()
            }
            
        except Exception as e:
            logger.warning(f"Could not get complete system info: {e}")
            return {
                "hostname": socket.gethostname(),
                "services": ["barcode_scanner", "iot_client"]
            }
    
    def _get_os_info(self):
        """Get OS information"""
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"')
                return os_info
        except:
            return {"NAME": "Unknown Linux"}
    
    def connect_to_iot_hub(self):
        """Connect to Azure IoT Hub"""
        if not AZURE_AVAILABLE or not self.connection_string:
            logger.warning("⚠️ IoT Hub connection not available")
            return False
        
        try:
            logger.info("🔗 Connecting to Azure IoT Hub...")
            self.iot_client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
            self.iot_client.connect()
            logger.info("✅ Connected to IoT Hub successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ IoT Hub connection failed: {e}")
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to IoT Hub via Device Twin"""
        if not self.iot_client:
            return False
        
        try:
            system_info = self._get_system_info()
            
            reported_properties = {
                "status": "online",
                "last_seen": datetime.utcnow().isoformat() + "Z",
                "device_info": system_info,
                "heartbeat_version": "3.0",
                "client_version": self.config["app_version"]
            }
            
            self.iot_client.patch_twin_reported_properties(reported_properties)
            self.last_heartbeat = datetime.now()
            
            logger.debug(f"💓 Heartbeat sent to IoT Hub")
            return True
            
        except Exception as e:
            logger.error(f"❌ Heartbeat failed: {e}")
            return False
    
    def check_for_updates(self):
        """Check for and apply OTA updates"""
        try:
            logger.info("🔍 Checking for updates...")
            
            response = requests.get(
                f"{self.server_url}/api/ota/check_update",
                params={
                    "device_id": self.device_id,
                    "current_version": self.config["app_version"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                update_info = response.json()
                
                if update_info.get("has_update", False):
                    logger.info(f"📦 Update available: {update_info.get('latest_version')}")
                    return self._apply_update(update_info)
                else:
                    logger.info("✅ No updates available")
                    return False
            else:
                logger.warning(f"⚠️ Update check failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Update check error: {e}")
            return False
    
    def _apply_update(self, update_info):
        """Download and apply update"""
        try:
            logger.info(f"📥 Downloading update {update_info.get('latest_version')}...")
            
            # Download update package
            download_url = f"{self.server_url}/api/ota/download_update"
            response = requests.get(
                download_url,
                params={"update_id": update_info.get("update_id")},
                stream=True,
                timeout=300
            )
            
            if response.status_code != 200:
                logger.error(f"❌ Download failed: {response.status_code}")
                return False
            
            # Save update file
            update_file = f"/tmp/update_{update_info.get('update_id')}.zip"
            with open(update_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Verify hash if provided
            if update_info.get("file_hash"):
                file_hash = self._calculate_file_hash(update_file)
                if file_hash != update_info.get("file_hash"):
                    logger.error("❌ Update file hash verification failed")
                    os.remove(update_file)
                    return False
            
            # Create backup
            backup_file = self._create_backup()
            if not backup_file:
                logger.error("❌ Failed to create backup")
                return False
            
            # Apply update
            if self._install_update(update_file, update_info):
                logger.info("✅ Update applied successfully")
                
                # Update version
                self.config["app_version"] = update_info.get("latest_version")
                self._save_config()
                
                # Notify server
                self._notify_update_status(update_info, "success")
                
                # Clean up
                os.remove(update_file)
                
                # Restart service
                logger.info("🔄 Restarting service...")
                subprocess.run(["sudo", "systemctl", "restart", "pi-auto-client"])
                
                return True
            else:
                logger.error("❌ Update installation failed, restoring backup")
                self._restore_backup(backup_file)
                self._notify_update_status(update_info, "failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Update application error: {e}")
            return False
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _create_backup(self):
        """Create backup of current installation"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"/tmp/backup_{timestamp}.zip"
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Backup this script
                zipf.write(__file__, "pi_auto_client.py")
                
                # Backup config if exists
                config_file = "/etc/pi_auto_client.json"
                if os.path.exists(config_file):
                    zipf.write(config_file, "config.json")
            
            logger.info(f"💾 Backup created: {backup_file}")
            return backup_file
            
        except Exception as e:
            logger.error(f"❌ Backup creation failed: {e}")
            return None
    
    def _install_update(self, update_file, update_info):
        """Install update from zip file"""
        try:
            # Extract update
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(update_file, 'r') as zipf:
                zipf.extractall(extract_dir)
            
            # Install files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    src_file = os.path.join(root, file)
                    
                    if file == "pi_auto_client.py":
                        # Replace this script
                        shutil.copy2(src_file, __file__)
                        os.chmod(__file__, 0o755)
                    elif file == "config.json":
                        # Update config
                        shutil.copy2(src_file, "/etc/pi_auto_client.json")
            
            # Clean up
            shutil.rmtree(extract_dir)
            
            logger.info("✅ Update files installed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Update installation error: {e}")
            return False
    
    def _restore_backup(self, backup_file):
        """Restore from backup"""
        try:
            extract_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                zipf.extractall(extract_dir)
            
            # Restore files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    src_file = os.path.join(root, file)
                    
                    if file == "pi_auto_client.py":
                        shutil.copy2(src_file, __file__)
                        os.chmod(__file__, 0o755)
                    elif file == "config.json":
                        shutil.copy2(src_file, "/etc/pi_auto_client.json")
            
            shutil.rmtree(extract_dir)
            logger.info("✅ Backup restored")
            return True
            
        except Exception as e:
            logger.error(f"❌ Backup restore failed: {e}")
            return False
    
    def _notify_update_status(self, update_info, status):
        """Notify server of update status"""
        try:
            requests.post(
                f"{self.server_url}/api/ota/update_status",
                json={
                    "device_id": self.device_id,
                    "version": update_info.get("latest_version"),
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                },
                timeout=10
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not notify update status: {e}")
    
    def listen_for_barcodes(self):
        """Listen for barcode scanner input"""
        logger.info("🔍 Starting barcode scanner listener...")
        
        # This would typically read from USB HID device
        # For now, simulate with stdin for testing
        try:
            while self.running:
                try:
                    # In real implementation, this would read from barcode scanner device
                    # For example: /dev/input/event0 or similar HID device
                    
                    # Simulate barcode input (replace with actual scanner reading)
                    barcode = input("Scan barcode (or 'quit' to exit): ").strip()
                    
                    if barcode.lower() == 'quit':
                        break
                    
                    if barcode:
                        self.process_barcode(barcode)
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"❌ Barcode reading error: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Barcode listener error: {e}")
    
    def process_barcode(self, barcode):
        """Process scanned barcode"""
        try:
            logger.info(f"📊 Processing barcode: {barcode}")
            
            # Send to server API
            api_success = self._send_to_api(barcode)
            
            # Send to IoT Hub
            iot_success = self._send_to_iot_hub(barcode)
            
            if api_success or iot_success:
                logger.info(f"✅ Barcode {barcode} processed successfully")
            else:
                logger.warning(f"⚠️ Barcode {barcode} processing failed")
                
        except Exception as e:
            logger.error(f"❌ Barcode processing error: {e}")
    
    def _send_to_api(self, barcode):
        """Send barcode to server API"""
        try:
            response = requests.post(
                f"{self.server_url}/api/v1/raspberry/barcodeScan",
                json={
                    "deviceId": self.device_id,
                    "scannedBarcode": barcode,
                    "quantity": 1
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("✅ Barcode sent to API")
                return True
            else:
                logger.warning(f"⚠️ API send failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ API send error: {e}")
            return False
    
    def _send_to_iot_hub(self, barcode):
        """Send barcode to IoT Hub"""
        if not self.iot_client:
            return False
        
        try:
            message_data = {
                "deviceId": self.device_id,
                "barcode": barcode,
                "quantity": 1,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "messageType": "barcode_scan"
            }
            
            message = Message(json.dumps(message_data))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"
            
            self.iot_client.send_message(message)
            logger.info("✅ Barcode sent to IoT Hub")
            return True
            
        except Exception as e:
            logger.error(f"❌ IoT Hub send error: {e}")
            return False
    
    def _save_config(self):
        """Save configuration to file"""
        try:
            config_file = "/etc/pi_auto_client.json"
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.debug("💾 Configuration saved")
        except Exception as e:
            logger.warning(f"⚠️ Could not save config: {e}")
    
    def _load_config(self):
        """Load configuration from file"""
        try:
            config_file = "/etc/pi_auto_client.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
                    self.connection_string = saved_config.get("connection_string")
                logger.info("📂 Configuration loaded")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not load config: {e}")
        return False
    
    def run_maintenance_loop(self):
        """Run background maintenance tasks"""
        logger.info("🔧 Starting maintenance loop...")
        
        while self.running:
            try:
                current_time = datetime.now()
                
                # Check for updates (hourly)
                if (not self.last_update_check or 
                    current_time - self.last_update_check > timedelta(seconds=self.config["update_interval"])):
                    self.check_for_updates()
                    self.last_update_check = current_time
                
                # Send heartbeat (every 30 seconds)
                if (not self.last_heartbeat or 
                    current_time - self.last_heartbeat > timedelta(seconds=self.config["heartbeat_interval"])):
                    self.send_heartbeat()
                
                # Sleep for 10 seconds before next check
                time.sleep(10)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Maintenance loop error: {e}")
                time.sleep(30)
    
    def start(self):
        """Start the Pi Auto Client"""
        logger.info("🚀 Starting Pi Auto Client...")
        
        # Load existing configuration
        self._load_config()
        
        # Register device if not already registered
        if not self.connection_string:
            if not self.register_device():
                logger.error("❌ Device registration failed, retrying in 5 minutes...")
                time.sleep(300)
                return self.start()  # Retry
        
        # Connect to IoT Hub
        if not self.connect_to_iot_hub():
            logger.warning("⚠️ IoT Hub connection failed, continuing without it...")
        
        # Start maintenance loop in background
        maintenance_thread = threading.Thread(target=self.run_maintenance_loop, daemon=True)
        maintenance_thread.start()
        
        # Start barcode listener (main thread)
        self.listen_for_barcodes()
        
        logger.info("🛑 Pi Auto Client stopped")
    
    def stop(self):
        """Stop the Pi Auto Client"""
        logger.info("🛑 Stopping Pi Auto Client...")
        self.running = False
        
        if self.iot_client:
            try:
                # Set offline status
                offline_properties = {
                    "status": "offline",
                    "last_seen": datetime.utcnow().isoformat() + "Z"
                }
                self.iot_client.patch_twin_reported_properties(offline_properties)
                self.iot_client.disconnect()
            except:
                pass

def main():
    """Main entry point"""
    client = PiAutoClient()
    
    try:
        client.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    finally:
        client.stop()

if __name__ == "__main__":
    main()
