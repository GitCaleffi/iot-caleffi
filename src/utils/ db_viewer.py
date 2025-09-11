import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database.local_storage import LocalStorage
from src.utils.config import load_config

class DatabaseViewer:
    def __init__(self):
        self.storage = LocalStorage()

    def view_recent_scans(self, limit=10):
        """Display recent barcode scans from the database"""
        try:
            print("\n=== Recent Barcode Scans ===")
            print("=" * 40)
            
            scans = self.storage.get_recent_scans(limit)
            if not scans:
                print("No scans found in database")
                return

            for scan in scans:
                print(f"Device ID: {scan['device_id']}")
                print(f"Barcode: {scan['barcode']}")
                print(f"Timestamp: {scan['timestamp']}")
                print("-" * 40)

        except Exception as e:
            print(f"Error viewing database: {e}")
        finally:
            self.storage.close()

def main():
    try:
        viewer = DatabaseViewer()
        viewer.view_recent_scans()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()