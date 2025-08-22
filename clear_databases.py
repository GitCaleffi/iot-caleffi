#!/usr/bin/env python3
"""
Database Cleanup Script
Clears all databases to reset the system for fresh testing
"""

import os
import sqlite3
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_database_tables(db_path):
    """Clear all tables in a SQLite database"""
    if not os.path.exists(db_path):
        logger.info(f"Database {db_path} does not exist, skipping...")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            logger.info(f"No tables found in {db_path}")
            conn.close()
            return
        
        logger.info(f"Clearing {len(tables)} tables in {db_path}")
        
        # Clear each table
        for table in tables:
            table_name = table[0]
            try:
                cursor.execute(f"DELETE FROM {table_name}")
                logger.info(f"  ✅ Cleared table: {table_name}")
            except Exception as e:
                logger.error(f"  ❌ Error clearing table {table_name}: {e}")
        
        # Commit changes
        conn.commit()
        conn.close()
        logger.info(f"✅ Successfully cleared database: {db_path}")
        
    except Exception as e:
        logger.error(f"❌ Error clearing database {db_path}: {e}")

def main():
    """Main function to clear all databases"""
    logger.info("🧹 Starting database cleanup...")
    
    # List of database files to clear
    databases = [
        "/var/www/html/abhimanyu/barcode_scanner_clean/barcode_device_mapping.db",
        "/var/www/html/abhimanyu/barcode_scanner_clean/barcode_scanner.db", 
        "/var/www/html/abhimanyu/barcode_scanner_clean/barcode_scans.db",
        "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_device_mapping.db"
    ]
    
    # Clear each database
    for db_path in databases:
        clear_database_tables(db_path)
    
    # Also clear any config files that might store device state
    config_files = [
        "/var/www/html/abhimanyu/barcode_scanner_clean/config.json"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                # Read current config
                with open(config_file, 'r') as f:
                    import json
                    config = json.load(f)
                
                # Clear device-specific data while keeping IoT Hub config
                if 'device' in config:
                    config['device'] = {}
                    logger.info("  ✅ Cleared device configuration")
                
                if 'iot_hub' in config and 'devices' in config['iot_hub']:
                    config['iot_hub']['devices'] = {}
                    logger.info("  ✅ Cleared IoT Hub device registrations")
                
                # Write back cleaned config
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                logger.info(f"✅ Cleaned config file: {config_file}")
                
            except Exception as e:
                logger.error(f"❌ Error cleaning config file {config_file}: {e}")
    
    logger.info("🎉 Database cleanup completed!")
    logger.info("")
    logger.info("📋 System is now reset for fresh testing:")
    logger.info("  • All device registrations cleared")
    logger.info("  • All barcode scans cleared") 
    logger.info("  • All unsent messages cleared")
    logger.info("  • Device mappings cleared")
    logger.info("  • IoT Hub device registry cleared (local)")
    logger.info("")
    logger.info("🚀 You can now test all functionality from a clean state!")

if __name__ == "__main__":
    main()
