import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import threading

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

class LocalStorage:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'barcode_scans.db')
        # Initialize the database schema without storing connection
        self._init_db()
    
    def _get_connection(self):
        """Get a thread-local connection to the database"""
        return sqlite3.connect(self.db_path)
    
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
                retry_count INTEGER DEFAULT 0,
                last_retry DATETIME,
                error_message TEXT,
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
        
        # Create inventory tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                barcode TEXT PRIMARY KEY,
                product_name TEXT,
                quantity INTEGER DEFAULT 0,
                last_updated DATETIME
            )
        ''')
        
        # Add the retry_count, last_retry, error_message, and quantity columns if they don't exist
        try:
            # Check if the columns exist in the table schema
            columns = [column[1] for column in cursor.execute('PRAGMA table_info(scans)').fetchall()]
            
            if 'retry_count' not in columns:
                cursor.execute('ALTER TABLE scans ADD COLUMN retry_count INTEGER DEFAULT 0')
                
            if 'last_retry' not in columns:
                cursor.execute('ALTER TABLE scans ADD COLUMN last_retry DATETIME')
                
            if 'error_message' not in columns:
                cursor.execute('ALTER TABLE scans ADD COLUMN error_message TEXT')
                
            if 'quantity' not in columns:
                cursor.execute('ALTER TABLE scans ADD COLUMN quantity INTEGER DEFAULT 1')
        except Exception as e:
            print(f"Warning: Could not add new columns to scans table: {str(e)}")
            
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
        """Save a barcode scan to the database
        
        Args:
            device_id (str): The device ID
            barcode (str): The barcode
            quantity (int): The quantity scanned (default: 1)
        
        Returns:
            str: The formatted timestamp of the scan
        """
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO scans (device_id, barcode, timestamp, sent_to_hub, retry_count, quantity) VALUES (?, ?, ?, ?, ?, ?)',
            (device_id, barcode, formatted_timestamp, 0, 0, quantity)
        )
        
        # Also update the inventory table
        cursor.execute(
            'INSERT INTO inventory (barcode, quantity, last_updated) VALUES (?, ?, ?) '
            'ON CONFLICT(barcode) DO UPDATE SET quantity = quantity + ?, last_updated = ?',
            (barcode, quantity, formatted_timestamp, quantity, formatted_timestamp)
        )
        
        conn.commit()
        conn.close()
        return formatted_timestamp

    def get_recent_scans(self, limit=10):
        """Get recent barcode scans from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT device_id, barcode, timestamp FROM scans ORDER BY timestamp DESC LIMIT ?',
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {'device_id': row[0], 'barcode': row[1], 'timestamp': self.format_timestamp(row[2])}
            for row in rows
        ]

    def mark_sent_to_hub(self, device_id, barcode, timestamp):
        """Mark a scan as successfully sent to IoT Hub"""
        formatted_timestamp = self.format_timestamp(timestamp)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE scans SET sent_to_hub = 1, retry_count = retry_count + 1, last_retry = ? WHERE device_id = ? AND barcode = ? AND timestamp = ?',
            (datetime.now(timezone.utc).isoformat(), device_id, barcode, formatted_timestamp)
        )
        conn.commit()
        conn.close()

    def mark_retry_attempt(self, device_id, barcode, timestamp, error_message=None):
        """Mark a retry attempt for a scan with optional error message"""
        formatted_timestamp = self.format_timestamp(timestamp)
        now = datetime.now(timezone.utc).isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        if error_message:
            cursor.execute(
                'UPDATE scans SET retry_count = retry_count + 1, last_retry = ?, error_message = ? WHERE device_id = ? AND barcode = ? AND timestamp = ?',
                (now, error_message, device_id, barcode, formatted_timestamp)
            )
        else:
            cursor.execute(
                'UPDATE scans SET retry_count = retry_count + 1, last_retry = ? WHERE device_id = ? AND barcode = ? AND timestamp = ?',
                (now, device_id, barcode, formatted_timestamp)
            )
        conn.commit()
        conn.close()
    
    def get_retry_stats(self):
        """Get statistics about message retries"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get total unsent messages
        cursor.execute('SELECT COUNT(*) FROM scans WHERE sent_to_hub = 0')
        unsent_count = cursor.fetchone()[0]
        
        # Get retry information 
        cursor.execute('SELECT MAX(retry_count) FROM scans WHERE sent_to_hub = 0')
        max_retries = cursor.fetchone()[0] or 0
        
        # Get messages with errors
        cursor.execute('SELECT COUNT(*) FROM scans WHERE sent_to_hub = 0 AND error_message IS NOT NULL')
        error_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "unsent_count": unsent_count,
            "max_retries": max_retries,
            "error_count": error_count
        }
    
    def get_device_id(self):
        """Get the most recent device ID stored in the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT device_id FROM device_info ORDER BY timestamp DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None

    def save_device_id(self, device_id):
        """Save the device ID to the database"""
        timestamp = datetime.now(timezone.utc)
        formatted_timestamp = self.format_timestamp(timestamp)
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO device_info (device_id, timestamp) VALUES (?, ?)',
            (device_id, formatted_timestamp)
        )
        conn.commit()
        conn.close()

    def get_unsent_scans(self, limit=100, max_retries=None):
        """Get all scans that haven't been sent to IoT Hub
        
        Args:
            limit (int): Maximum number of unsent scans to return
            max_retries (int): If set, only include scans with retry_count less than this value
            
        Returns:
            list: List of unsent scan records
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT device_id, barcode, timestamp, retry_count, last_retry, error_message FROM scans WHERE sent_to_hub = 0'
        params = []
        
        if max_retries is not None:
            query += ' AND retry_count < ?'
            params.append(max_retries)
        
        query += ' ORDER BY timestamp ASC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        scans = []
        for row in rows:
            scans.append({
                "device_id": row[0],
                "barcode": row[1],
                "timestamp": row[2],
                "retry_count": row[3] if row[3] is not None else 0,
                "last_retry": row[4],
                "error_message": row[5]
            })
            
        return scans

    def close(self):
        """Close database connection"""
        # Nothing to do as connections are created and closed per operation