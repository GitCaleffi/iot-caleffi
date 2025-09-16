#!/usr/bin/env python3
"""
Automatic Barcode Processor for Device 7079fa7ab32e
==================================================

This script automatically processes barcodes for the specific device 7079fa7ab32e
without any manual intervention. Just scan a barcode and it will be processed.

Usage: python3 auto_barcode_processor.py
"""

import os
import sys
import time
import json
import logging
import signal
from datetime import datetime, timezone

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from barcode_scanner_app
from barcode_scanner_app import process_barcode_scan, load_config
from database.local_storage import LocalStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AutoBarcodeProcessor:
    """Automatic barcode processor for device 7079fa7ab32e"""
    
    def __init__(self):
        self.device_id = "7079fa7ab32e"
        self.running = False
        self.local_db = LocalStorage()
        
        # Ensure device is registered in local database
        self.ensure_device_registered()
        
        logger.info(f"🚀 Auto Barcode Processor initialized for device: {self.device_id}")
    
    def ensure_device_registered(self):
        """Ensure the device is registered in local database"""
        try:
            # Check if device exists in local database
            existing_device = self.local_db.get_device_id()
            
            if existing_device != self.device_id:
                # Register the device
                timestamp = datetime.now(timezone.utc).isoformat()
                self.local_db.save_device_registration(self.device_id, timestamp)
                logger.info(f"✅ Device {self.device_id} registered in local database")
            else:
                logger.info(f"✅ Device {self.device_id} already registered")
                
        except Exception as e:
            logger.error(f"❌ Device registration error: {e}")
    
    def process_barcode_automatically(self, barcode):
        """Process barcode using the existing barcode_scanner_app logic"""
        try:
            logger.info(f"🔄 Auto-processing barcode: {barcode}")
            print(f"\n🔄 Processing barcode: {barcode}")
            
            # Use the existing process_barcode_scan function with our device ID
            result = process_barcode_scan(barcode, self.device_id)
            
            # Display result
            if "✅" in result:
                print(f"✅ Success: {result}")
                logger.info(f"✅ Barcode processed successfully: {barcode}")
            elif "⚠️" in result:
                print(f"⚠️ Warning: {result}")
                logger.warning(f"⚠️ Barcode processing warning: {barcode}")
            else:
                print(f"ℹ️ Info: {result}")
                logger.info(f"ℹ️ Barcode processing info: {barcode}")
            
            return result
            
        except Exception as e:
            error_msg = f"❌ Error processing barcode {barcode}: {e}"
            logger.error(error_msg)
            print(error_msg)
            return error_msg
    
    def listen_for_barcodes(self):
        """Listen for barcode input"""
        print("\n📊 Waiting for barcode input...")
        print("💡 Scan a barcode or type it and press Enter")
        print("💡 Type 'quit' or 'exit' to stop")
        print("💡 Type 'status' to check device status")
        
        while self.running:
            try:
                # Get input from keyboard/barcode scanner
                user_input = input("Barcode: ").strip()
                
                if user_input.lower() in ['quit', 'exit']:
                    self.running = False
                    break
                
                if user_input.lower() == 'status':
                    self.show_status()
                    continue
                
                if user_input and len(user_input) >= 8:  # Minimum barcode length
                    self.process_barcode_automatically(user_input)
                elif user_input:
                    print(f"⚠️ Barcode too short: {user_input} (minimum 8 characters)")
                    
            except EOFError:
                # Handle Ctrl+D
                break
            except KeyboardInterrupt:
                # Handle Ctrl+C
                break
            except Exception as e:
                logger.error(f"❌ Input error: {e}")
    
    def show_status(self):
        """Show current device status"""
        try:
            config = load_config()
            device_registered = config.get("iot_hub", {}).get("devices", {}).get(self.device_id) is not None
            
            print(f"\n📊 Device Status:")
            print(f"   📱 Device ID: {self.device_id}")
            print(f"   🔧 Registered: {'✅ Yes' if device_registered else '❌ No'}")
            print(f"   💾 Local DB: ✅ Connected")
            
            # Check recent scans
            try:
                recent_scans = self.local_db.get_recent_scans(limit=5)
                if recent_scans:
                    print(f"   📊 Recent scans: {len(recent_scans)}")
                    for scan in recent_scans[:3]:  # Show last 3
                        print(f"      - {scan.get('barcode', 'N/A')} at {scan.get('timestamp', 'N/A')}")
                else:
                    print(f"   📊 Recent scans: None")
            except:
                print(f"   📊 Recent scans: Unable to retrieve")
            
            print()
            
        except Exception as e:
            print(f"❌ Status error: {e}")
    
    def run(self):
        """Main service loop"""
        try:
            print("\n" + "="*60)
            print("🎯 AUTOMATIC BARCODE PROCESSOR")
            print("="*60)
            print(f"📱 Device ID: {self.device_id}")
            print("🔍 Mode: Automatic Processing")
            print("📡 Integration: IoT Hub + API + Local Database")
            print("="*60)
            
            # Start the service
            self.running = True
            self.listen_for_barcodes()
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service"""
        logger.info("🛑 Stopping Auto Barcode Processor...")
        self.running = False
        print("\n✅ Auto Barcode Processor stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutdown signal received...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run processor
    processor = AutoBarcodeProcessor()
    processor.run()

if __name__ == "__main__":
    main()
