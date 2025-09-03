#!/usr/bin/env python3
"""
Migration Script: Static to Dynamic Barcode Scanner
Migrates existing devices from static system to dynamic device management
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from database.local_storage import LocalStorage
from utils.dynamic_device_manager import device_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_existing_devices():
    """Migrate existing devices from static system to dynamic system"""
    
    print("🔄 Starting migration from static to dynamic device management...")
    
    # Initialize local database
    local_db = LocalStorage()
    
    try:
        # Get existing device from local storage
        existing_device_id = local_db.get_device_id()
        
        if existing_device_id:
            print(f"📱 Found existing device: {existing_device_id}")
            
            # Check if already migrated
            if device_manager.is_device_registered(existing_device_id):
                print(f"✅ Device {existing_device_id} already migrated to dynamic system")
                return True
            
            # Generate a migration token
            migration_token = device_manager.generate_registration_token(f"migration_{existing_device_id}")
            
            # Create device info for migration
            device_info = {
                "registration_method": "migration_from_static",
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "original_system": "static_test_barcode",
                "migration_token": migration_token
            }
            
            # Register the device in the dynamic system
            success, message = device_manager.register_device(migration_token, existing_device_id, device_info)
            
            if success:
                print(f"✅ Successfully migrated device {existing_device_id} to dynamic system")
                print(f"📝 Migration details: {message}")
                return True
            else:
                print(f"❌ Failed to migrate device {existing_device_id}: {message}")
                return False
        else:
            print("ℹ️  No existing device found in local storage")
            return True
            
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        logger.error(f"Migration error: {str(e)}")
        return False

def create_backup():
    """Create backup of current configuration"""
    try:
        backup_dir = Path("backup")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Backup local database if it exists
        local_db = LocalStorage()
        if hasattr(local_db, 'db_path') and Path(local_db.db_path).exists():
            backup_db_path = backup_dir / f"barcode_scans_backup_{timestamp}.db"
            import shutil
            shutil.copy2(local_db.db_path, backup_db_path)
            print(f"📦 Database backed up to: {backup_db_path}")
        
        # Backup config if it exists
        config_path = Path("config.json")
        if config_path.exists():
            backup_config_path = backup_dir / f"config_backup_{timestamp}.json"
            import shutil
            shutil.copy2(config_path, backup_config_path)
            print(f"📦 Config backed up to: {backup_config_path}")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Backup failed: {str(e)}")
        return False

def verify_migration():
    """Verify that migration was successful"""
    try:
        print("\n🔍 Verifying migration...")
        
        # Get stats from dynamic device manager
        stats = device_manager.get_registration_stats()
        
        print(f"📊 Dynamic system statistics:")
        print(f"   - Total devices: {stats['total_devices']}")
        print(f"   - Active devices: {stats['active_devices']}")
        print(f"   - Pending registrations: {stats['pending_registrations']}")
        
        # Check local device
        local_db = LocalStorage()
        existing_device_id = local_db.get_device_id()
        
        if existing_device_id:
            device_info = device_manager.get_device_info(existing_device_id)
            if device_info:
                print(f"✅ Device {existing_device_id} successfully registered in dynamic system")
                print(f"   - Registration method: {device_info.get('device_info', {}).get('registration_method', 'Unknown')}")
                print(f"   - Status: {device_info.get('status', 'Unknown')}")
                return True
            else:
                print(f"❌ Device {existing_device_id} not found in dynamic system")
                return False
        else:
            print("ℹ️  No local device to verify")
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {str(e)}")
        return False

def main():
    """Main migration process"""
    print("=" * 60)
    print("🚀 BARCODE SCANNER MIGRATION TOOL")
    print("   Static → Dynamic Device Management")
    print("=" * 60)
    
    # Step 1: Create backup
    print("\n📦 Step 1: Creating backup...")
    backup_success = create_backup()
    if not backup_success:
        print("⚠️  Backup failed, but continuing with migration...")
    
    # Step 2: Migrate devices
    print("\n🔄 Step 2: Migrating devices...")
    migration_success = migrate_existing_devices()
    
    if not migration_success:
        print("\n❌ Migration failed!")
        return False
    
    # Step 3: Verify migration
    print("\n🔍 Step 3: Verifying migration...")
    verification_success = verify_migration()
    
    if verification_success:
        print("\n" + "=" * 60)
        print("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📋 Next steps:")
        print("1. Test the new dynamic barcode scanner app:")
        print("   python src/barcode_scanner_app_dynamic.py")
        print("\n2. The new system supports:")
        print("   ✅ Dynamic device registration (no hardcoded barcodes)")
        print("   ✅ Scalable for 50,000+ users")
        print("   ✅ Token-based registration system")
        print("   ✅ Flexible barcode validation")
        print("\n3. Your existing device has been migrated automatically")
        print("   and will continue working with all existing functionality.")
        
        return True
    else:
        print("\n❌ Migration verification failed!")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
