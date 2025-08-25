#!/usr/bin/env python3
"""
Local Storage Updates - Add these methods to your LocalStorage class
"""

def update_device_status(self, device_id: str, status: str, ip_address: str = None):
    """Update device status and last seen timestamp"""
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        update_query = """
        UPDATE available_devices 
        SET status = ?, last_seen = ?
        """
        params = [status, datetime.now().isoformat()]
        
        if ip_address:
            update_query += ", ip_address = ?"
            params.append(ip_address)
            
        update_query += " WHERE device_id = ?"
        params.append(device_id)
        
        cursor.execute(update_query, params)
        conn.commit()
        conn.close()
        
        logger.info(f"Updated device status: {device_id} -> {status}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating device status: {e}")
        return False

def add_available_device(self, device_id: str, device_name: str, ip_address: str, 
                        mac_address: str = None, device_type: str = "raspberry_pi"):
    """Add a new available device"""
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS available_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT UNIQUE,
            device_name TEXT,
            ip_address TEXT,
            mac_address TEXT,
            device_type TEXT,
            status TEXT DEFAULT 'online',
            registered_at TEXT,
            last_seen TEXT
        )
        """)
        
        cursor.execute("""
        INSERT OR REPLACE INTO available_devices 
        (device_id, device_name, ip_address, mac_address, device_type, status, registered_at, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            device_id, device_name, ip_address, mac_address, device_type, 
            'online', datetime.now().isoformat(), datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error adding available device: {e}")
        return False

def update_device_status(self, device_id: str, status: str, ip_address: str = None):
    """Update device status and last seen timestamp"""
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        update_query = "UPDATE available_devices SET status = ?, last_seen = ?"
        params = [status, datetime.now().isoformat()]
        
        if ip_address:
            update_query += ", ip_address = ?"
            params.append(ip_address)
            
        update_query += " WHERE device_id = ?"
        params.append(device_id)
        
        cursor.execute(update_query, params)
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error updating device status: {e}")
        return False

def get_available_devices(self):
    """Get all available devices"""
    try:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM available_devices")
        rows = cursor.fetchall()
        
        devices = []
        for row in rows:
            devices.append({
                'id': row[0],
                'device_id': row[1],
                'device_name': row[2],
                'ip_address': row[3],
                'mac_address': row[4],
                'device_type': row[5],
                'status': row[6],
                'registered_at': row[7],
                'last_seen': row[8]
            })
        
        conn.close()
        return devices
        
    except Exception as e:
        logger.error(f"Error getting available devices: {e}")
        return []
