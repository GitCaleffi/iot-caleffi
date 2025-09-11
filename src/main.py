import os
import sys
from pathlib import Path
import time
import select
import logging
import threading

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging to suppress excessive Azure IoT messages
logging.getLogger('azure.iot').setLevel(logging.ERROR)

from src.utils.config import load_config
from src.iot.hub_client import HubClient
from src.database.local_storage import LocalStorage
from src.ota.update_client import OTAUpdateClient

class BarcodeReader:
    def __init__(self):
        self.config = load_config()
        if self.config is None:
            raise Exception("Failed to load configuration")
            
        # Initialize local storage first
        self.storage = LocalStorage()
        
        # Try to get device ID from local storage first
        saved_id = self.storage.get_device_id()
        if saved_id:
            self.device_id = saved_id
            print(f"✓ Loaded device ID from local storage: {self.device_id}")
        else:
            # No saved device ID yet - will be set on first scan
            self.device_id = None
            
        # Initialize IoT Hub client
        self.hub_client = HubClient(self.config["iot_hub"]["connection_string"])
        
        # Track IoT Hub connection status
        self.hub_connected = False
        
        # Initialize test mode (for manual input testing)
        self.test_mode = False
        
        # Initialize OTA update client
        self.ota_client = OTAUpdateClient()
        
        # Flag to control update checking
        self.check_for_updates = True
        
        # Start update checker thread
        self.update_thread = threading.Thread(target=self._update_checker, daemon=True)
        self.update_thread.start()

    def check_system_status(self):
        """Check connections to IoT Hub and Database"""
        try:
            # Test database connection
            self.storage.test_connection()
            print("✓ Database connection successful")
            
            # Try to test IoT Hub connection, but continue even if it fails
            try:
                self.hub_client.test_connection()
                print("✓ IoT Hub connection successful")
                self.hub_connected = True
            except Exception as e:
                print("! IoT Hub connection failed - will operate in offline mode")
                print("! Will store scans locally and retry sending later")
                self.hub_connected = False
            
            return True
        except Exception as e:
            print(f"✗ System check failed: {e}")
            return False

    def read_barcode(self, prompt="Ready for barcode scan..."):
        """Read barcode from USB handreader scanner or manual input in test mode"""
        try:
            print(prompt)
            
            if self.test_mode:
                # For testing: use manual input
                barcode = input("Enter barcode manually (test mode): ").strip()
                if barcode:
                    print(f"Barcode entered: {barcode}")
                    return barcode
                return None
            else:
                # The handreader typically sends the barcode followed by a carriage return
                # We'll use a timeout to avoid blocking indefinitely
                timeout = self.config.get("barcode_scanner", {}).get("scan_timeout", 5000) / 1000  # Convert ms to seconds
                
                # Check if there's input available within the timeout period
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if ready:
                    barcode = sys.stdin.readline().strip()
                    if barcode:
                        print(f"Barcode scanned: {barcode}")
                        return barcode
                
                print("No barcode detected within timeout period.")
                return None
                
        except (EOFError, KeyboardInterrupt):
            return None
        except Exception as e:
            print(f"Error reading barcode: {e}")
            return None

    def process_barcode(self, barcode):
        """Process scanned barcode and handle data storage"""
        try:
            # Store in local database first to ensure data is not lost and get timestamp
            timestamp = self.storage.save_scan(self.device_id, barcode)
            print(f"✓ Saved barcode to local database: {barcode}")
            
            # Only try to send to IoT Hub if we're connected
            if self.hub_connected:
                try:
                    success = self.hub_client.send_message(barcode, self.device_id)
                    if success:
                        # Mark as sent in local storage
                        self.storage.mark_sent_to_hub(self.device_id, barcode, timestamp)
                        print(f"✓ Sent barcode to IoT Hub and marked as sent: {barcode}")
                    else:
                        print(f"! Failed to send to IoT Hub, will retry later: {barcode}")
                except Exception as e:
                    print(f"! Exception sending to IoT Hub, will retry later: {e}")
                    # Try to reconnect for next time
                    self.hub_connected = False
            else:
                print(f"! IoT Hub not connected, barcode saved locally for later sending: {barcode}")
             
            return True
        except Exception as e:
            print(f"✗ Error processing barcode: {e}")
            return False

    def retry_unsent_scans(self):
        """Attempt to resend unsent scans stored locally"""
        # If not connected to IoT Hub, try to reconnect
        if not self.hub_connected:
            try:
                self.hub_client.test_connection()
                print("✓ Reconnected to IoT Hub")
                self.hub_connected = True
            except Exception:
                # Still not connected, skip retrying for now
                return
        
        scans = self.storage.get_unsent_scans()
        if scans and self.hub_connected:
            print(f"\nRetrying {len(scans)} unsent scans...")
            for rec in scans:
                try:
                    success = self.hub_client.send_message(rec['barcode'], rec['device_id'])
                    if success:
                        self.storage.mark_sent_to_hub(rec['device_id'], rec['barcode'], rec['timestamp'])
                        print(f"✓ Retried unsent scan: {rec['barcode']}")
                except Exception as e:
                    print(f"! Failed to resend scan {rec['barcode']}: {e}")
                    self.hub_connected = False
                    break  # Stop trying if we lose connection
    
    def _update_checker(self):
        """Background thread to periodically check for OTA updates"""
        # Wait for device ID to be set before checking for updates
        while self.device_id is None:
            time.sleep(5)
        
        # Initial delay to allow system to stabilize
        time.sleep(30)
        
        while self.check_for_updates:
            try:
                print("\nChecking for OTA updates...")
                update_available = self.ota_client.apply_update()
                
                if update_available:
                    print("✓ Update applied successfully! Application will restart.")
                    # The OTA client will handle the restart
                else:
                    print("✓ No updates available or update not needed")
                
                # Check for updates every hour
                for _ in range(60):
                    if not self.check_for_updates:
                        break
                    time.sleep(60)  # 1 minute sleep intervals
            except Exception as e:
                print(f"! Error checking for updates: {e}")
                time.sleep(300)  # 5 minutes retry on error

