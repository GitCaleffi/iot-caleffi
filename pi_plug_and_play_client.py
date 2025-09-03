#!/usr/bin/env python3
"""
Raspberry Pi Plug-and-Play Client
True plug-and-play: Connect to Wi-Fi → Scan barcode to register → Start working
Designed for deployment on client's remote server with cross-network discovery
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
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

# Azure IoT Hub imports
try:
    from azure.iot.device import IoTHubDeviceClient, Message
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/pi_plug_play.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("PiPlugPlay")

class PiPlugAndPlayClient:
    def __init__(self):
        self.device_id = None
        self.server_url = None
        self.connection_string = None
        self.iot_client = None
        self.registered = False
        self.running = True
        
        # Server discovery endpoints to try
        self.server_candidates = [
            # Client's production server
            "https://iot.caleffionline.it",
            "http://iot.caleffionline.it",
            
            # Local network discovery
            "http://10.0.0.4:5000",      # Your current server
            "http://192.168.1.1:5000",   # Common router IPs
            "http://192.168.0.1:5000",
            "http://10.0.0.1:5000",
            
            # Cloud fallback
            "https://api2.caleffionline.it"
        ]
        
        logger.info("🚀 Pi Plug-and-Play Client starting...")
        logger.info("📡 Will discover server automatically...")
    
    def discover_server(self):
        """Auto-discover server across networks"""
        logger.info("🔍 Discovering server...")
        
        for server_url in self.server_candidates:
            try:
                logger.info(f"🌐 Trying server: {server_url}")
                
                # Try health check endpoint
                response = requests.get(f"{server_url}/api/health", timeout=10)
                
                if response.status_code == 200:
                    health_data = response.json()
                    if health_data.get("service") == "barcode_scanner_server":
                        logger.info(f"✅ Server discovered: {server_url}")
                        self.server_url = server_url
                        return True
                        
            except Exception as e:
                logger.debug(f"❌ Server {server_url} not reachable: {e}")
                continue
        
        logger.error("❌ No server found! Check network connectivity.")
        return False
    
    def wait_for_barcode_registration(self):
        """Wait for barcode scan to trigger registration"""
        logger.info("📱 PLUG-AND-PLAY MODE ACTIVE")
        logger.info("🔌 Connect your USB barcode scanner")
        logger.info("📊 Scan ANY barcode to register this device")
        logger.info("⏳ Waiting for barcode scan...")
        
        while not self.registered and self.running:
            try:
                # Listen for barcode input
                # In production, this reads from USB HID device
                # For demo, using stdin
                print("\n🎯 Scan barcode to register (or type barcode + Enter):")
                barcode = input().strip()
                
                if barcode and len(barcode) >= 6:
                    logger.info(f"📊 Barcode scanned: {barcode}")
                    
                    # Use barcode to generate device ID
                    self.device_id = self._generate_device_id_from_barcode(barcode)
                    logger.info(f"🆔 Device ID generated: {self.device_id}")
                    
                    # Register device with server
                    if self.register_device_with_barcode(barcode):
                        logger.info("✅ REGISTRATION SUCCESSFUL!")
                        logger.info("🎉 Device is now ready for barcode scanning")
                        self.registered = True
                        return True
                    else:
                        logger.error("❌ Registration failed, try scanning again")
                        
                else:
                    logger.warning("⚠️ Invalid barcode, please scan a valid barcode")
                    
            except KeyboardInterrupt:
                logger.info("🛑 Registration cancelled")
                return False
            except Exception as e:
                logger.error(f"❌ Registration error: {e}")
                time.sleep(2)
        
        return False
    
    def _generate_device_id_from_barcode(self, barcode):
        """Generate unique device ID using barcode + hardware info"""
        try:
            # Get hardware identifiers
            mac = self._get_mac_address() or "unknown"
            cpu_serial = self._get_cpu_serial() or "unknown"
            
            # Create unique identifier
            unique_string = f"{barcode}-{mac}-{cpu_serial}"
            device_hash = hashlib.md5(unique_string.encode()).hexdigest()[:8]
            
            return f"pi-{barcode[-4:]}-{device_hash}"
            
        except Exception as e:
            logger.warning(f"⚠️ Could not generate device ID: {e}")
            return f"pi-{barcode[-8:]}-{int(time.time())}"
    
    def _get_mac_address(self):
        """Get primary MAC address"""
        try:
            # Try eth0 first
            result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().replace(':', '')
            
            # Fallback to wlan0
            result = subprocess.run(['cat', '/sys/class/net/wlan0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().replace(':', '')
                
        except Exception:
            pass
        return None
    
    def _get_cpu_serial(self):
        """Get CPU serial number"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        if serial and serial != '0000000000000000':
                            return serial[-8:]
        except Exception:
            pass
        return None
    
    def register_device_with_barcode(self, registration_barcode):
        """Register device using scanned barcode"""
        try:
            logger.info(f"📝 Registering device with barcode: {registration_barcode}")
            
            # Get system information
            system_info = self._get_system_info()
            
            # Registration payload
            registration_data = {
                "device_id": self.device_id,
                "registration_barcode": registration_barcode,
                "device_type": "raspberry_pi_plug_play",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "system_info": system_info,
                "plug_and_play": True,
                "registration_method": "barcode_scan",
                "client_version": "2.0.0"
            }
            
            # Register with server
            response = requests.post(
                f"{self.server_url}/api/register_device",
                json=registration_data,
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                self.connection_string = result.get("connection_string")
                
                logger.info("✅ Device registered successfully")
                logger.info(f"🔗 IoT Hub connection received")
                
                # Save configuration
                self._save_config()
                
                # Send registration confirmation to IoT Hub
                self._send_registration_confirmation(registration_barcode)
                
                return True
            else:
                logger.error(f"❌ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Registration error: {e}")
            return False
    
    def _send_registration_confirmation(self, registration_barcode):
        """Send registration confirmation to IoT Hub"""
        try:
            if not self.connection_string or not AZURE_AVAILABLE:
                logger.warning("⚠️ IoT Hub not available for registration confirmation")
                return
            
            # Connect to IoT Hub
            self.iot_client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
            self.iot_client.connect()
            
            # Send registration message
            registration_message = {
                "messageType": "device_registration",
                "deviceId": self.device_id,
                "registrationBarcode": registration_barcode,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "registrationMethod": "plug_and_play_barcode_scan",
                "systemInfo": self._get_system_info()
            }
            
            message = Message(json.dumps(registration_message))
            message.content_type = "application/json"
            message.content_encoding = "utf-8"
            
            self.iot_client.send_message(message)
            logger.info("✅ Registration confirmation sent to IoT Hub")
            
        except Exception as e:
            logger.error(f"❌ IoT Hub registration confirmation failed: {e}")
    
    def _get_system_info(self):
        """Get comprehensive system information"""
        try:
            hostname = socket.gethostname()
            
            # Get IP address
            try:
                # Connect to external server to get local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
                s.close()
            except:
                ip_address = "unknown"
            
            # Get network info
            wifi_ssid = self._get_wifi_ssid()
            
            return {
                "hostname": hostname,
                "ip_address": ip_address,
                "wifi_ssid": wifi_ssid,
                "mac_address": self._get_mac_address(),
                "cpu_serial": self._get_cpu_serial(),
                "registration_location": "plug_and_play",
                "services": ["barcode_scanner", "iot_client", "plug_play"],
                "network_type": "wifi" if wifi_ssid else "ethernet"
            }
            
        except Exception as e:
            logger.warning(f"Could not get complete system info: {e}")
            return {
                "hostname": socket.gethostname(),
                "registration_location": "plug_and_play"
            }
    
    def _get_wifi_ssid(self):
        """Get current Wi-Fi SSID"""
        try:
            result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None
    
    def start_barcode_scanning(self):
        """Start continuous barcode scanning after registration"""
        logger.info("🔍 Starting barcode scanning service...")
        logger.info("📊 Scan barcodes to send quantity updates")
        
        while self.running:
            try:
                print("\n📊 Scan barcode for quantity update:")
                barcode = input().strip()
                
                if barcode and len(barcode) >= 6:
                    self.process_barcode_scan(barcode)
                    
            except KeyboardInterrupt:
                logger.info("🛑 Barcode scanning stopped")
                break
            except Exception as e:
                logger.error(f"❌ Barcode scanning error: {e}")
                time.sleep(1)
    
    def process_barcode_scan(self, barcode):
        """Process scanned barcode and send to API + IoT Hub"""
        try:
            logger.info(f"📊 Processing barcode: {barcode}")
            
            # Send to API
            api_success = self._send_to_api(barcode)
            
            # Send to IoT Hub
            iot_success = self._send_to_iot_hub(barcode)
            
            if api_success and iot_success:
                logger.info(f"✅ Barcode {barcode} processed successfully (API + IoT Hub)")
            elif api_success:
                logger.info(f"✅ Barcode {barcode} sent to API (IoT Hub failed)")
            elif iot_success:
                logger.info(f"✅ Barcode {barcode} sent to IoT Hub (API failed)")
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
            config = {
                "device_id": self.device_id,
                "server_url": self.server_url,
                "connection_string": self.connection_string,
                "registered": self.registered,
                "registration_time": datetime.now().isoformat()
            }
            
            config_file = "/etc/pi_plug_play.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("💾 Configuration saved")
        except Exception as e:
            logger.warning(f"⚠️ Could not save config: {e}")
    
    def _load_config(self):
        """Load existing configuration"""
        try:
            config_file = "/etc/pi_plug_play.json"
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    
                self.device_id = config.get("device_id")
                self.server_url = config.get("server_url")
                self.connection_string = config.get("connection_string")
                self.registered = config.get("registered", False)
                
                logger.info("📂 Configuration loaded")
                logger.info(f"🆔 Device ID: {self.device_id}")
                logger.info(f"✅ Registered: {self.registered}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Could not load config: {e}")
        return False
    
    def run(self):
        """Main execution flow"""
        logger.info("🚀 Starting Plug-and-Play Client...")
        
        # Step 1: Load existing config
        config_loaded = self._load_config()
        
        # Step 2: Discover server
        if not self.server_url:
            if not self.discover_server():
                logger.error("❌ Cannot continue without server connection")
                return False
        
        # Step 3: Check if already registered
        if self.registered and self.device_id and self.connection_string:
            logger.info("✅ Device already registered")
            logger.info(f"🆔 Device ID: {self.device_id}")
            
            # Connect to IoT Hub
            try:
                self.iot_client = IoTHubDeviceClient.create_from_connection_string(self.connection_string)
                self.iot_client.connect()
                logger.info("✅ Connected to IoT Hub")
            except Exception as e:
                logger.warning(f"⚠️ IoT Hub connection failed: {e}")
            
            # Start barcode scanning
            self.start_barcode_scanning()
            
        else:
            # Step 4: Wait for barcode registration
            logger.info("📱 Device not registered - entering plug-and-play mode")
            
            if self.wait_for_barcode_registration():
                # Registration successful, start scanning
                self.start_barcode_scanning()
            else:
                logger.error("❌ Registration failed")
                return False
        
        return True

def main():
    """Main entry point"""
    client = PiPlugAndPlayClient()
    
    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("🛑 Plug-and-Play Client stopped")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        client.running = False

if __name__ == "__main__":
    main()
