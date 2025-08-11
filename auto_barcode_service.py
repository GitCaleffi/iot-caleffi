#!/usr/bin/env python3
"""
Fully Automated Barcode Scanner Service
Zero-configuration, plug-and-play barcode scanning

This service:
1. Auto-detects USB barcode scanners
2. Auto-registers devices with IoT Hub
3. Auto-scans barcodes and sends to IoT/API
4. Requires NO user interaction or configuration
"""

import os
import sys
import time
import threading
import logging
import json
import uuid
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

try:
    from src.utils.config import load_config
    from src.iot.hub_client import HubClient
    from src.api.api_client import ApiClient
    from src.database.local_storage import LocalStorage
    from src.utils.dynamic_device_manager import device_manager
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback imports without src prefix
    try:
        from utils.config import load_config
        from iot.hub_client import HubClient
        from api.api_client import ApiClient
        from database.local_storage import LocalStorage
        from utils.dynamic_device_manager import device_manager
    except ImportError as e2:
        print(f"Fallback import error: {e2}")
        sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/auto_barcode_service.log')
    ]
)
logger = logging.getLogger(__name__)

class AutoBarcodeService:
    """Fully automated barcode scanning service"""
    
    def __init__(self):
        self.running = False
        self.config = load_config()
        self.storage = LocalStorage()
        self.api_client = ApiClient()
        self.device_id = self._generate_device_id()
        self.hub_client = None
        self.barcode_buffer = ""
        self.last_scan_time = 0
        
        # Initialize IoT Hub client
        if self.config and 'iot_hub' in self.config:
            connection_string = self.config['iot_hub']['connection_string']
            if connection_string and connection_string != "REPLACE_WITH_YOUR_IOT_HUB_CONNECTION_STRING":
                try:
                    self.hub_client = HubClient(connection_string)
                    logger.info("IoT Hub client initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize IoT Hub client: {e}")
        
        # Auto-register this device
        self._auto_register_device()
        
        logger.info(f"🚀 Auto Barcode Service initialized with device ID: {self.device_id}")
        logger.info("📱 Plug-and-play mode: Just connect scanner and start scanning!")
    
    def _generate_device_id(self):
        """Generate a unique device ID based on system info"""
        try:
            # Try to get system serial number
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        if serial and serial != '0000000000000000':
                            return f"scanner-{serial[-8:]}"
            
            # Fallback to MAC address
            result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                mac = result.stdout.strip().replace(':', '')
                return f"scanner-{mac[-8:]}"
            
        except Exception as e:
            logger.warning(f"Could not get system ID: {e}")
        
        # Final fallback to random ID
        random_id = str(uuid.uuid4())[:8]
        return f"scanner-{random_id}"
    
    def _auto_register_device(self):
        """Automatically register this device without user interaction"""
        try:
            logger.info(f"🔄 Auto-registering device: {self.device_id}")
            
            # Generate registration token automatically
            token = device_manager.generate_registration_token()
            
            # Register device automatically
            device_info = {
                "registration_method": "auto_plug_and_play",
                "auto_registered": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            success, message = device_manager.register_device(token, self.device_id, device_info)
            
            if success:
                logger.info(f"✅ Device {self.device_id} auto-registered successfully")
                
                # Send registration confirmation to IoT Hub
                if self.hub_client:
                    try:
                        confirmation_msg = {
                            "deviceId": self.device_id,
                            "status": "auto_registered",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "message": "Device auto-registered via plug-and-play"
                        }
                        self.hub_client.send_message(json.dumps(confirmation_msg), self.device_id)
                        logger.info("📡 Registration confirmation sent to IoT Hub")
                    except Exception as e:
                        logger.error(f"Failed to send registration to IoT Hub: {e}")
                
                # Save device locally
                self.storage.save_device_id(self.device_id)
                
            else:
                logger.error(f"❌ Auto-registration failed: {message}")
                
        except Exception as e:
            logger.error(f"Auto-registration error: {e}")
    
    def _process_barcode(self, barcode):
        """Process a scanned barcode automatically"""
        if not barcode or len(barcode) < 4:
            return
        
        logger.info(f"📦 Barcode scanned: {barcode}")
        
        try:
            # Create message payload
            message_payload = {
                "scannedBarcode": barcode,
                "deviceId": self.device_id,
                "quantity": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "auto_scanned": True
            }
            
            # Send to API
            api_success = False
            try:
                if self.api_client.is_online():
                    result = self.api_client.send_barcode_scan(self.device_id, barcode, 1)
                    api_success = result.get("success", False) if isinstance(result, dict) else result
                    if api_success:
                        logger.info("📡 Barcode sent to API successfully")
                    else:
                        logger.warning("⚠️ Failed to send barcode to API")
            except Exception as e:
                logger.error(f"API error: {e}")
            
            # Send to IoT Hub
            hub_success = False
            try:
                if self.hub_client:
                    hub_success = self.hub_client.send_message(barcode, self.device_id)
                    if hub_success:
                        logger.info("☁️ Barcode sent to IoT Hub successfully")
                    else:
                        logger.warning("⚠️ Failed to send barcode to IoT Hub")
            except Exception as e:
                logger.error(f"IoT Hub error: {e}")
            
            # Store locally for retry if needed
            if not (api_success or hub_success):
                self.storage.save_barcode_scan(self.device_id, barcode, datetime.now())
                logger.info("💾 Barcode stored locally for retry")
            
            # Always store in local database for history
            self.storage.save_scan(self.device_id, barcode, 1)
            
            # Success feedback
            if api_success or hub_success:
                logger.info(f"✅ SUCCESS: Barcode {barcode} processed and sent!")
            else:
                logger.warning(f"⚠️ PARTIAL: Barcode {barcode} stored locally, will retry when online")
                
        except Exception as e:
            logger.error(f"Error processing barcode {barcode}: {e}")
    
    def _listen_for_input(self):
        """Listen for barcode scanner input"""
        logger.info("🎧 Listening for barcode scanner input...")
        
        while self.running:
            try:
                # Read input line (barcode scanners typically send complete lines)
                line = input().strip()
                
                if line and len(line) >= 4:  # Valid barcode
                    self._process_barcode(line)
                    
            except EOFError:
                # No more input
                time.sleep(0.1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Input error: {e}")
                time.sleep(0.1)
    
    def start(self):
        """Start the automated barcode service"""
        logger.info("🚀 Starting Automated Barcode Scanner Service")
        logger.info("📱 PLUG-AND-PLAY MODE: Just scan barcodes - no setup required!")
        logger.info(f"🏷️ Device ID: {self.device_id}")
        
        self.running = True
        
        # Start input listener in background thread
        input_thread = threading.Thread(target=self._listen_for_input, daemon=True)
        input_thread.start()
        
        # Main service loop
        try:
            logger.info("✅ Service running! Scan barcodes now - they will be processed automatically")
            logger.info("Press Ctrl+C to stop")
            
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Service stopped by user")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service"""
        logger.info("🛑 Stopping Automated Barcode Scanner Service")
        self.running = False

def main():
    """Main entry point"""
    print("")
    print("🚀 AUTOMATED BARCODE SCANNER SERVICE")
    print("======================================")
    print("📱 PLUG-AND-PLAY MODE ACTIVATED")
    print("")
    print("✅ No setup required!")
    print("✅ No URLs to remember!")
    print("✅ No manual registration!")
    print("")
    print("Just scan barcodes and they will be automatically:")
    print("📡 Sent to the API")
    print("☁️ Sent to IoT Hub")
    print("💾 Stored locally")
    print("")
    print("======================================")
    print("")
    
    try:
        service = AutoBarcodeService()
        service.start()
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()