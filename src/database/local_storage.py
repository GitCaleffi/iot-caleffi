import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class LocalStorage:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'barcode_scans.db')
        self._init_db()
    
    def _get_connection(self):
        """Get a new database connection for thread safety"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        return conn
    
    def _init_db(self):
        """Initialize SQLite database and create tables if they don't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create scans table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                device_id TEXT,
                barcode TEXT,
                timestamp DATETIME,
                sent_to_hub BOOLEAN DEFAULT 0,
                quantity INTEGER DEFAULT 1
            )
        ''')
        # Create device_info table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_info (
                device_id TEXT,
                timestamp DATETIME
            )
        ''')
        # Create available_devices table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS available_devices (
                device_id TEXT PRIMARY KEY,
                timestamp DATETIME
            )
        ''')
        # Create test_barcode_scans table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_barcode_scans (
                barcode TEXT,
                timestamp DATETIME
            )
        ''')
        conn.commit()
        conn.close()

    def test_connection(self):
        """Test database connection"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            conn.close()
            return True
        except sqlite3.Error as e:
            raise Exception(f"Database connection error: {e}")

    def format_timestamp(self, timestamp):
        """Format timestamp to match required format: 2025-05-09T10:34:17.353Z
        This handles various input timestamp formats and standardizes them
        """
        import re
        # If timestamp is already in the correct format, return it
        if isinstance(timestamp, str) and re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$', timestamp):
            return timestamp
            
        try:
            # If it's a string, try to parse it
            if isinstance(timestamp, str):
                # Try different formats
                try:
                    # Try ISO format with timezone
                    dt_obj = datetime.fromisoformat(timestamp)
                except ValueError:
                    try:
                        # Try standard datetime format
                        dt_obj = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        # If all else fails, return as is
                        return timestamp
            else:
                # If it's already a datetime object
                dt_obj = timestamp
                
            # Ensure it's timezone aware
            if dt_obj.tzinfo is None:
                dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                
            # Format to the required format
            return dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + 'Z'
        except Exception:
            # If any error occurs, return the original timestamp
            return str(timestamp)

    def save_scan(self, device_id, barcode, quantity=1):
        """Save a barcode scan to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        cursor.execute(
            'INSERT INTO scans (device_id, barcode, timestamp, quantity) VALUES (?, ?, ?, ?)',
            (device_id, barcode, formatted_timestamp, quantity)
        )
        conn.commit()
        conn.close()
        return formatted_timestamp

    def get_recent_scans(self, limit=10):
        """Get recent barcode scans from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT device_id, barcode, timestamp, quantity FROM scans ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'device_id': row[0], 'barcode': row[1], 'timestamp': self.format_timestamp(row[2]), 'quantity': row[3] if len(row) > 3 else 1}
            for row in rows
        ]

    def mark_sent_to_hub(self, device_id, barcode, timestamp):
        """Mark a scan as sent to IoT Hub"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE scans SET sent_to_hub = 1 WHERE device_id = ? AND barcode = ? AND timestamp = ?',
            (device_id, barcode, timestamp)
        )
        conn.commit()
        conn.close()

    def get_device_id(self):
        """Retrieve the stored device ID, or None if not set"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT device_id FROM device_info ORDER BY timestamp DESC LIMIT 1'
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def save_device_id(self, device_id):
        """Save the device ID to the database if it doesn't already exist"""
        # First check if this device ID already exists
        existing_device_id = self.get_device_id()
        if existing_device_id == device_id:
            logger.info(f"Device ID {device_id} already registered, skipping save")
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        cursor.execute(
            'INSERT INTO device_info (device_id, timestamp) VALUES (?, ?)',
            (device_id, formatted_timestamp)
        )
        conn.commit()
        conn.close()
        logger.info(f"Device ID {device_id} registered successfully")
        return True

    def get_registered_devices(self):
        """Get all registered devices from the device_info table
        
        Returns:
            list: List of dictionaries containing device information
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT DISTINCT device_id, timestamp FROM device_info ORDER BY timestamp DESC'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'device_id': row[0], 'registered_at': self.format_timestamp(row[1])}
            for row in rows
        ]

    def get_unsent_scans(self):
        """Get scans not yet sent to IoT Hub"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT device_id, barcode, timestamp, quantity FROM scans WHERE sent_to_hub = 0'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'device_id': row[0], 'barcode': row[1], 'timestamp': self.format_timestamp(row[2]), 'quantity': row[3] if len(row) > 3 else 1}
            for row in rows
        ]

    def save_available_devices(self, device_ids):
        """Save available device IDs to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        
        # Clear existing devices
        cursor.execute('DELETE FROM available_devices')
        
        # Insert new devices
        for device_id in device_ids:
            cursor.execute(
                'INSERT INTO available_devices (device_id, timestamp) VALUES (?, ?)',
                (device_id, formatted_timestamp)
            )
        
        conn.commit()
        conn.close()

    def get_available_devices(self):
        """Get available device IDs from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT device_id, timestamp FROM available_devices ORDER BY device_id'
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'device_id': row[0], 'timestamp': self.format_timestamp(row[1])}
            for row in rows
        ]

    def save_test_barcode_scan(self, barcode):
        """Save a test barcode scan to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        cursor.execute(
            'INSERT INTO test_barcode_scans (barcode, timestamp) VALUES (?, ?)',
            (barcode, formatted_timestamp)
        )
        conn.commit()
        conn.close()

    def get_test_barcode_scan(self):
        """Get the most recent test barcode scan"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT barcode, timestamp FROM test_barcode_scans ORDER BY timestamp DESC LIMIT 1'
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'barcode': row[0], 'timestamp': self.format_timestamp(row[1])}
        return None

    def is_device_registered(self):
        """Check if device is properly registered"""
        # Check if we have available devices
        available_devices = self.get_available_devices()
        has_available_devices = len(available_devices) > 0
        
        # Check if test barcode has been scanned
        test_scan = self.get_test_barcode_scan()
        test_barcode_scanned = test_scan is not None
        
        return {
            'has_available_devices': has_available_devices,
            'available_device_count': len(available_devices),
            'test_barcode_scanned': test_barcode_scanned,
            'test_barcode_value': test_scan['barcode'] if test_scan else None,
            'scanned_at': test_scan['timestamp'] if test_scan else None,
            'device_ready': has_available_devices and test_barcode_scanned
        }

    def save_unsent_message(self, device_id, barcode, quantity=1):
        """Save an unsent message (same as save_scan but explicitly for unsent messages)"""
        return self.save_scan(device_id, barcode, quantity)

    def close(self):
        """Close database connection - no longer needed with per-operation connections"""
        pass