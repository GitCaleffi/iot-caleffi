#!/usr/bin/env python3
import sys
import json
import os
import time
from pathlib import Path

# Dynamically find the deployment package path
current_dir = Path(__file__).resolve().parent
deployment_src = current_dir / 'deployment_package' / 'src'
sys.path.append(str(deployment_src))

try:
    from barcode_scanner_app import process_barcode_scan, register_device_id, confirm_registration
except ImportError as e:
    print(f"❌ Error importing from barcode_scanner_app: {e}")
    print("💡 Make sure you're running from the correct directory")
    sys.exit(1)

# GPIO LED control
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # LED pins
    RED_LED = 18
    YELLOW_LED = 23
    GREEN_LED = 24
    
    GPIO.setup(RED_LED, GPIO.OUT)
    GPIO.setup(YELLOW_LED, GPIO.OUT)
    GPIO.setup(GREEN_LED, GPIO.OUT)
    
    def led_off():
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
    
    def led_green():
        led_off()
        GPIO.output(GREEN_LED, GPIO.HIGH)
    
    def led_yellow():
        led_off()
        GPIO.output(YELLOW_LED, GPIO.HIGH)
    
    def led_red():
        led_off()
        GPIO.output(RED_LED, GPIO.HIGH)
        
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    def led_off(): pass
    def led_green(): pass
    def led_yellow(): pass
    def led_red(): pass
    GPIO_AVAILABLE = False

# Dynamically find the device config file path
DEVICE_CONFIG_FILE = current_dir / 'device_config.json'

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

def register_device_with_iot(device_id):
    """Use exact same registration flow as barcode_scanner_app.py"""
    try:
        print("📡 Step 1: Scanning test barcode for registration...")
        # First, scan the test barcode (required step)
        test_result = register_device_id("817994ccfe14")
        if not test_result or "❌" in test_result:
            print(f"❌ Test barcode scan failed: {test_result}")
            return False

        print("✅ Test barcode scanned successfully")

        print("📡 Step 2: Confirming device registration...")
        # Then confirm registration with the provided device ID
        confirm_result = confirm_registration("817994ccfe14", device_id)
        if not confirm_result or "❌" in confirm_result:
            print(f"❌ Device registration confirmation failed: {confirm_result}")
            return False

        print("✅ Device registration confirmed successfully")
        print(f"📱 Device ID: {device_id}")
        return True

    except Exception as e:
        print(f"❌ Registration error: {e}")
        return False

