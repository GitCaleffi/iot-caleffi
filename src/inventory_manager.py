#!/usr/bin/env python3
"""
Enhanced Inventory Management System
Handles inventory tracking, negative stock alerts, and device registration
"""

import sqlite3
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import requests

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from database.local_storage import LocalStorage
from api.api_client import ApiClient

logger = logging.getLogger(__name__)

class InventoryManager:
    def __init__(self):
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.db_path = project_root / 'barcode_scans.db'
        self._init_enhanced_tables()
        
    def _init_enhanced_tables(self):
        """Initialize enhanced inventory and device tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhanced inventory table with product details
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_enhanced (
                ean TEXT PRIMARY KEY,
                product_name TEXT,
                current_quantity INTEGER DEFAULT 0,
                min_threshold INTEGER DEFAULT 0,
                max_threshold INTEGER DEFAULT 100,
                last_updated DATETIME,
                status TEXT DEFAULT 'active',
                alerts_enabled BOOLEAN DEFAULT 1
            )
        ''')
        
        # Device registration table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_registry (
                device_id TEXT PRIMARY KEY,
                device_name TEXT,
                connection_string TEXT,
                registration_date DATETIME,
                last_seen DATETIME,
                status TEXT DEFAULT 'active',
                test_barcode TEXT
            )
        ''')
        
        # Inventory transactions table for audit trail
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ean TEXT,
                device_id TEXT,
                transaction_type TEXT,
                quantity_change INTEGER,
                previous_quantity INTEGER,
                new_quantity INTEGER,
                timestamp DATETIME,
                notes TEXT
            )
        ''')
        
        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ean TEXT,
                alert_type TEXT,
                message TEXT,
                severity TEXT,
                created_at DATETIME,
                resolved_at DATETIME,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def check_inventory_status(self, ean):
        """Check current inventory status for a given EAN"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current inventory
        cursor.execute(
            'SELECT current_quantity, min_threshold, product_name, status FROM inventory_enhanced WHERE ean = ?',
            (ean,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Check if it exists in the basic inventory table
            cursor.execute('SELECT quantity FROM inventory WHERE barcode = ?', (ean,))
            basic_result = cursor.fetchone()
            if basic_result:
                # Migrate to enhanced table
                self._migrate_basic_inventory(ean, basic_result[0])
                conn.close()
                return self.check_inventory_status(ean)
            else:
                conn.close()
                return {
                    'ean': ean,
                    'exists': False,
                    'message': f'Product with EAN {ean} not found in inventory'
                }
        
        current_qty, min_threshold, product_name, status = result
        conn.close()
        
        # Determine status
        if current_qty < 0:
            alert_level = 'CRITICAL'
            message = f'CRITICAL: Inventory for {ean} is negative ({current_qty})'
        elif current_qty == 0:
            alert_level = 'HIGH'
            message = f'HIGH ALERT: Inventory for {ean} is zero'
        elif current_qty <= min_threshold:
            alert_level = 'MEDIUM'
            message = f'LOW STOCK: Inventory for {ean} is below threshold ({current_qty} <= {min_threshold})'
        else:
            alert_level = 'NORMAL'
            message = f'Inventory for {ean} is normal ({current_qty})'
            
        return {
            'ean': ean,
            'exists': True,
            'product_name': product_name,
            'current_quantity': current_qty,
            'min_threshold': min_threshold,
            'status': status,
            'alert_level': alert_level,
            'message': message
        }
        
    def _migrate_basic_inventory(self, ean, quantity):
        """Migrate from basic inventory table to enhanced table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO inventory_enhanced (ean, current_quantity, last_updated)
            VALUES (?, ?, ?)
        ''', (ean, quantity, datetime.now(timezone.utc).isoformat()))
        
        conn.commit()
        conn.close()
        
    def update_inventory(self, ean, quantity_change, device_id, transaction_type='scan', notes=None):
        """Update inventory and create transaction record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current quantity
        cursor.execute('SELECT current_quantity FROM inventory_enhanced WHERE ean = ?', (ean,))
        result = cursor.fetchone()
        
        if result:
            previous_qty = result[0]
        else:
            # Create new inventory record
            previous_qty = 0
            cursor.execute('''
                INSERT INTO inventory_enhanced (ean, current_quantity, last_updated)
                VALUES (?, ?, ?)
            ''', (ean, 0, datetime.now(timezone.utc).isoformat()))
            
        new_qty = previous_qty + quantity_change
        
        # Update inventory
        cursor.execute('''
            UPDATE inventory_enhanced 
            SET current_quantity = ?, last_updated = ?
            WHERE ean = ?
        ''', (new_qty, datetime.now(timezone.utc).isoformat(), ean))
        
        # Create transaction record
        cursor.execute('''
            INSERT INTO inventory_transactions 
            (ean, device_id, transaction_type, quantity_change, previous_quantity, new_quantity, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (ean, device_id, transaction_type, quantity_change, previous_qty, new_qty, 
              datetime.now(timezone.utc).isoformat(), notes))
        
        # Check for alerts
        if new_qty < 0:
            self._create_alert(ean, 'NEGATIVE_INVENTORY', 
                             f'Inventory dropped below zero: {new_qty}', 'CRITICAL')
        elif new_qty == 0:
            self._create_alert(ean, 'ZERO_INVENTORY', 
                             f'Inventory reached zero', 'HIGH')
        
        conn.commit()
        conn.close()
        
        return {
            'ean': ean,
            'previous_quantity': previous_qty,
            'quantity_change': quantity_change,
            'new_quantity': new_qty,
            'transaction_type': transaction_type
        }
        
    def _create_alert(self, ean, alert_type, message, severity):
        """Create an inventory alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if similar alert already exists and is active
        cursor.execute('''
            SELECT id FROM inventory_alerts 
            WHERE ean = ? AND alert_type = ? AND status = 'active'
        ''', (ean, alert_type))
        
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO inventory_alerts (ean, alert_type, message, severity, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (ean, alert_type, message, severity, datetime.now(timezone.utc).isoformat()))
            
        conn.commit()
        conn.close()
        
    def register_new_device(self, device_id, device_name=None):
        """Register a new device if it doesn't exist in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if device already exists
        cursor.execute('SELECT device_id FROM device_registry WHERE device_id = ?', (device_id,))
        if cursor.fetchone():
            conn.close()
            return {
                'success': False,
                'message': f'Device {device_id} already registered',
                'device_id': device_id
            }
        
        # Generate test barcode for the device
        test_barcode = f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
        
        # Register device
        cursor.execute('''
            INSERT INTO device_registry 
            (device_id, device_name, registration_date, last_seen, test_barcode)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_id, device_name or f"Device_{device_id}", 
              datetime.now(timezone.utc).isoformat(),
              datetime.now(timezone.utc).isoformat(),
              test_barcode))
        
        conn.commit()
        conn.close()
        
        # Send registration message to client API
        registration_result = self._send_device_registration_to_api(device_id, test_barcode)
        
        return {
            'success': True,
            'message': f'Device {device_id} registered successfully',
            'device_id': device_id,
            'test_barcode': test_barcode,
            'api_result': registration_result
        }
        
    def _send_device_registration_to_api(self, device_id, test_barcode):
        """Send device registration notification to client API"""
        try:
            # Use the existing API client to send registration
            endpoint = f"{self.api_client.api_base_url}/raspberry/deviceRegistered"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_client.auth_token
            }
            
            payload = {
                "deviceId": device_id,
                "testBarcode": test_barcode,
                "registrationTime": datetime.now(timezone.utc).isoformat(),
                "status": "registered"
            }
            
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            data = response.json()
            
            if data.get("responseCode") == 200:
                return {
                    'success': True,
                    'message': 'Device registration sent to client API successfully'
                }
            else:
                return {
                    'success': False,
                    'message': f'API returned error: {data.get("responseMessage", "Unknown error")}'
                }
                
        except Exception as e:
            logger.error(f"Failed to send device registration to API: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to notify client API: {str(e)}'
            }
            
    def get_device_test_barcode(self, device_id):
        """Get the test barcode for a device"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT test_barcode FROM device_registry WHERE device_id = ?', (device_id,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
        
    def process_barcode_scan(self, barcode, device_id, quantity=1):
        """Process a barcode scan with enhanced inventory management"""
        # First check if it's a test barcode
        if self.api_client.is_test_barcode(barcode):
            return {
                'type': 'test_barcode',
                'message': f'Test barcode {barcode} processed successfully',
                'barcode': barcode,
                'device_id': device_id
            }
            
        # Check if device exists, if not register it
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT device_id FROM device_registry WHERE device_id = ?', (device_id,))
        if not cursor.fetchone():
            conn.close()
            registration_result = self.register_new_device(device_id)
            if not registration_result['success']:
                return {
                    'type': 'error',
                    'message': f'Failed to register device: {registration_result["message"]}'
                }
        else:
            conn.close()
            
        # Update inventory
        inventory_result = self.update_inventory(barcode, quantity, device_id, 'scan')
        
        # Check inventory status
        status = self.check_inventory_status(barcode)
        
        return {
            'type': 'inventory_update',
            'inventory_result': inventory_result,
            'status': status,
            'barcode': barcode,
            'device_id': device_id
        }
        
    def get_active_alerts(self):
        """Get all active inventory alerts"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ean, alert_type, message, severity, created_at
            FROM inventory_alerts 
            WHERE status = 'active'
            ORDER BY severity DESC, created_at DESC
        ''')
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'ean': row[0],
                'alert_type': row[1],
                'message': row[2],
                'severity': row[3],
                'created_at': row[4]
            })
            
        conn.close()
        return alerts
        
    def resolve_alert(self, ean, alert_type):
        """Resolve an active alert"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE inventory_alerts 
            SET status = 'resolved', resolved_at = ?
            WHERE ean = ? AND alert_type = ? AND status = 'active'
        ''', (datetime.now(timezone.utc).isoformat(), ean, alert_type))
        
        conn.commit()
        conn.close()
        
    def get_inventory_report(self):
        """Generate comprehensive inventory report"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all inventory items with their status
        cursor.execute('''
            SELECT ean, product_name, current_quantity, min_threshold, last_updated
            FROM inventory_enhanced
            ORDER BY current_quantity ASC
        ''')
        
        items = []
        for row in cursor.fetchall():
            ean, product_name, current_qty, min_threshold, last_updated = row
            
            if current_qty < 0:
                status = 'CRITICAL'
            elif current_qty == 0:
                status = 'OUT_OF_STOCK'
            elif current_qty <= min_threshold:
                status = 'LOW_STOCK'
            else:
                status = 'NORMAL'
                
            items.append({
                'ean': ean,
                'product_name': product_name,
                'current_quantity': current_qty,
                'min_threshold': min_threshold,
                'status': status,
                'last_updated': last_updated
            })
            
        conn.close()
        return items

def main():
    """Test the inventory manager"""
    manager = InventoryManager()
    
    # Test the problematic EAN
    ean = "23541523652145"
    print(f"Checking inventory for EAN: {ean}")
    status = manager.check_inventory_status(ean)
    print(json.dumps(status, indent=2))
    
    # Get active alerts
    alerts = manager.get_active_alerts()
    print(f"\nActive alerts: {len(alerts)}")
    for alert in alerts:
        print(f"- {alert['severity']}: {alert['message']}")

if __name__ == "__main__":
    main()