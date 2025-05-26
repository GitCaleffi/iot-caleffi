import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database.local_storage import LocalStorage

def test_database():
    """Test database storage and retrieval"""
    storage = LocalStorage()
    
    try:
        # Insert some test data
        print("Inserting test barcodes...")
        test_data = [
            ("DEVICE001", "TEST123456"),
            ("DEVICE001", "TEST789012"),
            ("DEVICE001", "TEST345678")
        ]
        
        for device_id, barcode in test_data:
            storage.save_scan(device_id, barcode)
            print(f"✓ Saved barcode: {barcode}")
        
        # Verify data was saved
        print("\nRetrieving recent scans...")
        scans = storage.get_recent_scans(5)
        if scans:
            print("\nFound scans in database:")
            for scan in scans:
                print(f"- Device: {scan['device_id']}, Barcode: {scan['barcode']}, Time: {scan['timestamp']}")
        else:
            print("No scans found in database")
            
    except Exception as e:
        print(f"Error during test: {e}")
    finally:
        storage.close()

if __name__ == "__main__":
    test_database()