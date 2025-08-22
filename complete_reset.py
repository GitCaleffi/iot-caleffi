#!/usr/bin/env python3
"""
Complete system reset script - clears ALL data including dynamic device manager cache
"""

import os
import sys
import json
import sqlite3
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_all_databases():
    """Clear all SQLite databases"""
    db_files = [
        "barcode_scans.db",
        "barcode_scanner.db", 
        "barcode_device_mapping.db",
        "src/barcode_device_mapping.db"
    ]
    
    for db_file in db_files:
        if os.path.exists(db_file):
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                
                # Get all table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                # Clear each table
                for table in tables:
                    table_name = table[0]
                    if table_name != 'sqlite_sequence':
                        cursor.execute(f"DELETE FROM {table_name}")
                        logger.info(f"  ✅ Cleared table: {table_name} in {db_file}")
                
                conn.commit()
                conn.close()
                logger.info(f"✅ Cleared database: {db_file}")
                
            except Exception as e:
                logger.error(f"Error clearing {db_file}: {e}")

def clear_dynamic_device_manager():
    """Clear dynamic device manager cache and config"""
    config_files = [
        "device_config.json",
        "src/device_config.json",
        "device_registry.json",
        "src/device_registry.json"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            try:
                os.remove(config_file)
                logger.info(f"✅ Removed: {config_file}")
            except Exception as e:
                logger.error(f"Error removing {config_file}: {e}")

def clear_logs():
    """Clear all log files"""
    log_patterns = ["*.log", "logs/*.log", "src/*.log"]
    
    for pattern in log_patterns:
        try:
            os.system(f"find . -name '{pattern}' -type f -exec truncate -s 0 {{}} \\; 2>/dev/null")
        except:
            pass
    
    logger.info("✅ Cleared all log files")

def reset_config():
    """Reset config.json to clean state"""
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
            
            # Clear device-specific settings
            if "iot_hub" in config:
                config["iot_hub"]["device_connection_string"] = ""
            
            with open("config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            logger.info("✅ Reset config.json")
    except Exception as e:
        logger.error(f"Error resetting config: {e}")

def clear_cache_files():
    """Clear Python cache and temporary files"""
    try:
        os.system("find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
        os.system("find . -name '*.pyc' -type f -delete 2>/dev/null")
        logger.info("✅ Cleared Python cache files")
    except:
        pass

def main():
    logger.info("🧹 Starting COMPLETE system reset...")
    
    # Clear all data sources
    clear_all_databases()
    clear_dynamic_device_manager()
    clear_logs()
    reset_config()
    clear_cache_files()
    
    logger.info("🎉 COMPLETE system reset finished!")
    logger.info("")
    logger.info("📋 Everything cleared:")
    logger.info("  • All SQLite databases")
    logger.info("  • Dynamic device manager cache")
    logger.info("  • All device registrations")
    logger.info("  • All barcode scans")
    logger.info("  • All log files")
    logger.info("  • Python cache files")
    logger.info("")
    logger.info("🚀 System is now completely clean for fresh testing!")

if __name__ == "__main__":
    main()
