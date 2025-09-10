#!/usr/bin/env python3
"""
Fully Automatic Barcode Scanner Service
No UI, No Server Dependencies - Pure Plug and Play
"""

import sys
import os
import json
import time
import threading
import logging
from datetime import datetime
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_barcode_service.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoBarcodeService:
    def __init__(self):
        self.running = False
        self.device_id = None
        self.config = self.load_config()
        self.setup_device_id()
        
    def load_config(self):
        """Load configuration from device_config.json"""
        config_path = current_dir / "device_config.json"
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"✅ Config loaded from {config_path}")
                return config
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}")
            # Default config
            return {
                "iot_hub": {
                    "connection_string": "HostName=iot-caleffi.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=YOUR_KEY"
                },
                "api": {
                    "base_url": "https://api2.caleffionline.it/api/v1"
                }
            }
    
    def setup_device_id(self):
        """Generate unique device ID based on system hardware"""
        try:
            # Try to get MAC address
            import uuid
            mac = hex(uuid.getnode())[2:].zfill(12)
            self.device_id = f"scanner-{mac[-8:]}"
            logger.info(f"🔧 Device ID generated: {self.device_id}")
        except Exception as e:
            # Fallback to timestamp-based ID
            timestamp = str(int(time.time()))[-8:]
            self.device_id = f"scanner-{timestamp}"
            logger.warning(f"⚠️ Using fallback device ID: {self.device_id}")
    
    def register_device(self):
        """Register device with IoT Hub"""
        try:
            from iot.dynamic_registration_service import DynamicRegistrationService
            
            # Create registration service
            reg_service = DynamicRegistrationService(self.config)
            
            # Register device
            connection_string = reg_service.register_device_with_azure(self.device_id)
            
            if connection_string:
                logger.info(f"✅ Device {self.device_id} registered successfully")
                return connection_string
            else:
                logger.error(f"❌ Failed to register device {self.device_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Device registration failed: {e}")
            return None
    
    def send_barcode_to_iot_hub(self, barcode, connection_string):
        """Send barcode scan to IoT Hub"""
        try:
            from iot.hub_client import HubClient
            
            hub_client = HubClient(connection_string)
            
            # Create message
            message_data = {
                "messageType": "barcode_scan",
                "deviceId": self.device_id,
                "barcode": barcode,
                "timestamp": datetime.now().isoformat(),
                "quantity": 1
            }
            
            # Send message
            result = hub_client.send_message(json.dumps(message_data), self.device_id)
            
            if result:
                logger.info(f"✅ Barcode {barcode} sent to IoT Hub successfully")
                return True
            else:
                logger.error(f"❌ Failed to send barcode {barcode} to IoT Hub")
                return False
                
        except Exception as e:
            logger.error(f"❌ IoT Hub send failed: {e}")
            return False
    
    def send_barcode_to_api(self, barcode):
        """Send barcode scan to API"""
        try:
            from api.api_client import ApiClient
            
            api_client = ApiClient(self.config["api"]["base_url"])
            
            # Send barcode scan
            result = api_client.send_barcode_scan(self.device_id, barcode, 1)
            
            if result and result.get("success"):
                logger.info(f"✅ Barcode {barcode} sent to API successfully")
                return True
            else:
                logger.error(f"❌ Failed to send barcode {barcode} to API")
                return False
                
        except Exception as e:
            logger.error(f"❌ API send failed: {e}")
            return False
    
    def process_barcode(self, barcode, connection_string):
        """Process a scanned barcode"""
        logger.info(f"🔍 Processing barcode: {barcode}")
        
        # Send to both IoT Hub and API in parallel
        iot_success = self.send_barcode_to_iot_hub(barcode, connection_string)
        api_success = self.send_barcode_to_api(barcode)
        
        # Log results
        if iot_success and api_success:
            logger.info(f"✅ Barcode {barcode} processed successfully (IoT Hub + API)")
        elif iot_success:
            logger.info(f"⚠️ Barcode {barcode} sent to IoT Hub only (API failed)")
        elif api_success:
            logger.info(f"⚠️ Barcode {barcode} sent to API only (IoT Hub failed)")
        else:
            logger.error(f"❌ Barcode {barcode} processing failed completely")
        
        return iot_success or api_success
    
    def listen_for_barcodes(self, connection_string):
        """Listen for barcode input from USB scanner"""
        logger.info("🎯 Listening for barcode scans... (Press Ctrl+C to stop)")
        logger.info("📱 Scan a barcode with your USB scanner")
        
        try:
            while self.running:
                try:
                    # Read barcode from stdin (USB scanners act like keyboards)
                    barcode = input().strip()
                    
                    if barcode:
                        # Process the barcode
                        self.process_barcode(barcode, connection_string)
                        
                except KeyboardInterrupt:
                    logger.info("🛑 Service stopped by user")
                    break
                except EOFError:
                    # Handle case where input is closed
                    time.sleep(0.1)
                    continue
                except Exception as e:
                    logger.error(f"❌ Error reading barcode: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            logger.error(f"❌ Barcode listening failed: {e}")
    
    def start(self):
        """Start the automatic barcode service"""
        logger.info("🚀 Starting Automatic Barcode Scanner Service")
        logger.info("=" * 50)
        
        # Register device
        logger.info("🔧 Registering device...")
        connection_string = self.register_device()
        
        if not connection_string:
            logger.error("❌ Cannot start service without device registration")
            return False
        
        # Start service
        self.running = True
        logger.info("✅ Service started successfully")
        logger.info(f"📱 Device ID: {self.device_id}")
        logger.info("🎯 Ready for barcode scanning!")
        
        # Listen for barcodes
        self.listen_for_barcodes(connection_string)
        
        return True
    
    def stop(self):
        """Stop the service"""
        self.running = False
        logger.info("🛑 Service stopped")

def main():
    """Main entry point"""
    print("🔧 Automatic Barcode Scanner Service")
    print("=" * 40)
    print("✅ No UI required - Pure plug and play")
    print("📱 Just scan barcodes with your USB scanner")
    print("🌐 Automatic IoT Hub and API integration")
    print("=" * 40)
    
    # Create and start service
    service = AutoBarcodeService()
    
    try:
        service.start()
    except KeyboardInterrupt:
        print("\n🛑 Service stopped by user")
    except Exception as e:
        print(f"❌ Service failed: {e}")
    finally:
        service.stop()
        print("👋 Thank you for using the barcode scanner!")

if __name__ == "__main__":
    main()
