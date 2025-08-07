#!/usr/bin/env python3
"""
Barcode Device Mapper - Maps barcodes to device IDs for commercial scale deployment
Supports plug-and-play functionality without manual device ID input
"""

import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import threading
from typing import Optional, Dict, Tuple
import sqlite3
import os

logger = logging.getLogger(__name__)

class BarcodeDeviceMapper:
    """
    Maps barcodes to unique device IDs for Azure IoT Hub registration.
    Supports commercial scale deployment (1000+ devices) with plug-and-play functionality.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the barcode device mapper"""
        self.project_root = Path(__file__).parent.parent.parent
        self.db_path = db_path or os.path.join(self.project_root, 'barcode_device_mapping.db')
        self.lock = threading.RLock()
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for barcode-device mappings"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        
        # Create mapping table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS barcode_device_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT UNIQUE NOT NULL,
                device_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT NOT NULL,
                registration_status TEXT DEFAULT 'pending',
                connection_string TEXT,
                azure_registered INTEGER DEFAULT 0
            )
        ''')
        
        # Create index for fast lookups
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_barcode ON barcode_device_mapping(barcode)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device_id ON barcode_device_mapping(device_id)')
        
        conn.commit()
        conn.close()
        logger.info(f"Barcode device mapping database initialized at: {self.db_path}")
    
    def generate_device_id_from_barcode(self, barcode: str) -> str:
        """
        Generate a unique, deterministic device ID from barcode.
        Uses SHA-256 hash to ensure uniqueness and consistency.
        """
        # Validate barcode format
        if not barcode or not barcode.isdigit():
            raise ValueError(f"Invalid barcode format: {barcode}")
        
        # Create deterministic device ID using hash
        # Use first 12 characters of SHA-256 hash for device ID
        hash_input = f"barcode_{barcode}_device"
        device_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
        device_id = f"bc_{device_hash}"
        
        logger.info(f"Generated device ID '{device_id}' for barcode '{barcode}'")
        return device_id
    
    def get_device_id_for_barcode(self, barcode: str) -> Optional[str]:
        """
        Get existing device ID for barcode, or create new mapping if not exists.
        This is the main method for barcode-to-device resolution.
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                # Check if mapping already exists
                cursor.execute(
                    'SELECT device_id, connection_string FROM barcode_device_mapping WHERE barcode = ?',
                    (barcode,)
                )
                result = cursor.fetchone()
                
                if result:
                    device_id, connection_string = result
                    # Update last_used timestamp
                    cursor.execute(
                        'UPDATE barcode_device_mapping SET last_used = ? WHERE barcode = ?',
                        (datetime.now(timezone.utc).isoformat(), barcode)
                    )
                    conn.commit()
                    logger.info(f"Found existing device ID '{device_id}' for barcode '{barcode}'")
                    return device_id
                
                # Create new mapping
                device_id = self.generate_device_id_from_barcode(barcode)
                timestamp = datetime.now(timezone.utc).isoformat()
                
                cursor.execute('''
                    INSERT INTO barcode_device_mapping 
                    (barcode, device_id, created_at, last_used, registration_status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (barcode, device_id, timestamp, timestamp, 'pending'))
                
                conn.commit()
                logger.info(f"Created new device mapping: barcode '{barcode}' -> device ID '{device_id}'")
                return device_id
                
            except Exception as e:
                logger.error(f"Error getting device ID for barcode '{barcode}': {e}")
                return None
            finally:
                conn.close()
    
    def is_new_device(self, barcode: str) -> bool:
        """Check if this barcode is completely new (not in database at all)"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    'SELECT COUNT(*) FROM barcode_device_mapping WHERE barcode = ?',
                    (barcode,)
                )
                result = cursor.fetchone()
                
                # If count is 0, barcode doesn't exist - it's a new device
                # If count > 0, barcode exists - it's an existing device (inventory update)
                count = result[0] if result else 0
                is_new = count == 0
                
                if is_new:
                    logger.info(f"[INVENTORY] NEW DEVICE: Barcode '{barcode}' not found in database")
                else:
                    logger.info(f"[INVENTORY] EXISTING DEVICE: Barcode '{barcode}' found in database - inventory update")
                
                return is_new
                
            except Exception as e:
                logger.error(f"Error checking if device is new for barcode '{barcode}': {e}")
                return True  # Assume new on error for safety
            finally:
                conn.close()
    
    def mark_device_registered(self, barcode: str) -> bool:
        """Mark a device as registered with Azure IoT Hub"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    UPDATE barcode_device_mapping 
                    SET azure_registered = 1, registration_status = 'registered'
                    WHERE barcode = ?
                ''', (barcode,))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Marked device as registered for barcode '{barcode}'")
                    return True
                else:
                    logger.warning(f"No device mapping found for barcode '{barcode}' to mark as registered")
                    return False
                    
            except Exception as e:
                logger.error(f"Error marking device as registered for barcode '{barcode}': {e}")
                return False
            finally:
                conn.close()

    def update_device_registration(self, barcode: str, connection_string: str, azure_registered: bool = True):
        """Update device registration status and connection string"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    UPDATE barcode_device_mapping 
                    SET connection_string = ?, azure_registered = ?, registration_status = ?
                    WHERE barcode = ?
                ''', (connection_string, 1 if azure_registered else 0, 'registered' if azure_registered else 'pending', barcode))
                
                conn.commit()
                
                if cursor.rowcount > 0:
                    logger.info(f"Updated device registration for barcode '{barcode}': Azure registered = {azure_registered}")
                    return True
                else:
                    logger.warning(f"No device mapping found for barcode '{barcode}' to update")
                    return False
                    
            except Exception as e:
                logger.error(f"Error updating device registration for barcode '{barcode}': {e}")
                return False
            finally:
                conn.close()
    
    def get_connection_string_for_barcode(self, barcode: str) -> Optional[str]:
        """Get Azure IoT Hub connection string for barcode"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    'SELECT connection_string FROM barcode_device_mapping WHERE barcode = ? AND azure_registered = 1',
                    (barcode,)
                )
                result = cursor.fetchone()
                return result[0] if result else None
                
            except Exception as e:
                logger.error(f"Error getting connection string for barcode '{barcode}': {e}")
                return None
            finally:
                conn.close()
    
    def get_mapping_stats(self) -> Dict:
        """Get statistics about barcode-device mappings"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                # Total mappings
                cursor.execute('SELECT COUNT(*) FROM barcode_device_mapping')
                total_mappings = cursor.fetchone()[0]
                
                # Registered devices
                cursor.execute('SELECT COUNT(*) FROM barcode_device_mapping WHERE azure_registered = 1')
                registered_devices = cursor.fetchone()[0]
                
                # Pending registrations
                cursor.execute('SELECT COUNT(*) FROM barcode_device_mapping WHERE registration_status = "pending"')
                pending_registrations = cursor.fetchone()[0]
                
                # Recent activity (last 24 hours)
                cursor.execute('''
                    SELECT COUNT(*) FROM barcode_device_mapping 
                    WHERE datetime(last_used) > datetime('now', '-1 day')
                ''')
                recent_activity = cursor.fetchone()[0]
                
                return {
                    'total_mappings': total_mappings,
                    'registered_devices': registered_devices,
                    'pending_registrations': pending_registrations,
                    'recent_activity': recent_activity
                }
                
            except Exception as e:
                logger.error(f"Error getting mapping stats: {e}")
                return {}
            finally:
                conn.close()
    
    def list_all_mappings(self, limit: int = 100) -> list:
        """List all barcode-device mappings for debugging/admin purposes"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    SELECT barcode, device_id, created_at, last_used, registration_status, azure_registered
                    FROM barcode_device_mapping 
                    ORDER BY last_used DESC 
                    LIMIT ?
                ''', (limit,))
                
                results = cursor.fetchall()
                return [
                    {
                        'barcode': row[0],
                        'device_id': row[1],
                        'created_at': row[2],
                        'last_used': row[3],
                        'registration_status': row[4],
                        'azure_registered': bool(row[5])
                    }
                    for row in results
                ]
                
            except Exception as e:
                logger.error(f"Error listing mappings: {e}")
                return []
            finally:
                conn.close()
    
    def cleanup_old_mappings(self, days_old: int = 30):
        """Clean up old unused mappings (for maintenance)"""
        with self.lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    DELETE FROM barcode_device_mapping 
                    WHERE datetime(last_used) < datetime('now', '-{} days')
                    AND azure_registered = 0
                '''.format(days_old))
                
                deleted_count = cursor.rowcount
                conn.commit()
                logger.info(f"Cleaned up {deleted_count} old unused mappings")
                return deleted_count
                
            except Exception as e:
                logger.error(f"Error cleaning up old mappings: {e}")
                return 0
            finally:
                conn.close()


# Global instance for easy access
barcode_mapper = BarcodeDeviceMapper()

def get_device_id_for_barcode(barcode: str) -> Optional[str]:
    """Convenience function to get device ID for barcode"""
    return barcode_mapper.get_device_id_for_barcode(barcode)

def get_connection_string_for_barcode(barcode: str) -> Optional[str]:
    """Convenience function to get connection string for barcode"""
    return barcode_mapper.get_connection_string_for_barcode(barcode)
