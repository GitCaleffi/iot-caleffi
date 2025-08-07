#!/usr/bin/env python3
"""
Enhanced Barcode Scanner Main Application
Supports commercial-scale plug-and-play deployment using barcodes only
Designed for 1000+ device deployment without manual device ID input
"""

import sys
import time
import threading
import select
from datetime import datetime, timezone
import logging
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from utils.config import load_config
from database.local_storage import LocalStorage
from iot.barcode_hub_client import BarcodeHubClient
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.barcode_device_mapper import barcode_mapper

# Optional OTA import
try:
    from ota.update_client import OTAUpdateClient
    OTA_AVAILABLE = True
except ImportError:
    try:
        from ota.ota_update_client import OTAUpdateClient
        OTA_AVAILABLE = True
    except ImportError:
        OTAUpdateClient = None
        OTA_AVAILABLE = False
        logger.warning("OTA update client not available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class CommercialBarcodeReader:
    """
    Commercial-scale barcode reader with plug-and-play functionality.
    Works with barcodes only - no manual device ID input required.
    """
    
    def __init__(self):
        """Initialize the commercial barcode reader"""
        print("Initializing Commercial Barcode Scanner System...")
        print("Designed for plug-and-play deployment with 1000+ devices")
        print("="*60)
        
        # Load configuration
        self.config = load_config()
        if self.config is None:
            raise Exception("Failed to load configuration")
        
        # Get IoT Hub owner connection string for device registration
        self.iot_hub_connection_string = self.config["iot_hub"]["connection_string"]
        if not self.iot_hub_connection_string:
            raise Exception("IoT Hub connection string not found in configuration")
        
        # Initialize local storage
        self.storage = LocalStorage()
        
        # Initialize barcode hub client
        self.hub_client = BarcodeHubClient(self.iot_hub_connection_string)
        
        # Initialize dynamic registration service
        self.registration_service = get_dynamic_registration_service(self.iot_hub_connection_string)
        if not self.registration_service:
            raise Exception("Failed to initialize dynamic registration service")
        
        # Current session state
        self.current_barcode = None
        self.current_device_id = None
        self.session_scans = 0
        
        # Connection status
        self.hub_connected = False
        
        # Initialize OTA update client (optional)
        if OTA_AVAILABLE and OTAUpdateClient:
            try:
                self.ota_client = OTAUpdateClient()
                self.check_for_updates = True
                # Start update checker thread
                self.update_thread = threading.Thread(target=self._update_checker, daemon=True)
                self.update_thread.start()
                logger.info("OTA update client initialized successfully")
            except Exception as e:
                logger.warning(f"OTA update client initialization failed: {e}")
                self.ota_client = None
                self.check_for_updates = False
        else:
            logger.info("OTA update client not available - running without OTA updates")
            self.ota_client = None
            self.check_for_updates = False
        
        # Test mode for manual input
        self.test_mode = False
        
        print("✓ Commercial Barcode Scanner System initialized successfully")
        print("✓ Ready for plug-and-play barcode scanning")
    
    def check_system_status(self) -> bool:
        """Check system connections and readiness"""
        print("\nChecking system status...")
        
        try:
            # Test local database
            self.storage.test_connection()
            print("✓ Local database connection successful")
            
            # Test Azure IoT Hub Registry connection
            if self.registration_service.test_connection():
                print("✓ Azure IoT Hub Registry connection successful")
            else:
                print("! Azure IoT Hub Registry connection failed")
                return False
            
            # Show system statistics
            stats = barcode_mapper.get_mapping_stats()
            print(f"✓ System ready - {stats.get('total_mappings', 0)} device mappings, {stats.get('registered_devices', 0)} registered")
            
            return True
            
        except Exception as e:
            print(f"✗ System check failed: {e}")
            return False
    
    def process_barcode_scan(self, barcode: str) -> bool:
        """
        Process a barcode scan with full plug-and-play functionality.
        This is the main method for commercial deployment.
        """
        try:
            print(f"\n{'='*50}")
            print(f"PROCESSING BARCODE: {barcode}")
            print(f"{'='*50}")
            
            # Validate barcode format
            if not barcode or not barcode.strip():
                print("✗ Invalid barcode: empty")
                return False
            
            barcode = barcode.strip()
            
            if not barcode.isdigit():
                print(f"✗ Invalid barcode format: {barcode}. Must be numeric.")
                return False
            
            valid_lengths = [8, 12, 13, 14]
            if len(barcode) not in valid_lengths:
                print(f"✗ Invalid barcode length: {len(barcode)}. Must be one of: {valid_lengths} digits.")
                return False
            
            # Step 1: Get or create device mapping
            print("Step 1: Resolving device ID from barcode...")
            device_id = barcode_mapper.get_device_id_for_barcode(barcode)
            if not device_id:
                print("✗ Failed to resolve device ID from barcode")
                return False
            
            print(f"✓ Device ID resolved: {barcode} -> {device_id}")
            
            # Update current session
            self.current_barcode = barcode
            self.current_device_id = device_id
            
            # Step 2: Store scan locally first (ensures no data loss)
            print("Step 2: Storing scan locally...")
            timestamp = self.storage.save_scan(device_id, barcode)
            print(f"✓ Scan stored locally: {barcode} at {timestamp}")
            
            # Step 3: Send to Azure IoT Hub (with auto-registration)
            print("Step 3: Sending to Azure IoT Hub...")
            success = self.hub_client.send_barcode_message(barcode)
            
            if success:
                # Mark as sent in local storage
                self.storage.mark_sent_to_hub(device_id, barcode, timestamp)
                print(f"✓ Barcode sent to Azure IoT Hub and marked as sent: {barcode}")
                self.hub_connected = True
                self.session_scans += 1
            else:
                print(f"! Failed to send to Azure IoT Hub, stored locally for retry: {barcode}")
                self.hub_connected = False
            
            # Step 4: Show session summary
            print(f"\nSession Summary:")
            print(f"  Current device: {device_id}")
            print(f"  Session scans: {self.session_scans}")
            print(f"  Azure IoT Hub: {'Connected' if self.hub_connected else 'Offline'}")
            
            return True
            
        except Exception as e:
            print(f"✗ Error processing barcode {barcode}: {e}")
            logger.error(f"Error processing barcode {barcode}: {e}")
            return False
    
    def read_barcode(self, prompt: str = "Ready for barcode scan...") -> str:
        """Read barcode from USB scanner or manual input"""
        try:
            print(f"\n{prompt}")
            
            if self.test_mode:
                # Manual input for testing
                barcode = input("Enter barcode manually (test mode): ").strip()
                if barcode:
                    print(f"Barcode entered: {barcode}")
                    return barcode
                return None
            else:
                # USB scanner input with timeout
                timeout = 30  # 30 seconds timeout
                
                print("Waiting for barcode scan... (30s timeout)")
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
    
    def retry_unsent_scans(self):
        """Retry sending unsent scans to Azure IoT Hub"""
        try:
            unsent_scans = self.storage.get_unsent_scans()
            if not unsent_scans:
                return
            
            print(f"\nRetrying {len(unsent_scans)} unsent scans...")
            
            for scan in unsent_scans:
                try:
                    # Use the barcode from the scan to send via barcode hub client
                    success = self.hub_client.send_barcode_message(scan['barcode'])
                    
                    if success:
                        self.storage.mark_sent_to_hub(
                            scan['device_id'], 
                            scan['barcode'], 
                            scan['timestamp']
                        )
                        print(f"✓ Retried scan: {scan['barcode']}")
                    else:
                        print(f"! Failed to retry scan: {scan['barcode']}")
                        break  # Stop retrying if we fail
                        
                except Exception as e:
                    print(f"! Error retrying scan {scan['barcode']}: {e}")
                    break
                    
        except Exception as e:
            print(f"Error retrying unsent scans: {e}")
    
    def show_statistics(self):
        """Show system and session statistics"""
        print(f"\n{'='*50}")
        print("SYSTEM STATISTICS")
        print(f"{'='*50}")
        
        try:
            # Barcode mapping stats
            mapping_stats = barcode_mapper.get_mapping_stats()
            print(f"\nDevice Mapping Statistics:")
            print(f"  Total mappings: {mapping_stats.get('total_mappings', 0)}")
            print(f"  Azure registered: {mapping_stats.get('registered_devices', 0)}")
            print(f"  Pending registrations: {mapping_stats.get('pending_registrations', 0)}")
            print(f"  Recent activity (24h): {mapping_stats.get('recent_activity', 0)}")
            
            # Registration service stats
            if self.registration_service:
                reg_stats = self.registration_service.get_registration_statistics()
                print(f"\nRegistration Statistics:")
                print(f"  Success rate: {reg_stats.get('registration_success_rate', 0)}%")
                print(f"  Total barcode mappings: {reg_stats.get('total_barcode_mappings', 0)}")
            
            # Local storage stats
            recent_scans = self.storage.get_recent_scans(10)
            print(f"\nLocal Storage:")
            print(f"  Recent scans: {len(recent_scans)}")
            
            unsent_scans = self.storage.get_unsent_scans()
            print(f"  Unsent scans: {len(unsent_scans)}")
            
            # Current session
            print(f"\nCurrent Session:")
            print(f"  Current barcode: {self.current_barcode or 'None'}")
            print(f"  Current device ID: {self.current_device_id or 'None'}")
            print(f"  Session scans: {self.session_scans}")
            print(f"  Azure IoT Hub: {'Connected' if self.hub_connected else 'Offline'}")
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
    
    def _update_checker(self):
        """Background thread for OTA updates"""
        if not self.ota_client:
            return
        
        # Wait for system to stabilize
        time.sleep(30)
        
        while self.check_for_updates:
            try:
                print("\nChecking for OTA updates...")
                update_available = self.ota_client.apply_update()
                
                if update_available:
                    print("✓ Update applied successfully! Application will restart.")
                else:
                    print("✓ No updates available")
                
                # Check every hour
                for _ in range(60):
                    if not self.check_for_updates:
                        break
                    time.sleep(60)
                    
            except Exception as e:
                print(f"! Error checking for updates: {e}")
                time.sleep(300)  # 5 minutes retry on error
    
    def run_interactive_mode(self):
        """Run interactive barcode scanning mode"""
        print(f"\n{'='*60}")
        print("COMMERCIAL BARCODE SCANNER - INTERACTIVE MODE")
        print("Plug-and-play operation - no device ID required")
        print(f"{'='*60}")
        print("\nCommands:")
        print("  scan    - Scan a barcode")
        print("  test    - Toggle test mode (manual input)")
        print("  retry   - Retry unsent scans")
        print("  stats   - Show statistics")
        print("  status  - Check system status")
        print("  quit    - Exit application")
        print(f"{'='*60}")
        
        while True:
            try:
                command = input("\nCommand (scan/test/retry/stats/status/quit): ").strip().lower()
                
                if command == 'quit' or command == 'q':
                    print("Shutting down...")
                    break
                elif command == 'scan' or command == 's':
                    barcode = self.read_barcode()
                    if barcode:
                        self.process_barcode_scan(barcode)
                    else:
                        print("No barcode received")
                elif command == 'test' or command == 't':
                    self.test_mode = not self.test_mode
                    print(f"Test mode: {'ON' if self.test_mode else 'OFF'}")
                elif command == 'retry' or command == 'r':
                    self.retry_unsent_scans()
                elif command == 'stats':
                    self.show_statistics()
                elif command == 'status':
                    self.check_system_status()
                else:
                    print("Unknown command. Use: scan, test, retry, stats, status, quit")
                    
            except KeyboardInterrupt:
                print("\nShutting down...")
                break
            except Exception as e:
                print(f"Error: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            print("Cleaning up resources...")
            
            # Stop update checker
            self.check_for_updates = False
            
            # Disconnect from Azure IoT Hub
            if self.hub_client:
                self.hub_client.disconnect()
            
            # Close local storage
            if hasattr(self.storage, 'close'):
                self.storage.close()
            
            print("✓ Cleanup completed")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")


def main():
    """Main function for commercial barcode scanner"""
    scanner = None
    
    try:
        print("Commercial Scale Barcode Scanner System")
        print("Plug-and-play deployment for 1000+ devices")
        print("No manual device ID input required")
        
        # Initialize scanner
        scanner = CommercialBarcodeReader()
        
        # Check system status
        if not scanner.check_system_status():
            print("System check failed. Please check configuration and connections.")
            return 1
        
        # Run interactive mode
        scanner.run_interactive_mode()
        
        return 0
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        logger.error(f"Application error: {e}")
        return 1
    finally:
        if scanner:
            scanner.cleanup()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