def main():
    barcode_reader = None
    try:
        # Load configuration first
        config = load_config()
        if config is None:
            raise Exception("Failed to load configuration. Please check your config.json file and environment variables.")
        
        # Ensure device ID is set in config
        if "device_id" not in config.get("iot_hub", {}):
            device_id = "694833b1b872"  # Default device ID from memory
            if "iot_hub" not in config:
                config["iot_hub"] = {}
            config["iot_hub"]["device_id"] = device_id
            
            # Save updated config
            config_path = project_root / "config.json"
            with open(config_path, "w") as f:
                import json
                json.dump(config, f, indent=2)
        
        print("\nInitializing barcode reader...")
        barcode_reader = BarcodeReader()
        
        # Set test mode for manual input (change to False for production with real handreader)
        barcode_reader.test_mode = True
        
        # Check system status
        if not barcode_reader.check_system_status():
            raise Exception("System check failed")

        # Check if we already have a device ID from local storage
        if barcode_reader.device_id:
            print(f"✓ Using device ID from local storage: {barcode_reader.device_id}")
        else:
            # Get device ID by scanning
            print("\nPlease scan the device ID barcode...")
            first_barcode = barcode_reader.read_barcode("Scan or enter the device ID barcode:")
            if not first_barcode:
                raise Exception("No device ID scanned or entered")

            barcode_reader.device_id = first_barcode
            print(f"✓ Device ID set: {first_barcode}")
            # Save device ID to local storage
            barcode_reader.storage.save_device_id(first_barcode)

        # Main scanning loop
        print("\nReady to scan barcodes... (Ctrl+C to exit)")
        while True:
            barcode_reader.retry_unsent_scans()
            barcode = barcode_reader.read_barcode()
            if barcode:
                barcode_reader.process_barcode(barcode)
                time.sleep(0.5)  # Small delay between scans

    except KeyboardInterrupt:
        print("\nExiting gracefully...")
        if barcode_reader:
            barcode_reader.check_for_updates = False
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if barcode_reader is not None:
            try:
                if hasattr(barcode_reader, 'hub_client'):
                    # Old method
                    # device = registry_manager.create_or_update_device(device_id, device_info, if_match='*')
                    # New method
                    device = barcode_reader.hub_client.registry_manager.create_device_with_sas(barcode_reader.device_id, barcode_reader.config["iot_hub"]["primary_key"], barcode_reader.config["iot_hub"]["secondary_key"], "ENABLED")
                    barcode_reader.hub_client.disconnect()
                if hasattr(barcode_reader, 'storage'):
                    barcode_reader.storage.close()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")

if __name__ == "__main__":
    main()