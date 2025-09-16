#!/usr/bin/env python3
"""
Simple Plug-and-Play Barcode Scanner
====================================

This script provides a simple, automatic barcode scanner that:
1. Uses direct keyboard input capture
2. Automatically processes barcodes for device 7079fa7ab32e
3. Sends quantity updates to IoT Hub
4. Requires no manual intervention

Usage: python3 simple_barcode_scanner.py
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime, timezone

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
from utils.config import load_config
from database.local_storage import LocalStorage
from iot.hub_client import HubClient
from api.api_client import ApiClient
from utils.barcode_validator import validate_ean, BarcodeValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleBarcodeScanner:
    """Simple plug-and-play barcode scanner"""
    
    def __init__(self, device_id="7079fa7ab32e"):
        self.device_id = device_id
        self.running = False
        self.last_barcode = None
        self.last_scan_time = 0
        self.cooldown_period = 2  # seconds between duplicate scans
        
        # Initialize components
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.hub_client = None
        self.config = None
        
        logger.info(f"🚀 Simple Barcode Scanner initialized for device: {device_id}")
    
    def initialize_hub_client(self):
        """Initialize IoT Hub client for the device"""
        try:
            self.config = load_config()
            if not self.config:
                logger.error("❌ Configuration not found")
                return False
            
            # Get device connection string from config
            device_connection_string = self.config.get("iot_hub", {}).get("devices", {}).get(self.device_id, {}).get("connection_string")
            
            if device_connection_string:
                self.hub_client = HubClient(device_connection_string)
                logger.info(f"✅ IoT Hub client initialized for device {self.device_id}")
                return True
            else:
                logger.error(f"❌ No connection string found for device {self.device_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Hub client initialization error: {e}")
            return False
    
    def process_barcode(self, barcode):
        """Process a detected barcode automatically"""
        try:
            current_time = time.time()
            
            # Duplicate detection
            if (self.last_barcode == barcode and 
                current_time - self.last_scan_time < self.cooldown_period):
                return
            
            self.last_barcode = barcode
            self.last_scan_time = current_time
            
            print(f"\n🔄 Processing barcode: {barcode}")
            logger.info(f"🔄 Processing barcode: {barcode}")
            
            # Validate barcode
            try:
                validated_barcode = validate_ean(barcode)
                logger.info(f"✅ Barcode validation successful: {validated_barcode}")
            except BarcodeValidationError as e:
                logger.warning(f"⚠️ Barcode validation warning: {e} (continuing anyway)")
                validated_barcode = barcode
            
            # Save to local database
            timestamp = self.local_db.save_scan(self.device_id, validated_barcode)
            logger.info(f"💾 Saved scan to local database")
            
            # Send quantity update to IoT Hub
            if self.hub_client:
                quantity_message = {
                    "messageType": "quantity_update",
                    "scannedBarcode": validated_barcode,
                    "deviceId": self.device_id,
                    "quantity": 1,
                    "action": "scan",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                success = self.hub_client.send_message(json.dumps(quantity_message), self.device_id)
                if success:
                    logger.info(f"📡 Quantity update sent to IoT Hub: {validated_barcode}")
                    print(f"✅ Barcode {validated_barcode} processed and sent to IoT Hub")
                else:
                    logger.warning(f"⚠️ Failed to send to IoT Hub, saved locally")
                    print(f"⚠️ Barcode {validated_barcode} saved locally (IoT Hub offline)")
            else:
                print(f"⚠️ Barcode {validated_barcode} saved locally (IoT Hub not connected)")
            
            # Send to API
            try:
                api_result = self.api_client.send_barcode_scan(self.device_id, validated_barcode, 1)
                if api_result.get("success"):
                    logger.info("📡 Quantity update sent to API")
                else:
                    logger.warning("⚠️ API send failed")
            except Exception as api_error:
                logger.warning(f"⚠️ API error: {api_error}")
            
        except Exception as e:
            logger.error(f"❌ Barcode processing error: {e}")
            print(f"❌ Error processing barcode: {e}")
    
    def keyboard_input_listener(self):
        """Listen for keyboard input (barcode scanner input)"""
        print("\n📊 Waiting for barcode input...")
        print("💡 Scan a barcode or type it manually and press Enter")
        print("💡 Type 'quit' to exit")
        
        while self.running:
            try:
                # Get input from keyboard/barcode scanner
                user_input = input().strip()
                
                if user_input.lower() == 'quit':
                    self.running = False
                    break
                
                if user_input and len(user_input) >= 8:  # Minimum barcode length
                    # Check if it's all digits (typical barcode)
                    if user_input.isdigit():
                        self.process_barcode(user_input)
                    else:
                        print(f"⚠️ Invalid barcode format: {user_input} (must be numeric)")
                elif user_input:
                    print(f"⚠️ Barcode too short: {user_input} (minimum 8 digits)")
                    
            except EOFError:
                # Handle Ctrl+D
                break
            except KeyboardInterrupt:
                # Handle Ctrl+C
                break
            except Exception as e:
                logger.error(f"❌ Input error: {e}")
    
    def run(self):
        """Main service loop"""
        try:
            print("\n" + "="*60)
            print("🎯 SIMPLE BARCODE SCANNER")
            print("="*60)
            print(f"📱 Device ID: {self.device_id}")
            print("🔍 Mode: Keyboard Input")
            
            # Initialize IoT Hub connection
            hub_connected = self.initialize_hub_client()
            print(f"📡 IoT Hub: {'✅ Connected' if hub_connected else '❌ Offline'}")
            
            print("="*60)
            
            # Start the service
            self.running = True
            self.keyboard_input_listener()
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service"""
        logger.info("🛑 Stopping Simple Barcode Scanner...")
        self.running = False
        
        if self.hub_client:
            try:
                self.hub_client.disconnect()
            except:
                pass
        
        print("\n✅ Simple Barcode Scanner stopped")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple Barcode Scanner')
    parser.add_argument('--device-id', default='7079fa7ab32e', help='Device ID to use')
    
    args = parser.parse_args()
    
    # Create and run scanner
    scanner = SimpleBarcodeScanner(device_id=args.device_id)
    scanner.run()

if __name__ == "__main__":
    main()
