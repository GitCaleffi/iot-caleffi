#!/usr/bin/env python3
"""
Script to add the missing create_available_devices_table method to LocalStorage
This fixes the 500 error: 'LocalStorage' object has no attribute 'create_available_devices_table'
"""

import os
import sys

def add_missing_method():
    """Add the missing create_available_devices_table method to local_storage.py"""
    
    # Find the local_storage.py file in the current directory structure
    possible_paths = [
        "src/database/local_storage.py",
        "../iot-caleffi/src/database/local_storage.py",
        "/var/www/html/iot-caleffi/src/database/local_storage.py"
    ]
    
    target_file = None
    for path in possible_paths:
        if os.path.exists(path):
            target_file = path
            break
    
    if not target_file:
        print("❌ Could not find local_storage.py file")
        return False
    
    print(f"📁 Found local_storage.py at: {target_file}")
    
    # Read the current file
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Check if method already exists
    if 'def create_available_devices_table(self):' in content:
        print("✅ Method create_available_devices_table already exists")
        return True
    
    # Find the insertion point (after save_unsent_message method)
    insertion_point = content.find('logger.info(f"Unsent message saved for device {device_id}")')
    if insertion_point == -1:
        print("❌ Could not find insertion point in file")
        return False
    
    # Find the end of the save_unsent_message method
    insertion_point = content.find('\n\n    def ', insertion_point)
    if insertion_point == -1:
        print("❌ Could not find method boundary")
        return False
    
    # Method to insert
    method_code = '''
    def create_available_devices_table(self):
        """Create the available_devices table if it doesn't exist"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS available_devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT UNIQUE,
                device_name TEXT,
                ip_address TEXT,
                mac_address TEXT,
                device_type TEXT,
                status TEXT DEFAULT 'offline',
                registered_at TEXT,
                last_seen TEXT
            )
        """)
        
        conn.commit()
        conn.close()
'''
    
    # Insert the method
    new_content = content[:insertion_point] + method_code + content[insertion_point:]
    
    # Write back to file
    with open(target_file, 'w') as f:
        f.write(new_content)
    
    print("✅ Successfully added create_available_devices_table method")
    return True

if __name__ == "__main__":
    success = add_missing_method()
    sys.exit(0 if success else 1)
