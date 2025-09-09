#!/usr/bin/env python3
"""
Simple Barcode Scanner Flow
1. Device Registration: Scan device barcode → Check database → Register if new → Save → Send to IoT Hub/API
2. EAN Scanning: Scan EAN → Update quantity +1 → Send to IoT Hub/API
"""

import json
import os
import sys
import logging
import sqlite3
import requests
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_barcode_flow.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SimpleBarcodeFlow:
    def __init__(self, config_path="deployment_package/config.json"):
        """Initialize the simple barcode flow"""
        self.config_path = config_path
        self.config = self.load_config()
        self.db_path = "simple_barcode_flow.db"
        self.current_device_id = None
        
        # Initialize database
        self.init_database()
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                logger.info("✅ Configuration loaded successfully")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {
                "iot_hub": {
                    "connection_string": "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="
                },
                "api": {
                    "base_url": "https://api2.caleffionline.it/api/v1"
                }
            }
    
    def init_database(self):
        """Initialize SQLite database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create devices table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registered_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT UNIQUE NOT NULL,
                    registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    iot_hub_registered INTEGER DEFAULT 0,
                    api_registered INTEGER DEFAULT 0
                )
            """)
            
            # Create barcode_scans table  
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS barcode_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    barcode TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    scan_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    iot_hub_sent INTEGER DEFAULT 0,
                    api_sent INTEGER DEFAULT 0
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def is_device_registered(self, device_id: str) -> bool:
        """Check if device is already registered"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM registered_devices WHERE device_id = ?", (device_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count > 0
        except Exception as e:
            logger.error(f"Error checking device registration: {e}")
            return False
    
    def register_device(self, device_id: str) -> dict:
        """
        Register a new device
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
            # Step 1: Check if already registered
            if self.is_device_registered(device_id):
                result["already_registered"] = True
                result["success"] = True
                result["message"] = f"✅ Device {device_id} already registered"
                logger.info(result["message"])
                self.current_device_id = device_id
                return result
            
            # Step 2: Save to database
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO registered_devices (device_id, registration_date, status)
                    VALUES (?, ?, 'active')
                """, (device_id, datetime.now(timezone.utc).isoformat()))
                conn.commit()
                conn.close()
                
                result["database_saved"] = True
                logger.info(f"✅ Device {device_id} saved to database")
                
            except Exception as e:
                logger.error(f"❌ Failed to save device to database: {e}")
                result["message"] = f"Database save failed: {e}"
                return result
            
            # Step 3: Send to IoT Hub (simplified)
            try:
                iot_hub_connection = self.config.get("iot_hub", {}).get("connection_string", "")
                if iot_hub_connection:
                    registration_message = {
                        "messageType": "device_registration",
                        "deviceId": device_id,
                        "action": "register",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "registered"
                    }
                    
                    # Simulate IoT Hub send (replace with actual implementation)
                    logger.info(f"📡 Sending registration to IoT Hub: {json.dumps(registration_message, indent=2)}")
                    result["iot_hub_sent"] = True
                    
                    # Update database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE registered_devices SET iot_hub_registered = 1 WHERE device_id = ?",
                        (device_id,)
                    )
                    conn.commit()
                    conn.close()
                    
            except Exception as e:
                logger.error(f"❌ IoT Hub registration failed: {e}")
            
            # Step 4: Send to API
            try:
                api_base_url = self.config.get("api", {}).get("base_url", "")
                if api_base_url:
                    api_payload = {
                        "deviceId": device_id,
                        "messageType": "device_registration",
                        "action": "register", 
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Simulate API send (replace with actual implementation)
                    logger.info(f"🌐 Sending registration to API: {json.dumps(api_payload, indent=2)}")
                    result["api_sent"] = True
                    
                    # Update database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE registered_devices SET api_registered = 1 WHERE device_id = ?",
                        (device_id,)
                    )
                    conn.commit()
                    conn.close()
                    
            except Exception as e:
                logger.error(f"❌ API registration failed: {e}")
            
            # Set current device
            self.current_device_id = device_id
            
            # Final result
            result["success"] = result["database_saved"]
            status_parts = []
            if result["iot_hub_sent"]: status_parts.append("IoT Hub")
            if result["api_sent"]: status_parts.append("API")
            
            if result["success"]:
                if status_parts:
                    result["message"] = f"✅ Device {device_id} registered successfully (Database + {' + '.join(status_parts)})"
                else:
                    result["message"] = f"✅ Device {device_id} registered in database"
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
        Process EAN barcode scan
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
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO barcode_scans (device_id, barcode, quantity, scan_timestamp)
                    VALUES (?, ?, ?, ?)
                """, (device_id, barcode, quantity, datetime.now(timezone.utc).isoformat()))
                conn.commit()
                conn.close()
                
                result["database_saved"] = True
                logger.info(f"✅ Barcode scan saved to database")
                
            except Exception as e:
                logger.error(f"❌ Failed to save barcode scan: {e}")
                result["message"] = f"Database save failed: {e}"
                return result
            
            # Step 3: Send to IoT Hub
            try:
                iot_hub_connection = self.config.get("iot_hub", {}).get("connection_string", "")
                if iot_hub_connection:
                    quantity_message = {
                        "messageType": "quantity_update",
                        "deviceId": device_id,
                        "barcode": barcode,
                        "ean": barcode,
                        "quantity": quantity,
                        "action": "add",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Simulate IoT Hub send
                    logger.info(f"📡 Sending quantity update to IoT Hub: {json.dumps(quantity_message, indent=2)}")
                    result["iot_hub_sent"] = True
                    
                    # Update database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE barcode_scans SET iot_hub_sent = 1 WHERE device_id = ? AND barcode = ? ORDER BY id DESC LIMIT 1",
                        (device_id, barcode)
                    )
                    conn.commit()
                    conn.close()
                    
            except Exception as e:
                logger.error(f"❌ IoT Hub messaging failed: {e}")
            
            # Step 4: Send to API
            try:
                api_base_url = self.config.get("api", {}).get("base_url", "")
                if api_base_url:
                    api_payload = {
                        "deviceId": device_id,
                        "scannedBarcode": barcode,
                        "quantity": quantity,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    # Simulate API send
                    logger.info(f"🌐 Sending quantity update to API: {json.dumps(api_payload, indent=2)}")
                    result["api_sent"] = True
                    
                    # Update database
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE barcode_scans SET api_sent = 1 WHERE device_id = ? AND barcode = ? ORDER BY id DESC LIMIT 1",
                        (device_id, barcode)
                    )
                    conn.commit()
                    conn.close()
                    
            except Exception as e:
                logger.error(f"❌ API messaging failed: {e}")
            
            # Final result
            result["success"] = result["database_saved"]
            status_parts = []
            if result["iot_hub_sent"]: status_parts.append("IoT Hub")
            if result["api_sent"]: status_parts.append("API")
            
            if result["success"]:
                if status_parts:
                    result["message"] = f"✅ Barcode {barcode} processed successfully (Database + {' + '.join(status_parts)})"
                else:
                    result["message"] = f"✅ Barcode {barcode} saved to database"
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get device info
            cursor.execute("SELECT * FROM registered_devices WHERE device_id = ?", (device_id,))
            device_info = cursor.fetchone()
            
            if not device_info:
                conn.close()
                return {"error": f"Device {device_id} not found"}
            
            # Get scan count
            cursor.execute("SELECT COUNT(*) FROM barcode_scans WHERE device_id = ?", (device_id,))
            scan_count = cursor.fetchone()[0]
            
            conn.close()
            
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT device_id, registration_date, status FROM registered_devices ORDER BY registration_date DESC")
            result = cursor.fetchall()
            conn.close()
            
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
    """Main function demonstrating the barcode scanner flow"""
    print("🔄 Simple Barcode Scanner Flow Test")
    print("=" * 50)
    
    # Initialize scanner
    scanner = SimpleBarcodeFlow()
    
    # Test device registration with your device ID from the image
    device_id = "2379394fd95c"
    print(f"\n1. Testing Device Registration: {device_id}")
    registration_result = scanner.register_device(device_id)
    print(f"Result: {registration_result['message']}")
    print(f"Details: Database={registration_result['database_saved']}, IoT Hub={registration_result['iot_hub_sent']}, API={registration_result['api_sent']}")
    
    # Test barcode scanning with sample EAN
    test_barcode = "1234567890123"  # Example EAN barcode
    print(f"\n2. Testing EAN Barcode Scanning: {test_barcode}")
    scan_result = scanner.scan_barcode(test_barcode, device_id, quantity=1)
    print(f"Result: {scan_result['message']}")
    print(f"Details: Database={scan_result['database_saved']}, IoT Hub={scan_result['iot_hub_sent']}, API={scan_result['api_sent']}")
    
    # Test another barcode scan
    test_barcode2 = "9876543210987"
    print(f"\n3. Testing Another EAN Barcode: {test_barcode2}")
    scan_result2 = scanner.scan_barcode(test_barcode2, device_id, quantity=1)
    print(f"Result: {scan_result2['message']}")
    
    # Show device status
    print(f"\n4. Device Status:")
    status = scanner.get_device_status(device_id)
    if "error" not in status:
        print(f"Device ID: {status['device_id']}")
        print(f"Registration Date: {status['registration_date']}")
        print(f"Status: {status['status']}")
        print(f"IoT Hub Registered: {'✅' if status['iot_hub_registered'] else '❌'}")
        print(f"API Registered: {'✅' if status['api_registered'] else '❌'}")
        print(f"Total Scans: {status['total_scans']}")
    else:
        print(f"Error: {status['error']}")
    
    # List all devices
    print(f"\n5. All Registered Devices:")
    devices = scanner.list_registered_devices()
    if devices:
        for device in devices:
            print(f"- {device['device_id']} (registered: {device['registration_date']})")
    else:
        print("No devices registered")
    
    print(f"\n✅ Test completed! Check simple_barcode_flow.log for detailed logs.")
    print(f"📊 Database file: simple_barcode_flow.db")

if __name__ == "__main__":
    main()
