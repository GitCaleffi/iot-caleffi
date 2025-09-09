#!/usr/bin/env python3
"""
Database Cleanup Script
Clears all registered devices and barcode scan history from the local database
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))
sys.path.append(str(project_root / 'src'))

from src.database.local_storage import LocalStorage

def main():
    """Clear all database records"""
    print("🔄 Starting database cleanup...")
    
    try:
        # Initialize local storage
        local_db = LocalStorage()
        
        # Test connection first
        local_db.test_connection()
        print("✅ Database connection successful")
        
        # Perform complete database reset
        result = local_db.reset_database()
        
        if result['success']:
            print(f"\n🎉 {result['message']}")
            print("\n📊 Details:")
            for table, count in result['details'].items():
                print(f"  • {table}: {count} records cleared")
        else:
            print(f"❌ Database reset failed: {result.get('message', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error during database cleanup: {e}")
        return 1
    
    print("\n✅ Database cleanup complete!")
    return 0

if __name__ == "__main__":
    exit(main())
