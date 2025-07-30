import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.database.local_storage import LocalStorage
from src.iot.hub_client import HubClient

def check_system_status():
    """Check both database and IoT Hub status"""
    print("\n=== System Status Check ===")
    print("=" * 40)
    
    # Check Database Status
    try:
        db = LocalStorage()
        recent_scans = db.get_recent_scans(5)
        print("\n📁 Database Status:")
        print("-" * 20)
        print(f"Database Connected: ✓")
        print(f"Recent Scans: {len(recent_scans)}")
        if recent_scans:
            print("\nLast 5 Scans:")
            for scan in recent_scans:
                print(f"- {scan['barcode']} (Device: {scan['device_id']}, Time: {scan['timestamp']})")
    except Exception as e:
        print(f"Database Error: {e}")
    finally:
        db.close()

    # Check IoT Hub Status
    print("\n📡 IoT Hub Status:")
    print("-" * 20)
    try:
        # Load config to get connection string
        from src.utils.config import load_config
        config = load_config()
        connection_string = config["iot_hub"]["connection_string"]
        
        iot = HubClient(connection_string)
        connected = iot.connect()
        status = iot.get_status()
        
        print(f"IoT Hub Connected: {'✓' if connected else '✗'}")
        print(f"Device ID: {status['deviceId']}")
        print(f"Messages Sent: {status['messages_sent']}")
        if status['last_message_time']:
            print(f"Last Message Sent: {status['last_message_time']}")
    except Exception as e:
        print(f"IoT Hub Error: {e}")
    finally:
        iot.disconnect()

def main():
    try:
        check_system_status()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()