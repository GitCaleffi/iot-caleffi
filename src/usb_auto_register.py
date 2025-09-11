#!/usr/bin/env python3
"""
USB Auto-Register Script
Automatically captures USB scanner input and registers device
"""

import sys
import select
import tty
import termios
import time
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

from database.local_storage import LocalStorage
from utils.config import load_config
from api.api_client import ApiClient
from iot.hub_client import HubClient
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize components
local_db = LocalStorage()
api_client = ApiClient()

def register_device_with_barcode(barcode):
    """Register device using scanned barcode"""
    try:
        print(f"\n🔍 Processing barcode: {barcode}")
        
        # Check if device already registered
        existing_device = local_db.get_device_id()
        if existing_device:
            print(f"⚠️ Device already registered: {existing_device}")
            return existing_device
        
        # Check if online
        if not api_client.is_online():
            print("❌ Device is offline. Cannot register.")
            return None
        
        # Try to register with API
        api_url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {"scannedBarcode": barcode}
        
        print("📡 Calling registration API...")
        api_result = api_client.send_registration_barcode(api_url, payload)
        
        if api_result.get("success", False) and "response" in api_result:
            response_data = json.loads(api_result["response"])
            
            if response_data.get("deviceId") and response_data.get("responseCode") == 200:
                device_id = response_data.get("deviceId")
                
                # Save device ID
                local_db.save_device_id(device_id)
                print(f"✅ Device registered: {device_id}")
                
                # Register with IoT Hub
                try:
                    from iot_registration import register_device_with_iot_hub
                    iot_result = register_device_with_iot_hub(device_id)
                    if iot_result.get("success"):
                        print("✅ IoT Hub registration successful")
                    else:
                        print(f"⚠️ IoT Hub registration failed: {iot_result.get('error')}")
                except Exception as e:
                    print(f"⚠️ IoT Hub registration error: {e}")
                
                return device_id
            else:
                print(f"❌ API returned error: {response_data}")
                return None
        else:
            print(f"❌ API call failed: {api_result.get('message', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return None

def capture_usb_input():
    """Capture input from USB scanner"""
    print("🔌 USB Auto-Register Mode")
    print("📱 Scan a barcode with your USB scanner to register device...")
    print("Press Ctrl+C to exit")
    
    # Save terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        # Set terminal to raw mode
        tty.setraw(sys.stdin.fileno())
        
        barcode_buffer = ""
        
        while True:
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)
                
                # Handle Enter key (barcode complete)
                if ord(char) == 13 or ord(char) == 10:  # Enter or newline
                    if barcode_buffer.strip():
                        print(f"\n📱 Scanned: {barcode_buffer}")
                        
                        # Process the barcode
                        device_id = register_device_with_barcode(barcode_buffer.strip())
                        
                        if device_id:
                            print(f"🎉 Registration complete! Device ID: {device_id}")
                            print("✅ You can now use the web interface for barcode scanning")
                            break
                        else:
                            print("❌ Registration failed. Try scanning again.")
                            
                        barcode_buffer = ""
                    
                # Handle Ctrl+C
                elif ord(char) == 3:
                    print("\n👋 Exiting...")
                    break
                    
                # Handle backspace
                elif ord(char) == 127:
                    if barcode_buffer:
                        barcode_buffer = barcode_buffer[:-1]
                        
                # Add character to buffer
                elif 32 <= ord(char) <= 126:  # Printable characters
                    barcode_buffer += char
                    
            time.sleep(0.01)  # Small delay to prevent high CPU usage
            
    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

if __name__ == "__main__":
    capture_usb_input()