def main():
    led_off()
    device_id = load_device_id()
    
    if not device_id:
        print("🔧 DEVICE REGISTRATION REQUIRED")
        print("📱 Scan barcode to register this device:")
        print("💡 Sample device ID: a5944658fdf7")
        if GPIO_AVAILABLE:
            print("💡 LEDs: Green=Success, Yellow=Already registered, Red=Error")
        print("=" * 50)
        
        while True:
            try:
                barcode = input().strip()
                if barcode and len(barcode) >= 8 and barcode.replace('-', '').replace('_', '').isalnum():
                    print(f"📝 Registering device: {barcode}")
                    
                    try:
                        # Register device with IoT Hub
                        result = register_device_with_iot(barcode)
                        if result:
                            device_id = barcode
                            save_device_id(device_id)
                            print(f"✅ Device registered successfully: {device_id}")
                            print("📡 Device registration sent to IoT Hub")
                            led_green()
                            time.sleep(2)
                            led_off()
                            break
                        else:
                            print("❌ Device registration failed, try again")
                            led_red()
                            time.sleep(1)
                            led_off()
                    except Exception as e:
                        print(f"❌ Registration error: {e}")
                        led_red()
                        time.sleep(1)
                        led_off()
                else:
                    print("❌ Invalid barcode format")
                    print("💡 Valid formats: alphanumeric, minimum 8 characters")
                    led_red()
                    time.sleep(1)
                    led_off()
            except KeyboardInterrupt:
                print("\n🛑 Registration cancelled")
                led_off()
                return
    else:
        # Device already registered
        print(f"📱 Device already registered: {device_id}")
        led_yellow()
        time.sleep(1)
        led_off()
    
    print(f"\n🎯 BARCODE SCANNER READY")
    print(f"📱 Device ID: {device_id}")
    print("🔍 Mode: Quantity Update")
    print("📊 Scan barcodes to update quantities...")
    print("💡 Commands:")
    print("   • Scan barcode or type 'process <barcode>'")
    print("   • 'register' or 'reregister' - Register new device")
    print("   • 'status' or 'info' - Show current device info")
    if GPIO_AVAILABLE:
        print("💡 LEDs: Green=Success, Red=Error")
    print("=" * 50)
    
    while True:
        try:
            user_input = input().strip()

            # Check for special commands
            if user_input.lower() == 'register' or user_input.lower() == 'reregister':
                print("\n🔧 DEVICE RE-REGISTRATION")
                print("📱 Enter new device ID to register:")
                print("💡 Sample device ID: a5944658fdf7")
                if GPIO_AVAILABLE:
                    print("💡 LEDs: Green=Success, Yellow=Already registered, Red=Error")
                print("=" * 50)

                try:
                    new_device_input = input().strip()
                    if new_device_input and len(new_device_input) >= 8 and new_device_input.replace('-', '').replace('_', '').isalnum():
                        print(f"📝 Registering new device: {new_device_input}")

                        try:
                            # Register the new device
                            result = register_device_with_iot(new_device_input)
                            if result:
                                device_id = new_device_input
                                save_device_id(device_id)
                                print(f"✅ New device registered successfully: {device_id}")
                                print("📡 Device registration sent to IoT Hub")
                                print(f"\n🎯 BARCODE SCANNER READY")
                                print(f"📱 Device ID: {device_id}")
                                print("🔍 Mode: Quantity Update")
                                led_green()
                                time.sleep(2)
                                led_off()
                            else:
                                print("❌ Device registration failed, keeping current device")
                                led_red()
                                time.sleep(1)
                                led_off()
                        except Exception as e:
                            print(f"❌ Registration error: {e}")
                            led_red()
                            time.sleep(1)
                            led_off()
                    else:
                        print("❌ Invalid device ID format")
                        print("💡 Valid formats: alphanumeric, minimum 8 characters")
                        led_red()
                        time.sleep(1)
                        led_off()
                except KeyboardInterrupt:
                    print("\n🛑 Registration cancelled")
                    led_off()
                continue

            elif user_input.lower() == 'status' or user_input.lower() == 'info':
                print(f"\n📋 DEVICE STATUS")
                print(f"📱 Current Device ID: {device_id}")
                print(f"🔍 Mode: Quantity Update")
                print("💡 Commands: 'register' (new device), 'status' (info), or scan barcode")
                print("=" * 50)
                continue

            elif user_input.startswith('process '):
                barcode = user_input[8:].strip()
            elif len(user_input) >= 8 and user_input.replace('-', '').replace('_', '').isalnum():
                barcode = user_input
            else:
                if user_input:
                    print("❌ Invalid barcode format")
                    print("💡 Try: 'register' (new device), 'status' (info), or scan a barcode")
                    print("💡 Valid formats: alphanumeric, minimum 8 characters")
                    led_red()
                    time.sleep(1)
                    led_off()
                continue
                
            print(f"\n📦 QUANTITY UPDATE - BARCODE: {barcode}")
            print("=" * 40)
            
            try:
                # Always use the registered device ID for barcode scanning
                from database.local_storage import LocalStorage
                local_db = LocalStorage()

                # Ensure the correct device ID is saved to local database
                local_db.save_device_id(device_id)

                # Create a custom barcode processing function that uses the correct device ID
                def process_barcode_with_device(barcode, device_id=device_id):
                    """Process barcode scan with the specified device ID"""
                    try:
                        from iot.hub_client import HubClient
                        from utils.config import load_config
                        from api.api_client import ApiClient
                        from utils.barcode_validator import validate_ean, BarcodeValidationError

                        api_client = ApiClient()

                        # Validate barcode format
                        try:
                            validated_barcode = validate_ean(barcode)
                        except BarcodeValidationError as e:
                            return f"❌ Barcode validation error: {str(e)}"

                        # Save scan to local database with correct device ID
                        timestamp = local_db.save_scan(device_id, validated_barcode)

                        # Check if we're online
                        is_online = api_client.is_online()
                        if not is_online:
                            return f"📥 Device appears to be offline. Message saved locally for device '{device_id}'."

                        # Send to API
                        api_result = api_client.send_barcode_scan(device_id, validated_barcode, 1)
                        api_success = api_result.get("success", False)
                        if not api_success:
                            return f"⚠️ API call failed. Barcode saved locally for device '{device_id}'."

                        # Send to IoT Hub
                        config = load_config()
                        if config and config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string"):
                            connection_string = config["iot_hub"]["devices"][device_id]["connection_string"]
                            hub_client = HubClient(connection_string)
                            iot_success = hub_client.send_message(validated_barcode, device_id)

                            if iot_success:
                                local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
                                return f"✅ Barcode {validated_barcode} sent to IoT Hub from device '{device_id}'!"
                            else:
                                return f"⚠️ Barcode sent to API but failed to send to IoT Hub from device '{device_id}'."
                        else:
                            return f"⚠️ Barcode sent to API but no IoT Hub connection string found for device '{device_id}'."

                    except Exception as e:
                        return f"❌ Error processing barcode: {str(e)}"

                result = process_barcode_with_device(barcode)
                if "✅" in result:
                    print("✅ Quantity updated - sent to IoT Hub!")
                    print("💾 Saved to local database")
                    led_green()
                    time.sleep(1)
                    led_off()
                else:
                    print(result)
                    if "❌" in result:
                        led_red()
                    else:
                        led_yellow()
                    time.sleep(1)
                    led_off()
            except Exception as e:
                print(f"❌ Error: {e}")
                led_red()
                time.sleep(1)
                led_off()
                
            print("\n🔍 Ready for next barcode...")
            
        except KeyboardInterrupt:
            print("\n🛑 Scanner stopped")
            led_off()
            break

if __name__ == "__main__":
    try:
        main()
    finally:
        if GPIO_AVAILABLE:
            GPIO.cleanup()
