#!/usr/bin/env python3
"""
Streamlined Barcode Scanner Application
Two-step flow: Device Registration → EAN Barcode Scanning
"""

import json
import os
import sys
import logging
import sqlite3
import requests
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import uuid
import socket

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent / "deployment_package" / "src"))

try:
    from api.api_client import ApiClient
    from iot.hub_client import HubClient
    from database.local_storage import LocalStorage
    from iot.dynamic_registration_service import get_dynamic_registration_service
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure all required modules are available")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlined_scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StreamlinedBarcodeScanner:
    def __init__(self, config_path="deployment_package/config.json"):
        """Initialize the streamlined barcode scanner"""
        self.config_path = config_path
        self.config = self.load_config()
        self.storage = LocalStorage(self.config.get("database", {}).get("path", "barcode_scans.db"))
        self.api_client = ApiClient(self.config.get("api", {}).get("base_url", ""))
        self.current_device_id = None
        
        # Initialize database
        self.init_database()
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def init_database(self):
        """Initialize database tables"""
        try:
            # Create devices table if not exists
            self.storage.execute_query("""
                CREATE TABLE IF NOT EXISTS registered_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT UNIQUE NOT NULL,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    iot_hub_registered BOOLEAN DEFAULT 0,
                    api_registered BOOLEAN DEFAULT 0
                )
            """)
            
            # Create barcode_scans table if not exists  
            self.storage.execute_query("""
                CREATE TABLE IF NOT EXISTS barcode_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    barcode TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    iot_hub_sent BOOLEAN DEFAULT 0,
                    api_sent BOOLEAN DEFAULT 0,
                    FOREIGN KEY (device_id) REFERENCES registered_devices (device_id)
                )
            """)
            
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def is_device_registered(self, device_id: str) -> bool:
        """Check if device is already registered in database"""
        try:
            result = self.storage.execute_query(
                "SELECT COUNT(*) FROM registered_devices WHERE device_id = ?", 
                (device_id,)
            )
            return result[0][0] > 0 if result else False
        except Exception as e:
            logger.error(f"Error checking device registration: {e}")
            return False
    
    def register_device(self, device_id: str) -> dict:
        """
        Register a new device in the system
        Flow: Check database → Register if new → Save to database → Send to IoT Hub/API
        """
        logger.info(f"🔄 Starting device registration for: {device_id}")
        
        result = {
            "success": False,
            "device_id": device_id,
            "already_registered": False,
            "database_saved": False,
            "iot_hub_sent": False,
            "api_sent": False,
            "message": ""
        }
        
        try:
            # Step 1: Check if device already registered
            if self.is_device_registered(device_id):
                result["already_registered"] = True
                result["success"] = True
                result["message"] = f"✅ Device {device_id} already registered"
                logger.info(result["message"])
                return result
            
            # Step 2: Save device to database
            try:
                self.storage.execute_query("""
                    INSERT INTO registered_devices (device_id, registration_date, status)
                    VALUES (?, ?, 'active')
                """, (device_id, datetime.now(timezone.utc).isoformat()))
                
                result["database_saved"] = True
                logger.info(f"✅ Device {device_id} saved to database")
                
            except Exception as e:
                logger.error(f"❌ Failed to save device to database: {e}")
                result["message"] = f"Database save failed: {e}"
                return result
            
            # Step 3: Register with IoT Hub
            try:
                registration_service = get_dynamic_registration_service()
                if registration_service:
                    connection_string = registration_service.register_device_with_azure(device_id)
                    if connection_string:
                        # Send registration message to IoT Hub
                        hub_client = HubClient(connection_string)
                        if hub_client.connect():
                            registration_message = {
                                "messageType": "device_registration",
                                "deviceId": device_id,
                                "action": "register",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "status": "registered"
                            }
                            
                            if hub_client.send_message(json.dumps(registration_message), device_id):
                                result["iot_hub_sent"] = True
                                logger.info(f"✅ Device registration sent to IoT Hub")
                                
                                # Update database
                                self.storage.execute_query(
                                    "UPDATE registered_devices SET iot_hub_registered = 1 WHERE device_id = ?",
                                    (device_id,)
                                )
                            else:
                                logger.warning(f"⚠️ Failed to send registration to IoT Hub")
                        else:
                            logger.warning(f"⚠️ Failed to connect to IoT Hub")
                    else:
                        logger.warning(f"⚠️ Failed to get connection string from registration service")
                else:
                    logger.warning(f"⚠️ Registration service not available")
                    
            except Exception as e:
                logger.error(f"❌ IoT Hub registration failed: {e}")
            
            # Step 4: Register with Frontend API
            try:
                api_payload = {
                    "deviceId": device_id,
                    "messageType": "device_registration",
                    "action": "register", 
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                response = self.api_client.confirm_registration(device_id)
                if response and response.get("success"):
                    result["api_sent"] = True
                    logger.info(f"✅ Device registration sent to API")
                    
                    # Update database
                    self.storage.execute_query(
                        "UPDATE registered_devices SET api_registered = 1 WHERE device_id = ?",
                        (device_id,)
                    )
                else:
                    logger.warning(f"⚠️ Failed to send registration to API")
                    
            except Exception as e:
                logger.error(f"❌ API registration failed: {e}")
            
            # Set current device
            self.current_device_id = device_id
            
            # Final result
            result["success"] = result["database_saved"]  # Success if at least saved to database
            if result["success"]:
                status_parts = []
                if result["iot_hub_sent"]: status_parts.append("IoT Hub")
                if result["api_sent"]: status_parts.append("API")
                
                if status_parts:
                    result["message"] = f"✅ Device {device_id} registered successfully (Database + {' + '.join(status_parts)})"
                else:
                    result["message"] = f"✅ Device {device_id} registered in database (Cloud services pending)"
            else:
                result["message"] = f"❌ Device registration failed"
                
            logger.info(result["message"])
            return result
            
        except Exception as e:
            logger.error(f"❌ Device registration error: {e}")
            result["message"] = f"Registration error: {e}"
            return result
    
    def scan_barcode(self, barcode: str, device_id: str = None, quantity: int = 1) -> dict:
        """
        Process EAN barcode scan and update quantity
        Flow: Validate device → Scan EAN → Update quantity → Send to IoT Hub/API
        """
        if not device_id:
            device_id = self.current_device_id
            
        if not device_id:
            return {
                "success": False,
                "message": "❌ No device registered. Please register a device first."
            }
        
        logger.info(f"🔄 Processing barcode scan: {barcode} for device: {device_id}")
        
        result = {
            "success": False,
            "device_id": device_id,
            "barcode": barcode,
            "quantity": quantity,
            "database_saved": False,
            "iot_hub_sent": False,
            "api_sent": False,
            "message": ""
        }
        
        try:
            # Step 1: Validate device is registered
            if not self.is_device_registered(device_id):
                result["message"] = f"❌ Device {device_id} not registered. Please register device first."
                logger.warning(result["message"])
                return result
            
            # Step 2: Save barcode scan to database
            try:
                self.storage.execute_query("""
                    INSERT INTO barcode_scans (device_id, barcode, quantity, scan_timestamp)
                    VALUES (?, ?, ?, ?)
                """, (device_id, barcode, quantity, datetime.now(timezone.utc).isoformat()))
                
                result["database_saved"] = True
                logger.info(f"✅ Barcode scan saved to database")
                
            except Exception as e:
                logger.error(f"❌ Failed to save barcode scan: {e}")
                result["message"] = f"Database save failed: {e}"
                return result
            
            # Step 3: Send to IoT Hub
            try:
                registration_service = get_dynamic_registration_service()
                if registration_service:
                    connection_string = registration_service.register_device_with_azure(device_id)
                    if connection_string:
                        hub_client = HubClient(connection_string)
                        if hub_client.connect():
                            quantity_message = {
                                "messageType": "quantity_update",
                                "deviceId": device_id,
                                "barcode": barcode,
                                "ean": barcode,
                                "quantity": quantity,
                                "action": "add",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            
                            if hub_client.send_message(json.dumps(quantity_message), device_id):
                                result["iot_hub_sent"] = True
                                logger.info(f"✅ Quantity update sent to IoT Hub")
                                
                                # Update database
                                self.storage.execute_query(
                                    "UPDATE barcode_scans SET iot_hub_sent = 1 WHERE device_id = ? AND barcode = ? ORDER BY id DESC LIMIT 1",
                                    (device_id, barcode)
                                )
                            else:
                                logger.warning(f"⚠️ Failed to send quantity update to IoT Hub")
                        else:
                            logger.warning(f"⚠️ Failed to connect to IoT Hub")
                    else:
                        logger.warning(f"⚠️ Failed to get connection string")
                else:
                    logger.warning(f"⚠️ Registration service not available")
                    
            except Exception as e:
                logger.error(f"❌ IoT Hub messaging failed: {e}")
            
            # Step 4: Send to Frontend API
            try:
                api_result = self.api_client.send_barcode_scan(device_id, barcode, quantity)
                if api_result and api_result.get("success"):
                    result["api_sent"] = True
                    logger.info(f"✅ Quantity update sent to API")
                    
                    # Update database
                    self.storage.execute_query(
                        "UPDATE barcode_scans SET api_sent = 1 WHERE device_id = ? AND barcode = ? ORDER BY id DESC LIMIT 1",
                        (device_id, barcode)
                    )
                else:
                    logger.warning(f"⚠️ Failed to send quantity update to API")
                    
            except Exception as e:
                logger.error(f"❌ API messaging failed: {e}")
            
            # Final result
            result["success"] = result["database_saved"]  # Success if at least saved to database
            if result["success"]:
                status_parts = []
                if result["iot_hub_sent"]: status_parts.append("IoT Hub")
                if result["api_sent"]: status_parts.append("API")
                
                if status_parts:
                    result["message"] = f"✅ Barcode {barcode} processed successfully (Database + {' + '.join(status_parts)})"
                else:
                    result["message"] = f"✅ Barcode {barcode} saved to database (Cloud services pending)"
            else:
                result["message"] = f"❌ Barcode processing failed"
                
            logger.info(result["message"])
            return result
            
        except Exception as e:
            logger.error(f"❌ Barcode scanning error: {e}")
            result["message"] = f"Scanning error: {e}"
            return result
    
    def get_device_status(self, device_id: str = None) -> dict:
        """Get status of registered device"""
        if not device_id:
            device_id = self.current_device_id
            
        if not device_id:
            return {"error": "No device specified"}
        
        try:
            # Get device info
            device_result = self.storage.execute_query(
                "SELECT * FROM registered_devices WHERE device_id = ?",
                (device_id,)
            )
            
            if not device_result:
                return {"error": f"Device {device_id} not found"}
            
            device_info = device_result[0]
            
            # Get scan count
            scan_result = self.storage.execute_query(
                "SELECT COUNT(*) FROM barcode_scans WHERE device_id = ?",
                (device_id,)
            )
            
            scan_count = scan_result[0][0] if scan_result else 0
            
            return {
                "device_id": device_info[1],
                "registration_date": device_info[2],
                "status": device_info[3],
                "iot_hub_registered": bool(device_info[4]),
                "api_registered": bool(device_info[5]),
                "total_scans": scan_count
            }
            
        except Exception as e:
            logger.error(f"Error getting device status: {e}")
            return {"error": str(e)}
    
    def list_registered_devices(self) -> list:
        """List all registered devices"""
        try:
            result = self.storage.execute_query(
                "SELECT device_id, registration_date, status FROM registered_devices ORDER BY registration_date DESC"
            )
            
            devices = []
            for row in result:
                devices.append({
                    "device_id": row[0],
                    "registration_date": row[1],
                    "status": row[2]
                })
            
            return devices
            
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []

def main():
    """Main function for testing the streamlined scanner"""
    print("🔄 Streamlined Barcode Scanner Test")
    print("=" * 50)
    
    # Initialize scanner
    scanner = StreamlinedBarcodeScanner()
    
    # Test device registration with your device ID
    device_id = "2379394fd95c"
    print(f"\n1. Testing Device Registration: {device_id}")
    registration_result = scanner.register_device(device_id)
    print(f"Result: {registration_result['message']}")
    
    # Test barcode scanning
    test_barcode = "1234567890123"  # Example EAN barcode
    print(f"\n2. Testing Barcode Scanning: {test_barcode}")
    scan_result = scanner.scan_barcode(test_barcode, device_id)
    print(f"Result: {scan_result['message']}")
    
    # Show device status
    print(f"\n3. Device Status:")
    status = scanner.get_device_status(device_id)
    if "error" not in status:
        print(f"Device ID: {status['device_id']}")
        print(f"Registration Date: {status['registration_date']}")
        print(f"Status: {status['status']}")
        print(f"IoT Hub Registered: {status['iot_hub_registered']}")
        print(f"API Registered: {status['api_registered']}")
        print(f"Total Scans: {status['total_scans']}")
    else:
        print(f"Error: {status['error']}")
    
    # List all devices
    print(f"\n4. All Registered Devices:")
    devices = scanner.list_registered_devices()
    for device in devices:
        print(f"- {device['device_id']} (registered: {device['registration_date']})")

if __name__ == "__main__":
    main()
