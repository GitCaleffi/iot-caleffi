import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import sqlite3

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class LocalStorage:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'barcode_scans.db')
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database and create tables if they don't exist"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create scans table if it doesn't exist
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                device_id TEXT,
                barcode TEXT,
                timestamp DATETIME,
                sent_to_hub BOOLEAN DEFAULT 0
            )
        ''')
        # Create device_info table if it doesn't exist
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_info (
                device_id TEXT,
                timestamp DATETIME
            )
        ''')
        self.conn.commit()

    def test_connection(self):
        """Test database connection"""
        try:
            self.cursor.execute('SELECT 1')
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

    def save_scan(self, device_id, barcode):
        """Save a barcode scan to the database"""
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        self.cursor.execute(
            'INSERT INTO scans (device_id, barcode, timestamp) VALUES (?, ?, ?)',
            (device_id, barcode, formatted_timestamp)
        )
        self.conn.commit()
        return formatted_timestamp

    def get_recent_scans(self, limit=10):
        """Get recent barcode scans from the database"""
        self.cursor.execute(
            'SELECT device_id, barcode, timestamp FROM scans ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )
        rows = self.cursor.fetchall()
        return [
            {'device_id': row[0], 'barcode': row[1], 'timestamp': self.format_timestamp(row[2])}
            for row in rows
        ]

    def mark_sent_to_hub(self, device_id, barcode, timestamp):
        """Mark a scan as sent to IoT Hub"""
        self.cursor.execute(
            'UPDATE scans SET sent_to_hub = 1 WHERE device_id = ? AND barcode = ? AND timestamp = ?',
            (device_id, barcode, timestamp)
        )
        self.conn.commit()

    def get_device_id(self):
        """Retrieve the stored device ID, or None if not set"""
        self.cursor.execute(
            'SELECT device_id FROM device_info ORDER BY timestamp DESC LIMIT 1'
        )
        row = self.cursor.fetchone()
        return row[0] if row else None

    def save_device_id(self, device_id):
        """Save the device ID to the database"""
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        self.cursor.execute(
            'INSERT INTO device_info (device_id, timestamp) VALUES (?, ?)',
            (device_id, formatted_timestamp)
        )
        self.conn.commit()

    def get_unsent_scans(self):
        """Get scans not yet sent to IoT Hub"""
        self.cursor.execute(
            'SELECT device_id, barcode, timestamp FROM scans WHERE sent_to_hub = 0'
        )
        rows = self.cursor.fetchall()
        return [
            {'device_id': row[0], 'barcode': row[1], 'timestamp': self.format_timestamp(row[2])}
            for row in rows
        ]

    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()