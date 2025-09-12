#!/usr/bin/env python3
"""
Fully Automatic USB Barcode Scanner
- Auto-detects USB scanner
- Auto-registers device on first scan
- Auto-sends all scanned barcodes to IoT Hub
"""

import sys
import time
import logging
import json
import threading
from pathlib import Path
from datetime import datetime, timezone

# Try importing evdev for USB scanner support
try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    USB_SCANNER_AVAILABLE = True
except ImportError:
    print("❌ evdev not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, categorize, ecodes
    USB_SCANNER_AVAILABLE = True

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from database.local_storage import LocalStorage
from utils.config import load_config, save_config
from api.api_client import ApiClient
from iot.hub_client import HubClient
from iot.connection_manager import connection_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
local_db = LocalStorage()
api_client = ApiClient()

class AutoUSBScanner:
    def __init__(self):
        self.device_id = None
        self.scanner_device = None
        self.running = False
        self.scan_count = 0
        self.last_scan_time = None
        
    def find_usb_scanner(self):
        """Auto-detect USB barcode scanner"""
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            for device in devices:
                device_name = device.name.lower()
                # Check for common barcode scanner names
                scanner_keywords = ['barcode', 'scanner', 'honeywell', 'symbol', 
                                  'datalogic', 'zebra', 'usb barcode', 'hid']
                
                if any(keyword in device_name for keyword in scanner_keywords):
                    logger.info(f"✅ Found USB scanner: {device.name} at {device.path}")
                    return device
                    
                # Check if device has keyboard-like capabilities (many scanners act as keyboards)
                caps = device.capabilities()
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    # Check for alphanumeric keys and Enter key
                    if ecodes.KEY_A in keys and ecodes.KEY_ENTER in keys:
                        logger.info(f"✅ Found keyboard-like scanner: {device.name} at {device.path}")
                        return device
                        
            logger.warning("⚠️ No USB scanner detected. Waiting for connection...")
            return None
            
        except Exception as e:
            logger.error(f"Error detecting USB scanner: {e}")
            return None
    
    def auto_register_device(self, barcode):
        """Auto-register device using first scanned barcode"""
        try:
            # Check if already registered
            existing_device = local_db.get_device_id()
            if existing_device:
                self.device_id = existing_device
                logger.info(f"✅ Using existing device ID: {self.device_id}")
                return True
                
            logger.info(f"🔄 Auto-registering device with barcode: {barcode}")
            
            # Check if online
            if not api_client.is_online():
                # Save barcode locally for later registration
                logger.warning("⚠️ Offline - saving barcode locally")
                self.device_id = barcode  # Use barcode as temporary device ID
                local_db.save_device_id(self.device_id)
                return True
                
            # Try API registration
            api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
            payload = {"scannedBarcode": barcode}
            
            api_result = api_client.send_registration_barcode(api_url, payload)
            
            if api_result.get("success", False) and "response" in api_result:
                try:
                    response_data = json.loads(api_result["response"])
                    if response_data.get("deviceId"):
                        self.device_id = response_data.get("deviceId")
                        local_db.save_device_id(self.device_id)
                        
                        # Register with IoT Hub
                        self.register_with_iot_hub(self.device_id)
                        
                        # Send registration message to IoT Hub
                        self.send_registration_message(self.device_id, barcode)
                        
                        logger.info(f"✅ Device auto-registered: {self.device_id}")
                        return True
                except:
                    pass
                    
            # Fallback: use barcode as device ID
            self.device_id = barcode
            local_db.save_device_id(self.device_id)
            self.register_with_iot_hub(self.device_id)
            self.send_registration_message(self.device_id, barcode)
            logger.info(f"✅ Device registered with barcode as ID: {self.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Auto-registration error: {e}")
            # Use barcode as device ID as last resort
            self.device_id = barcode
            local_db.save_device_id(self.device_id)
            return True
            
    def register_with_iot_hub(self, device_id):
        """Register device with Azure IoT Hub"""
        try:
            from azure.iot.hub import IoTHubRegistryManager
            import base64
            import os
            import re
            
            config = load_config()
            if not config or "iot_hub" not in config:
                logger.warning("IoT Hub config not found")
                return False
                
            # Check if already registered
            devices = config.get("iot_hub", {}).get("devices", {})
            if device_id in devices:
                logger.info(f"Device {device_id} already in IoT Hub config")
                return True
                
            hub_conn_string = config["iot_hub"]["connection_string"]
            
            # Create registry manager
            registry_manager = IoTHubRegistryManager.from_connection_string(hub_conn_string)
            
            # Try to get or create device
            try:
                device = registry_manager.get_device(device_id)
                logger.info(f"Device {device_id} exists in IoT Hub")
            except:
                # Create new device
                primary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                secondary_key = base64.b64encode(os.urandom(32)).decode('utf-8')
                device = registry_manager.create_device_with_sas(
                    device_id, primary_key, secondary_key, "enabled"
                )
                logger.info(f"Created device {device_id} in IoT Hub")
                
            # Get device key
            primary_key = device.authentication.symmetric_key.primary_key
            
            # Extract hostname
            hostname_match = re.search(r'HostName=([^;]+)', hub_conn_string)
            if not hostname_match:
                return False
                
            hostname = hostname_match.group(1)
            device_conn_string = f"HostName={hostname};DeviceId={device_id};SharedAccessKey={primary_key}"
            
            # Update config
            if "devices" not in config["iot_hub"]:
                config["iot_hub"]["devices"] = {}
                
            config["iot_hub"]["devices"][device_id] = {
                "connection_string": device_conn_string,
                "deviceId": device_id
            }
            
            save_config(config)
            logger.info(f"✅ Device {device_id} registered with IoT Hub")
            return True
            
        except ImportError:
            logger.warning("Azure IoT Hub SDK not available")
            return False
        except Exception as e:
            logger.error(f"IoT Hub registration error: {e}")
            return False
            
    def send_registration_message(self, device_id, barcode):
        """Send registration message to IoT Hub"""
        try:
            config = load_config()
            devices = config.get("iot_hub", {}).get("devices", {})
            
            if device_id in devices:
                conn_string = devices[device_id]["connection_string"]
                hub_client = HubClient(conn_string)
                
                # Create registration message payload
                registration_message = {
                    "deviceId": device_id,
                    "messageType": "device_registration",
                    "action": "register",
                    "scannedBarcode": barcode,
                    "registrationMethod": "usb_scanner_plug_and_play",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "registered"
                }
                
                # Send registration message to IoT Hub
                success = hub_client.send_message(json.dumps(registration_message), device_id)
                if success:
                    logger.info(f"📡 USB Scanner registration message sent to IoT Hub for device {device_id}")
                    print(f"✅ Registration message sent to IoT Hub")
                else:
                    logger.warning(f"⚠️ Failed to send registration message to IoT Hub")
                    print(f"⚠️ Registration message failed")
                    
        except Exception as e:
            logger.error(f"Error sending registration message: {e}")
            print(f"⚠️ Registration message error: {e}")
            
    def process_barcode(self, barcode):
        """Process scanned barcode automatically"""
        try:
            self.scan_count += 1
            self.last_scan_time = datetime.now()
            
            logger.info(f"📱 Scanned #{self.scan_count}: {barcode}")
            
            # Auto-register on first scan if needed
            if not self.device_id:
                if not self.auto_register_device(barcode):
                    logger.error("Failed to auto-register device")
                    return
                    
            # Save scan locally
            timestamp = local_db.save_scan(self.device_id, barcode, 1)
            
            # Send to IoT Hub
            config = load_config()
            devices = config.get("iot_hub", {}).get("devices", {})
            
            if self.device_id in devices:
                conn_string = devices[self.device_id]["connection_string"]
                
                # Use connection manager for persistent connection
                success = connection_manager.send_message(
                    self.device_id, conn_string, barcode
                )
                
                if success:
                    local_db.mark_sent_to_hub(self.device_id, barcode, timestamp)
                    logger.info(f"✅ Sent to IoT Hub: {barcode}")
                    print(f"\n✅ Scan #{self.scan_count} sent to IoT Hub: {barcode}")
                else:
                    logger.warning(f"⚠️ Failed to send to IoT Hub, saved locally: {barcode}")
                    print(f"\n⚠️ Scan #{self.scan_count} saved locally: {barcode}")
            else:
                logger.warning(f"⚠️ Device not in IoT Hub config, saved locally: {barcode}")
                print(f"\n⚠️ Scan #{self.scan_count} saved locally: {barcode}")
                
        except Exception as e:
            logger.error(f"Error processing barcode: {e}")
            print(f"\n❌ Error processing barcode: {e}")
            
    def monitor_scanner(self):
        """Monitor USB scanner for barcodes"""
        if not self.scanner_device:
            return
            
        try:
            logger.info(f"🔍 Monitoring scanner: {self.scanner_device.name}")
            print(f"\n📱 Ready to scan! Device: {self.scanner_device.name}")
            print("Scan any barcode to process automatically...")
            print("Press Ctrl+C to stop\n")
            
            barcode_buffer = ""
            
            for event in self.scanner_device.read_loop():
                if not self.running:
                    break
                    
                if event.type == ecodes.EV_KEY and event.value == 1:  # Key press
                    key_code = event.code
                    
                    # Map key codes to characters
                    if key_code >= ecodes.KEY_1 and key_code <= ecodes.KEY_9:
                        barcode_buffer += str(key_code - ecodes.KEY_1 + 1)
                    elif key_code == ecodes.KEY_0:
                        barcode_buffer += "0"
                    elif key_code >= ecodes.KEY_A and key_code <= ecodes.KEY_Z:
                        barcode_buffer += chr(ord('a') + key_code - ecodes.KEY_A)
                    elif key_code == ecodes.KEY_ENTER:
                        # Barcode complete
                        if barcode_buffer.strip():
                            self.process_barcode(barcode_buffer.strip())
                            barcode_buffer = ""
                    elif key_code == ecodes.KEY_SPACE:
                        barcode_buffer += " "
                    elif key_code == ecodes.KEY_MINUS:
                        barcode_buffer += "-"
                    elif key_code == ecodes.KEY_DOT:
                        barcode_buffer += "."
                        
        except Exception as e:
            logger.error(f"Scanner monitoring error: {e}")
            print(f"\n❌ Scanner error: {e}")
            
    def wait_for_scanner(self):
        """Wait for USB scanner to be connected"""
        print("\n🔌 Waiting for USB barcode scanner...")
        print("Please connect your USB barcode scanner\n")
        
        while self.running:
            self.scanner_device = self.find_usb_scanner()
            if self.scanner_device:
                print(f"✅ Scanner connected: {self.scanner_device.name}")
                return True
            time.sleep(2)
            
        return False
        
    def run(self):
        """Main run loop"""
        self.running = True
        
        print("\n" + "="*50)
        print("🚀 AUTOMATIC USB BARCODE SCANNER")
        print("="*50)
        
        # Load existing device ID if available
        existing_device = local_db.get_device_id()
        if existing_device:
            self.device_id = existing_device
            print(f"✅ Using registered device: {self.device_id}")
        else:
            print("📝 Device will auto-register on first scan")
            
        try:
            while self.running:
                # Wait for scanner if not connected
                if not self.scanner_device:
                    if not self.wait_for_scanner():
                        break
                        
                # Monitor scanner
                self.monitor_scanner()
                
                # If scanner disconnected, wait for reconnection
                if self.running:
                    print("\n⚠️ Scanner disconnected. Waiting for reconnection...")
                    self.scanner_device = None
                    time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\n\n👋 Stopping automatic scanner...")
        finally:
            self.stop()
            
    def stop(self):
        """Stop the scanner"""
        self.running = False
        if self.scan_count > 0:
            print(f"\n📊 Session Summary:")
            print(f"  • Total scans: {self.scan_count}")
            print(f"  • Device ID: {self.device_id}")
            print(f"  • Last scan: {self.last_scan_time}")
        print("\n✅ Scanner stopped")
        
    def process_offline_queue(self):
        """Process any offline queued messages"""
        try:
            if not api_client.is_online():
                return
                
            unsent = local_db.get_unsent_scans()
            if not unsent:
                return
                
            logger.info(f"Processing {len(unsent)} offline messages...")
            
            config = load_config()
            for msg in unsent:
                device_id = msg["device_id"]
                barcode = msg["barcode"]
                timestamp = msg["timestamp"]
                
                devices = config.get("iot_hub", {}).get("devices", {})
                if device_id in devices:
                    conn_string = devices[device_id]["connection_string"]
                    success = connection_manager.send_message(
                        device_id, conn_string, barcode
                    )
                    if success:
                        local_db.mark_sent_to_hub(device_id, barcode, timestamp)
                        logger.info(f"✅ Sent offline message: {barcode}")
                        
        except Exception as e:
            logger.error(f"Error processing offline queue: {e}")

def main():
    """Main entry point"""
    scanner = AutoUSBScanner()
    
    # Start offline queue processor in background
    def queue_processor():
        while scanner.running:
            scanner.process_offline_queue()
            time.sleep(30)  # Check every 30 seconds
            
    queue_thread = threading.Thread(target=queue_processor, daemon=True)
    queue_thread.start()
    
    # Run the scanner
    scanner.run()

if __name__ == "__main__":
    main()