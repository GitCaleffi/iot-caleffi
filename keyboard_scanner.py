#!/usr/bin/env python3
import sys
import json
import os
import time
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src')
from barcode_scanner_app import process_barcode_scan, register_device_id, get_registration_status

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
except ImportError:
    def led_off(): pass
    def led_green(): pass
    def led_yellow(): pass
    def led_red(): pass
    GPIO_AVAILABLE = False

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
    led_off()
    device_id = load_device_id()
    
    if not device_id:
        print("🔧 DEVICE REGISTRATION")
        print("📱 Scan barcode to register this device:")
        if GPIO_AVAILABLE:
            print("💡 GPIO LEDs: Green=Success, Yellow=Already registered, Red=Invalid")
        print("=" * 50)
        
        while True:
            try:
                barcode = input().strip()
                if barcode and len(barcode) >= 8:
                    print(f"📝 Registering device: {barcode}")
                    
                    try:
                        result = register_device_id(barcode)
                        if result:
                            device_id = barcode
                            save_device_id(device_id)
                            print(f"✅ Device registered successfully: {device_id}")
                            print("📡 Registration sent to IoT Hub")
                            led_green()
                            time.sleep(2)
                            led_off()
                            break
                        else:
                            print("❌ Registration failed, try again")
                            led_red()
                            time.sleep(1)
                            led_off()
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        led_red()
                        time.sleep(1)
                        led_off()
                else:
                    print("❌ Invalid barcode format")
                    led_red()
                    time.sleep(1)
                    led_off()
            except KeyboardInterrupt:
                print("\n🛑 Registration cancelled")
                led_off()
                return
    else:
        # Device already registered
        led_yellow()
        time.sleep(1)
        led_off()
    
    print(f"🎯 BARCODE SCANNER READY")
    print(f"📱 Device ID: {device_id}")
    print("🔍 Scan Mode: Keyboard Input")
    print("📊 Scan barcodes to update quantity...")
    print("💡 Scan barcode or type 'process <barcode>'")
    if GPIO_AVAILABLE:
        print("💡 LEDs: Green=Success, Red=Error")
    print("=" * 50)
    
    while True:
        try:
            user_input = input().strip()
            
            if user_input.startswith('process '):
                barcode = user_input[8:].strip()
            elif user_input.isdigit() and len(user_input) >= 8:
                barcode = user_input
            else:
                if user_input:
                    print("❌ Invalid barcode format")
                    led_red()
                    time.sleep(1)
                    led_off()
                continue
                
            print(f"\n📦 BARCODE: {barcode}")
            print("=" * 30)
            
            try:
                result = process_barcode_scan(barcode, device_id)
                if result:
                    print("✅ Quantity updated - sent to IoT Hub!")
                    print("💾 Saved to local database")
                    led_green()
                    time.sleep(1)
                    led_off()
                else:
                    print("❌ Failed to send to IoT Hub")
                    print("💾 Saved locally for retry")
                    led_red()
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
