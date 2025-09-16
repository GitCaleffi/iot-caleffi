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
        """Setup device ID - will be set from first barcode scan"""
        self.device_id = None
        logger.info("🔧 Device ID will be set from first numeric barcode scan")
    
    def register_device_with_barcode(self, numeric_barcode):
        """Register device using numeric barcode as device ID"""
        try:
            from iot.dynamic_registration_service import DynamicRegistrationService
            
            # Use numeric barcode as device ID
            self.device_id = f"device-{numeric_barcode}"
            logger.info(f"🔧 Setting device ID from barcode: {self.device_id}")
            
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
    
    def listen_for_barcodes(self):
        """Listen for barcode input from USB scanner and handle device registration"""
        if not self.device_id:
            logger.info("🔧 DEVICE REGISTRATION MODE")
            logger.info("📱 Please scan a NUMERIC barcode to register this device")
            logger.info("   (The barcode will become your device ID)")
            
            # Wait for first barcode to register device
            try:
                numeric_barcode = input().strip()
                if numeric_barcode and numeric_barcode.isdigit():
                    logger.info(f"🔍 Registering device with barcode: {numeric_barcode}")
                    connection_string = self.register_device_with_barcode(numeric_barcode)
                    if not connection_string:
                        logger.error("❌ Device registration failed")
                        return
                else:
                    logger.error("❌ Please scan a NUMERIC barcode for device registration")
                    return
            except KeyboardInterrupt:
                logger.info("🛑 Registration cancelled")
                return
        else:
            # Device already registered, get connection string
            connection_string = self.register_device_with_barcode(self.device_id.split('-')[-1])
        
        logger.info("🎯 Listening for barcode scans... (Press Ctrl+C to stop)")
        logger.info("📱 Scan barcodes with your USB scanner")
        
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
        """Start the barcode scanner service"""
        logger.info("🚀 Starting Automatic Barcode Scanner Service")
        logger.info("==================================================")
        
        self.running = True
        
        # Start listening for barcodes (will handle device registration)
        self.listen_for_barcodes()
        
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
