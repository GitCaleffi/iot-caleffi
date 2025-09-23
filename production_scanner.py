2532662747
#!/usr/bin/env python3
import sys
import json
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
from barcode_scanner_app import process_barcode_scan, register_device_id

DEVICE_CONFIG_FILE = '/var/www/html/abhimanyu/barcode_scanner_clean/device_config.json'

def load_device_id():
    """Load device ID from config file"""
    if os.path.exists(DEVICE_CONFIG_FILE):
        try:
            with open(DEVICE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('device_id')
        except:
            pass
    return None

def save_device_id(device_id):
    """Save device ID to config file"""
    config = {'device_id': device_id}
    with open(DEVICE_CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def main():
    device_id = load_device_id()
    
    if not device_id:
        print("🔧 DEVICE REGISTRATION REQUIRED")
        print("📱 Scan a barcode to register this device:")
        print("=" * 50)
        
        while True:
            try:
                barcode = input().strip()
                if barcode and len(barcode) >= 8:
                    print(f"📝 Registering device with barcode: {barcode}")
                    
                    try:
                        result = register_device_id(barcode)
                        if result:
                            device_id = barcode
                            save_device_id(device_id)
                            print(f"✅ Device registered: {device_id}")
                            break
                        else:
                            print("❌ Registration failed, try again")
                    except Exception as e:
                        print(f"❌ Registration error: {e}")
                        print("Try again...")
            except KeyboardInterrupt:
                print("\n🛑 Registration cancelled")
                return
    
    print(f"🎯 PRODUCTION BARCODE SCANNER")
    print(f"📱 Device ID: {device_id}")
    print("🔍 Scan Mode: Production")
    print("📊 Ready for barcodes...")
    print("💡 Scan barcode or type 'process <barcode>'")
    print("=" * 50)
    
    while True:
        try:
            user_input = input().strip()
            
            if user_input.startswith('process '):
                barcode = user_input[8:].strip()
            elif user_input.isdigit() and len(user_input) >= 8:
                barcode = user_input
            else:
                continue
                
            print(f"\n📦 BARCODE: {barcode}")
            print("=" * 30)
            
            try:
                result = process_barcode_scan(barcode, device_id)
                if result:
                    print("✅ Sent to IoT Hub!")
                else:
                    print("❌ Failed to send")
            except Exception as e:
                print(f"❌ Error: {e}")
                
            print("\n🔍 Ready for next barcode...")
            
        except KeyboardInterrupt:
            print("\n🛑 Scanner stopped")
            break

if __name__ == "__main__":
    main()
