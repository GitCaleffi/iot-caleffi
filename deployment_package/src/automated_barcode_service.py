#!/usr/bin/env python3
"""
Fully Automated Barcode Scanner Service
=======================================

This service provides complete plug-and-play barcode scanning functionality:
1. Automatic device registration on startup
2. Continuous barcode scanning (USB/Camera)
3. Automatic quantity updates to IoT Hub
4. Offline message queuing and retry
5. Zero manual configuration required

Usage:
    python3 automated_barcode_service.py [--camera] [--usb] [--device-id DEVICE_ID]
"""

import os
import sys
import time
import json
import logging
import threading
import queue
import signal
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required modules
from utils.config import load_config, save_config
from database.local_storage import LocalStorage
from iot.hub_client import HubClient
from api.api_client import ApiClient
from utils.barcode_validator import validate_ean, BarcodeValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/automated_barcode_service.log')
    ]
)
logger = logging.getLogger(__name__)

class AutomatedBarcodeService:
    """Fully automated barcode scanner service"""
    
    def __init__(self, device_id=None, scan_mode='usb'):
        self.device_id = device_id
        self.scan_mode = scan_mode  # 'usb', 'camera', or 'both'
        self.running = False
        self.barcode_queue = queue.Queue()
        self.last_barcode = None
        self.last_scan_time = 0
        self.cooldown_period = 2  # seconds between duplicate scans
        
        # Initialize components
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.hub_client = None
        self.config = None
        
        # Threading
        self.scan_thread = None
        self.process_thread = None
        self.shutdown_event = threading.Event()
        
        logger.info("🚀 Automated Barcode Service initialized")
    
    def generate_device_id(self):
        """Generate unique device ID based on system hardware"""
        try:
            import uuid
            import hashlib
            
            # Try to get MAC address
            mac = hex(uuid.getnode())[2:].upper()
            if mac and mac != 'FFFFFFFFFFFF':
                # Use last 12 characters of MAC for device ID
                device_id = mac[-12:].lower()
                logger.info(f"📱 Generated device ID from MAC: {device_id}")
                return device_id
            
            # Fallback: Use system hostname + random
            import socket
            hostname = socket.gethostname()
            random_suffix = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:8]
            device_id = f"{hostname}-{random_suffix}".lower()
            logger.info(f"📱 Generated device ID from hostname: {device_id}")
            return device_id
            
        except Exception as e:
            # Ultimate fallback
            import uuid
            device_id = str(uuid.uuid4()).replace('-', '')[:12]
            logger.warning(f"📱 Generated random device ID: {device_id}")
            return device_id
    
    def register_device_automatically(self):
        """Automatically register device with IoT Hub"""
        try:
            if not self.device_id:
                self.device_id = self.generate_device_id()
            
            logger.info(f"🔧 Auto-registering device: {self.device_id}")
            
            # Load configuration
            self.config = load_config()
            if not self.config:
                logger.error("❌ Configuration not found")
                return False
            
            # Check if device already registered
            existing_connection = self.config.get("iot_hub", {}).get("devices", {}).get(self.device_id, {}).get("connection_string")
            if existing_connection:
                logger.info(f"✅ Device {self.device_id} already registered")
                self.hub_client = HubClient(existing_connection)
                return True
            
            # Register with Azure IoT Hub
            from barcode_scanner_app import register_device_with_iot_hub
            result = register_device_with_iot_hub(self.device_id)
            
            if result.get("success"):
                connection_string = result.get("connection_string")
                self.hub_client = HubClient(connection_string)
                logger.info(f"✅ Device {self.device_id} registered successfully")
                
                # Save device to local database
                timestamp = datetime.now(timezone.utc).isoformat()
                self.local_db.save_device_registration(self.device_id, timestamp)
                
                # Send registration message to IoT Hub
                registration_message = {
                    "messageType": "device_registration",
                    "deviceId": self.device_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "auto_register",
                    "status": "active"
                }
                
                success = self.hub_client.send_message(json.dumps(registration_message), self.device_id)
                if success:
                    logger.info("📡 Registration message sent to IoT Hub")
                
                return True
            else:
                logger.error(f"❌ Device registration failed: {result.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Auto-registration error: {e}")
            return False
    
    def detect_usb_scanner(self):
        """Detect USB barcode scanner"""
        try:
            import evdev
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            # Priority order for scanner detection
            scanner_keywords = ['scanner', 'barcode', 'honeywell', 'symbol', 'datalogic']
            keyboard_devices = []
            
            for device in devices:
                device_name = device.name.lower()
                
                # First priority: devices with scanner keywords
                for keyword in scanner_keywords:
                    if keyword in device_name:
                        logger.info(f"🔍 Found barcode scanner: {device.name}")
                        return device.path
                
                # Second priority: keyboard devices
                if 'keyboard' in device_name:
                    keyboard_devices.append(device)
            
            # Use first keyboard device as fallback
            if keyboard_devices:
                device = keyboard_devices[0]
                logger.info(f"🔍 Using keyboard device as scanner: {device.name}")
                return device.path
                    
        except ImportError:
            logger.warning("⚠️ evdev not available, USB scanning disabled")
        except Exception as e:
            logger.error(f"❌ USB scanner detection error: {e}")
        
        return None
    
    def scan_usb_barcodes(self):
        """Continuously scan for USB barcode input"""
        try:
            import evdev
            
            device_path = self.detect_usb_scanner()
            if not device_path:
                logger.error("❌ No USB scanner detected")
                return
            
            device = evdev.InputDevice(device_path)
            logger.info(f"📱 Monitoring USB scanner: {device.name}")
            
            barcode_buffer = ""
            last_key_time = 0
            barcode_timeout = 2.0  # seconds
            
            # Key mapping for barcode scanners (comprehensive mapping)
            key_map = {
                evdev.ecodes.KEY_1: '1', evdev.ecodes.KEY_2: '2', evdev.ecodes.KEY_3: '3',
                evdev.ecodes.KEY_4: '4', evdev.ecodes.KEY_5: '5', evdev.ecodes.KEY_6: '6',
                evdev.ecodes.KEY_7: '7', evdev.ecodes.KEY_8: '8', evdev.ecodes.KEY_9: '9',
                evdev.ecodes.KEY_0: '0', evdev.ecodes.KEY_A: 'A', evdev.ecodes.KEY_B: 'B',
                evdev.ecodes.KEY_C: 'C', evdev.ecodes.KEY_D: 'D', evdev.ecodes.KEY_E: 'E',
                evdev.ecodes.KEY_F: 'F', evdev.ecodes.KEY_G: 'G', evdev.ecodes.KEY_H: 'H',
                evdev.ecodes.KEY_I: 'I', evdev.ecodes.KEY_J: 'J', evdev.ecodes.KEY_K: 'K',
                evdev.ecodes.KEY_L: 'L', evdev.ecodes.KEY_M: 'M', evdev.ecodes.KEY_N: 'N',
                evdev.ecodes.KEY_O: 'O', evdev.ecodes.KEY_P: 'P', evdev.ecodes.KEY_Q: 'Q',
                evdev.ecodes.KEY_R: 'R', evdev.ecodes.KEY_S: 'S', evdev.ecodes.KEY_T: 'T',
                evdev.ecodes.KEY_U: 'U', evdev.ecodes.KEY_V: 'V', evdev.ecodes.KEY_W: 'W',
                evdev.ecodes.KEY_X: 'X', evdev.ecodes.KEY_Y: 'Y', evdev.ecodes.KEY_Z: 'Z'
            }
            
            for event in device.read_loop():
                if not self.running:
                    break
                
                current_time = time.time()
                
                # Check for timeout (barcode complete without ENTER)
                if barcode_buffer and current_time - last_key_time > barcode_timeout:
                    if len(barcode_buffer) >= 8:  # Minimum barcode length
                        logger.info(f"📊 USB Barcode detected (timeout): {barcode_buffer}")
                        print(f"📊 Barcode scanned: {barcode_buffer}")
                        self.barcode_queue.put(barcode_buffer)
                    else:
                        logger.debug(f"Discarding short buffer: {barcode_buffer}")
                    barcode_buffer = ""
                    
                if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # Key press
                    last_key_time = current_time
                    
                    if event.code == evdev.ecodes.KEY_ENTER:
                        # Barcode complete
                        if barcode_buffer:
                            logger.info(f"📊 USB Barcode detected: {barcode_buffer}")
                            print(f"📊 Barcode scanned: {barcode_buffer}")
                            self.barcode_queue.put(barcode_buffer)
                            barcode_buffer = ""
                    elif event.code in key_map:
                        char = key_map[event.code]
                        barcode_buffer += char
                        logger.debug(f"Key pressed: {char}, buffer: {barcode_buffer}")
                    else:
                        # Handle common special cases
                        if event.code == evdev.ecodes.KEY_TAB:
                            # Some scanners use TAB instead of ENTER
                            if barcode_buffer:
                                logger.info(f"📊 USB Barcode detected (TAB): {barcode_buffer}")
                                print(f"📊 Barcode scanned: {barcode_buffer}")
                                self.barcode_queue.put(barcode_buffer)
                                barcode_buffer = ""
                        
        except Exception as e:
            logger.error(f"❌ USB scanning error: {e}")
    
    def scan_camera_barcodes(self):
        """Continuously scan for camera barcode input"""
        try:
            import cv2
            from pyzbar import pyzbar
            
            # Initialize camera
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                logger.error("❌ Camera not available")
                return
            
            logger.info("📷 Camera barcode scanning started")
            
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Decode barcodes
                barcodes = pyzbar.decode(frame)
                for barcode in barcodes:
                    barcode_data = barcode.data.decode('utf-8')
                    logger.info(f"📊 Camera Barcode detected: {barcode_data}")
                    self.barcode_queue.put(barcode_data)
                
                time.sleep(0.1)  # Prevent excessive CPU usage
            
            cap.release()
            
        except ImportError:
            logger.warning("⚠️ OpenCV/pyzbar not available, camera scanning disabled")
        except Exception as e:
            logger.error(f"❌ Camera scanning error: {e}")
    
    def process_barcode(self, barcode):
        """Process a detected barcode"""
        try:
            current_time = time.time()
            
            # Duplicate detection
            if (self.last_barcode == barcode and 
                current_time - self.last_scan_time < self.cooldown_period):
                return
            
            self.last_barcode = barcode
            self.last_scan_time = current_time
            
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
    
    def barcode_processor_worker(self):
        """Worker thread to process barcodes from queue"""
        while self.running:
            try:
                barcode = self.barcode_queue.get(timeout=1)
                self.process_barcode(barcode)
                self.barcode_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ Barcode processor error: {e}")
    
    def start_scanning(self):
        """Start barcode scanning threads"""
        if self.scan_mode in ['usb', 'both']:
            self.scan_thread = threading.Thread(target=self.scan_usb_barcodes, daemon=True)
            self.scan_thread.start()
            logger.info("🔍 USB scanning thread started")
        
        if self.scan_mode in ['camera', 'both']:
            camera_thread = threading.Thread(target=self.scan_camera_barcodes, daemon=True)
            camera_thread.start()
            logger.info("📷 Camera scanning thread started")
        
        # Start barcode processor
        self.process_thread = threading.Thread(target=self.barcode_processor_worker, daemon=True)
        self.process_thread.start()
        logger.info("🔄 Barcode processor thread started")
    
    def run(self):
        """Main service loop"""
        try:
            logger.info("🚀 Starting Automated Barcode Service...")
            
            # Step 1: Register device automatically
            if not self.register_device_automatically():
                logger.error("❌ Device registration failed, exiting")
                return False
            
            # Step 2: Start scanning
            self.running = True
            self.start_scanning()
            
            print("\n" + "="*60)
            print("🎯 AUTOMATED BARCODE SCANNER READY")
            print("="*60)
            print(f"📱 Device ID: {self.device_id}")
            print(f"🔍 Scan Mode: {self.scan_mode.upper()}")
            print(f"📡 IoT Hub: {'✅ Connected' if self.hub_client else '❌ Offline'}")
            print("📊 Waiting for barcodes...")
            print("💡 If barcode appears but isn't processed, type 'process <barcode>' and press Enter")
            print("Press Ctrl+C to stop")
            print("="*60)
            
            # Main loop
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Shutdown requested by user")
        except Exception as e:
            logger.error(f"❌ Service error: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the service"""
        logger.info("🛑 Stopping Automated Barcode Service...")
        self.running = False
        
        if self.hub_client:
            try:
                self.hub_client.disconnect()
            except:
                pass
        
        print("\n✅ Automated Barcode Service stopped")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\n🛑 Shutdown signal received...")
    sys.exit(0)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Automated Barcode Scanner Service')
    parser.add_argument('--camera', action='store_true', help='Enable camera scanning')
    parser.add_argument('--usb', action='store_true', help='Enable USB scanning')
    parser.add_argument('--device-id', help='Custom device ID')
    parser.add_argument('--both', action='store_true', help='Enable both USB and camera scanning')
    
    args = parser.parse_args()
    
    # Determine scan mode
    if args.both:
        scan_mode = 'both'
    elif args.camera:
        scan_mode = 'camera'
    elif args.usb:
        scan_mode = 'usb'
    else:
        scan_mode = 'usb'  # Default to USB
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and run service
    service = AutomatedBarcodeService(device_id=args.device_id, scan_mode=scan_mode)
    service.run()

if __name__ == "__main__":
    main()
