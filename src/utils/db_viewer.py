import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import re

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database.local_storage import LocalStorage

class DatabaseViewer:
    def __init__(self):
        self.storage = LocalStorage()
        
    def format_timestamp(self, timestamp):
        """Format timestamp to match required format: 2025-05-09T10:34:17.353Z
        This handles various input timestamp formats and standardizes them
        """
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
            return timestamp

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
                print(f"Timestamp: {self.format_timestamp(scan['timestamp'])}")
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