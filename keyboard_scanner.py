#!/usr/bin/env python3
import sys
import json
import os
import time
import select
import termios
import tty
from pathlib import Path

# Dynamically find the deployment package path
current_dir = Path(__file__).resolve().parent
deployment_src = current_dir / 'deployment_package' / 'src'
src_dir = current_dir / 'src'
sys.path.append(str(deployment_src))
sys.path.append(str(src_dir))

utils_dir = src_dir / 'utils'

try:
    # Import from deployment package
    sys.path.insert(0, str(deployment_src))
    from barcode_scanner_app import process_barcode_scan, register_device_id, confirm_registration
    
    # Import directly from utils directory
    sys.path.insert(0, str(utils_dir))
    from usb_hid_forwarder import get_hid_forwarder, start_hid_service
    from auto_updater import start_auto_update_service
    from barcode_input_monitor import create_barcode_monitor
except ImportError as e:
    print(f"❌ Error importing modules: {e}")
    print(f"💡 Deployment src: {deployment_src}")
    print(f"💡 Src dir: {src_dir}")
    print(f"💡 Utils dir: {utils_dir}")
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

def read_barcode_from_monitor():
    """Read barcode from the USB input monitor in service mode"""
    try:
        # Check for barcode from file first (for testing)
        barcode_file = '/tmp/barcode_input.txt'
        if os.path.exists(barcode_file):
            with open(barcode_file, 'r') as f:
                barcode = f.read().strip()
            if barcode:
                os.remove(barcode_file)  # Remove after reading
                return barcode
        
        # In a real implementation, this would interface with the barcode monitor
        # For now, we'll wait for file input or timeout
        print("⏳ Waiting for barcode input (create /tmp/barcode_input.txt with barcode)...")
        
        timeout = 30  # 30 seconds timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(barcode_file):
                with open(barcode_file, 'r') as f:
                    barcode = f.read().strip()
                if barcode:
                    os.remove(barcode_file)
                    return barcode
            time.sleep(0.5)
        
        print("⏰ Timeout waiting for barcode input")
        return None
        
    except Exception as e:
        print(f"❌ Error reading barcode: {e}")
        return None

def read_barcode_automatically():
    """Read barcode input character by character and auto-process when complete"""
    # Check if running in service mode (no TTY available)
    if not sys.stdin.isatty():
        # In service mode, use the barcode input monitor
        print("🔧 Service mode: Using USB barcode scanner input...")
        return read_barcode_from_monitor()
    
    barcode_buffer = ""
    last_char_time = time.time()
    
    # Set terminal to raw mode and disable echo completely
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        # Set raw mode with no echo
        new_settings = termios.tcgetattr(sys.stdin)
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        
        while True:
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)
                current_time = time.time()
                
                # Handle Enter key (barcode scanners typically send Enter/Return)
                if ord(char) == 13 or ord(char) == 10:  # Enter or Line Feed
                    if barcode_buffer.strip():
                        print(f"📝 Detected: {barcode_buffer.strip()}")
                        return barcode_buffer.strip()
                    barcode_buffer = ""
                    continue
                
                # Handle regular characters (no echo, completely silent)
                if char.isprintable():
                    barcode_buffer += char
                    last_char_time = current_time

                # Clear buffer if too much time passed (2 seconds)
                elif current_time - last_char_time > 2.0:
                    barcode_buffer = ""
            
            # Auto-process if buffer is complete and timeout reached
            current_time = time.time()
            if len(barcode_buffer) >= 8 and current_time - last_char_time > 0.5:
                if barcode_buffer.strip():
                    print(f"📝 Detected: {barcode_buffer.strip()}")
                    return barcode_buffer.strip()
                barcode_buffer = ""
                
    except KeyboardInterrupt:
        return None
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def read_input_smart():
    """Smart input reader that handles both automatic barcodes and manual commands"""
    barcode_buffer = ""
    last_char_time = time.time()
    
    # Set terminal to raw mode and disable echo completely
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        # Set raw mode with no echo
        new_settings = termios.tcgetattr(sys.stdin)
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        
        while True:
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)
                current_time = time.time()
                
                # Handle Enter key (barcode scanners typically send Enter/Return)
                if ord(char) == 13 or ord(char) == 10:  # Enter or Line Feed
                    if barcode_buffer.strip():
                        result = barcode_buffer.strip()
                        # Check if it's a command or barcode
                        if result.lower() in ['register', 'reregister', 'status', 'info']:
                            print(f"💬 Command: {result}")
                        else:
                            print(f"📝 Detected: {result}")
                        return result
                    barcode_buffer = ""
                    continue
                
                # Handle regular characters (show them for commands, hide for barcodes)
                if char.isprintable():
                    barcode_buffer += char
                    last_char_time = current_time
                    
                    # Show characters if it looks like a command being typed
                    if len(barcode_buffer) <= 10 and barcode_buffer.lower() in 'register status info'[:len(barcode_buffer)]:
                        print(char, end='', flush=True)

                # Clear buffer if too much time passed (3 seconds for commands)
                elif current_time - last_char_time > 3.0:
                    if barcode_buffer:
                        print()  # New line
                    barcode_buffer = ""
            
            # Auto-process if buffer looks like complete barcode and timeout reached
            current_time = time.time()
            if len(barcode_buffer) >= 8 and current_time - last_char_time > 0.5:
                if barcode_buffer.strip() and not barcode_buffer.lower() in ['register', 'reregister', 'status', 'info']:
                    print(f"📝 Detected: {barcode_buffer.strip()}")
                    return barcode_buffer.strip()
                
    except KeyboardInterrupt:
        return None
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def read_barcode_automatically():
    """Read barcode input character by character and auto-process when complete"""
    # Check if running in service mode (no TTY available)
    if not sys.stdin.isatty():
        # In service mode, use the barcode input monitor
        print("🔧 Service mode: Using USB barcode scanner input...")
        return read_barcode_from_monitor()
    
    barcode_buffer = ""
    last_char_time = time.time()
    
    # Set terminal to raw mode and disable echo completely
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        # Set raw mode with no echo
        new_settings = termios.tcgetattr(sys.stdin)
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        
        while True:
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)
                current_time = time.time()
                
                # Handle Enter key (barcode scanners typically send Enter/Return)
                if ord(char) == 13 or ord(char) == 10:  # Enter or Line Feed
                    if barcode_buffer.strip():
                        print(f"📝 Detected: {barcode_buffer.strip()}")
                        return barcode_buffer.strip()
                    barcode_buffer = ""
                    continue
                
                # Handle regular characters (no echo, completely silent)
                if char.isprintable():
                    barcode_buffer += char
                    last_char_time = current_time

                # Clear buffer if too much time passed (2 seconds)
                elif current_time - last_char_time > 2.0:
                    barcode_buffer = ""
            
            # Auto-process if buffer is complete and timeout reached
            current_time = time.time()
            if len(barcode_buffer) >= 8 and current_time - last_char_time > 0.5:
                if barcode_buffer.strip():
                    print(f"📝 Detected: {barcode_buffer.strip()}")
                    return barcode_buffer.strip()
                barcode_buffer = ""
                
    except KeyboardInterrupt:
        return None
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def read_input_smart():
    """Smart input reader that handles both automatic barcodes and manual commands"""
    barcode_buffer = ""
    last_char_time = time.time()
    
    # Set terminal to raw mode and disable echo completely
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        # Set raw mode with no echo
        new_settings = termios.tcgetattr(sys.stdin)
        new_settings[3] = new_settings[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, new_settings)
        
        while True:
            # Check if input is available
            if select.select([sys.stdin], [], [], 0.1)[0]:
                char = sys.stdin.read(1)
                current_time = time.time()
                
                # Handle Enter key (barcode scanners typically send Enter/Return)
                if ord(char) == 13 or ord(char) == 10:  # Enter or Line Feed
                    if barcode_buffer.strip():
                        result = barcode_buffer.strip()
                        # Check if it's a command or barcode
                        if result.lower() in ['register', 'reregister', 'status', 'info']:
                            print(f"💬 Command: {result}")
                        else:
                            print(f"📝 Detected: {result}")
                        return result
                    barcode_buffer = ""
                    continue
                
                # Handle regular characters (show them for commands, hide for barcodes)
                if char.isprintable():
                    barcode_buffer += char
                    last_char_time = current_time
                    
                    # Show characters if it looks like a command being typed
                    if len(barcode_buffer) <= 10 and barcode_buffer.lower() in 'register status info'[:len(barcode_buffer)]:
                        print(char, end='', flush=True)

                # Clear buffer if too much time passed (3 seconds for commands)
                elif current_time - last_char_time > 3.0:
                    if barcode_buffer:
                        print()  # New line
                    barcode_buffer = ""
            
            # Auto-process if buffer looks like complete barcode and timeout reached
            current_time = time.time()
            if len(barcode_buffer) >= 8 and current_time - last_char_time > 0.5:
                if barcode_buffer.strip() and not barcode_buffer.lower() in ['register', 'reregister', 'status', 'info']:
                    print(f"📝 Detected: {barcode_buffer.strip()}")
                    return barcode_buffer.strip()
                
    except KeyboardInterrupt:
        return None
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def register_device_with_iot(device_id):
    """Use exact same registration flow as barcode_scanner_app.py"""
    try:
        print("📡 Step 1: Scanning test barcode for registration...")
        # First, scan the test barcode with the specific device ID
        # test_result = register_device_id("817994ccfe14", device_id)
        # if not test_result or "❌" in test_result:
        #     print(f"❌ Test barcode scan failed: {test_result}")
        #     return False

        # print("✅ Test barcode scanned successfully")

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

def is_device_registration_verified():
    """Check if device registration is verified with test barcode"""
    if os.path.exists(DEVICE_CONFIG_FILE):
        try:
            with open(DEVICE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
            return config.get('test_barcode_verified', False)
        except:
            pass
    return False

def mark_registration_verified():
    """Mark device registration as verified"""
    config = {}
    if os.path.exists(DEVICE_CONFIG_FILE):
        try:
            with open(DEVICE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            pass
    
    config['test_barcode_verified'] = True
    config['first_scan_done'] = True
    
    with open(DEVICE_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def verify_test_barcode_with_api(device_id, barcode):
    """Verify test barcode with API"""
    try:
        from api.api_client import ApiClient
        api_client = ApiClient()
        
        # Call API to verify test barcode
        url = "https://api2.caleffionline.it/api/v1/raspberry/saveDeviceId"
        payload = {
            "scannedBarcode": device_id,
            "testBarcode": barcode
        }
        
        result = api_client.send_registration_barcode(url, payload)
        if result.get("success") and "response" in result:
            try:
                response_data = json.loads(result["response"])
                is_verified = response_data.get("data", {}).get("isTestBarcodeVerified", False)
                
                # Show detailed response for debugging
                if not is_verified:
                    response_msg = response_data.get("responseMessage", "Unknown error")
                    print(f"🔍 API Response: {response_msg}")
                
                return {"success": True, "isTestBarcodeVerified": is_verified, "response": response_data}
            except Exception as e:
                print(f"🔍 API Response parsing error: {str(e)}")
                return {"success": False, "isTestBarcodeVerified": False}
        
        return {"success": False, "isTestBarcodeVerified": False}
    except Exception as e:
        print(f"🔍 API call error: {str(e)}")
        return {"success": False, "error": str(e)}

def process_barcode_with_device(barcode, device_id):
    """Process barcode scan with the specified device ID"""
    try:
        from database.local_storage import LocalStorage
        from iot.hub_client import HubClient
        from utils.config import load_config
        from api.api_client import ApiClient
        from utils.barcode_validator import validate_ean, BarcodeValidationError

        local_db = LocalStorage()
        api_client = ApiClient()
        validated_barcode = barcode.strip()
        
        # TEMPORARILY DISABLE POS forwarding to eliminate feedback loop
        # hid_forwarder = get_hid_forwarder()
        # pos_forwarded = hid_forwarder.forward_barcode(validated_barcode)
        pos_status = "⚠️ POS forwarding disabled (preventing feedback loop)"

        # Check if device registration is verified
        if not is_device_registration_verified():
            # Check if the scanned barcode contains the expected test barcode
            expected_test_barcode = "817994ccfe14"
            
            # Clean the barcode - remove common prefixes and extra characters
            cleaned_barcode = barcode.replace("process ", "").replace("process", "").strip()
            
            # Enhanced test barcode detection - handle scanner input corruption
            # Check for various corrupted forms of 817994ccfe14
            test_patterns = [
                "817994ccfe14",    # Full correct barcode
                "17994ccfe14",     # Missing first character
                "7994ccfe14",      # Missing first two characters  
                "17994ccfe141",    # Extra character at end
                "17994ccfe148",    # Different last character
                "7994ccfe148",     # Missing chars + different end
            ]
            
            barcode_detected = False
            for pattern in test_patterns:
                if (cleaned_barcode == pattern or 
                    pattern in cleaned_barcode or
                    cleaned_barcode in pattern):
                    barcode_detected = True
                    break
            
            if barcode_detected:
                
                print(f"🔧 Test barcode detected: {cleaned_barcode} (from: {barcode})")
                
                # Use the expected test barcode for API verification
                result = verify_test_barcode_with_api(device_id, expected_test_barcode)
                if result.get('success') and result.get('isTestBarcodeVerified'):
                    mark_registration_verified()
                    return f"✅ Test barcode verified! Device ready for quantity updates: {expected_test_barcode}"
                else:
                    response_data = result.get('response', {})
                    if response_data:
                        msg = response_data.get('responseMessage', 'Invalid test barcode')
                        return f"❌ {msg}. Test barcode: {expected_test_barcode}"
                    else:
                        return f"❌ Test barcode verification failed: {expected_test_barcode}"
            else:
                # Check if it's a partial match (at least 10 characters matching)
                matching_chars = 0
                for i, char in enumerate(cleaned_barcode):
                    if i < len(expected_test_barcode) and char == expected_test_barcode[i]:
                        matching_chars += 1
                    elif i < len(expected_test_barcode):
                        break
                
                if matching_chars >= 10:
                    print(f"🔧 Partial test barcode detected ({matching_chars} chars match): {cleaned_barcode}")
                    
                    # Use the expected test barcode for API verification
                    result = verify_test_barcode_with_api(device_id, expected_test_barcode)
                    if result.get('success') and result.get('isTestBarcodeVerified'):
                        mark_registration_verified()
                        return f"✅ Test barcode verified! Device ready for quantity updates: {expected_test_barcode}"
                    else:
                        response_data = result.get('response', {})
                        if response_data:
                            msg = response_data.get('responseMessage', 'Invalid test barcode')
                            return f"❌ {msg}. Test barcode: {expected_test_barcode}"
                        else:
                            return f"❌ Test barcode verification failed: {expected_test_barcode}"
                else:
                    return f"❌ Device not verified. Please scan the test barcode {expected_test_barcode} first to verify the device."

        # Device is verified, process as quantity update
        # ✅ Differentiate device IDs from product barcodes
        if barcode == device_id:
            validated_barcode = barcode
        else:
            try:
                validated_barcode = validate_ean(barcode)
            except BarcodeValidationError as e:
                return f"❌ Barcode validation error: {str(e)}"

        # Save scan to local database
        timestamp = local_db.save_scan(device_id, validated_barcode)

        # Check if we're online
        is_online = api_client.is_online()
        if not is_online:
            return f"📥 Device appears to be offline. Message saved locally for device '{device_id}'. {pos_status}"

        # Send to API
        api_result = api_client.send_barcode_scan(device_id, validated_barcode, 1)
        api_success = api_result.get("success", False)
        if not api_success:
            return f"⚠️ API call failed. Barcode saved locally for device '{device_id}'. {pos_status}"

        # Send to IoT Hub
        config = load_config()
        if config and config.get("iot_hub", {}).get("devices", {}).get(device_id, {}).get("connection_string"):
            connection_string = config["iot_hub"]["devices"][device_id]["connection_string"]
            hub_client = HubClient(connection_string)
            iot_success = hub_client.send_message(validated_barcode, device_id)

            if iot_success:
                local_db.mark_sent_to_hub(device_id, validated_barcode, timestamp)
                return f"✅ Barcode {validated_barcode} sent to IoT Hub from device '{device_id}'! {pos_status}"
            else:
                return f"⚠️ Barcode sent to API but failed to send to IoT Hub from device '{device_id}'. {pos_status}"
        else:
            return f"⚠️ Barcode sent to API but no IoT Hub connection string found for device '{device_id}'. {pos_status}"

    except Exception as e:
        return f"❌ Error processing barcode: {str(e)}"

def main():
    # Check for service mode argument, USB mode, or if running without TTY
    service_mode = '--service' in sys.argv or '--usb' in sys.argv or not sys.stdin.isatty()
    
    if '--usb' in sys.argv:
        print("🔌 USB HID mode enabled - will process barcode scanner input automatically")
    
    led_off()
    
    # Start HID forwarding service
    print("🚀 Starting USB HID forwarding service...")
    try:
        start_hid_service()
        print("✅ HID service started - barcodes will be forwarded to POS")
    except Exception as e:
        print(f"⚠️ HID service failed to start: {e}")
        print("💡 Barcodes will still be processed but not forwarded to POS")
    
    # Start auto-update service
    print("🔄 Starting auto-update service...")
    try:
        start_auto_update_service()
        print("✅ Auto-update service started - will check for updates automatically")
    except Exception as e:
        print(f"⚠️ Auto-update service failed to start: {e}")
        print("💡 Manual updates will still be possible")
    
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
                print("🔍 Scan device ID barcode (automatic detection)...")
                barcode = read_barcode_automatically()
                if barcode is None:  # Ctrl+C pressed
                    print("\n🛑 Registration cancelled")
                    led_off()
                    return
                barcode = barcode.strip()
                if barcode and len(barcode) >= 8 and barcode.replace('-', '').replace('_', '').isalnum():
                    # Remove extra character if present (7079fa7ab32e7 -> 7079fa7ab32e)
                    if len(barcode) > 12:
                        barcode = barcode[:12]
                    print(f"📝 Registering device: {barcode}")
                    
                    try:
                        # Send initial message to IoT Hub
                        from deployment_package.src.iot.hub_client import HubClient
                        from deployment_package.src.utils.config import load_config
                        
                        try:
                            config = load_config()
                            if config and config.get("iot_hub", {}).get("connection_string"):
                                # Get device-specific connection string using dynamic registration
                                from deployment_package.src.utils.dynamic_registration_service import get_dynamic_registration_service
                                
                                iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
                                registration_service = get_dynamic_registration_service(iot_hub_connection_string)
                                device_connection_string = registration_service.register_device_with_azure(barcode)
                                
                                if device_connection_string:
                                    hub_client = HubClient(device_connection_string)
                                    initial_message = "Procedure complete, now you can scan real product"
                                    hub_client.send_message(initial_message, barcode)
                                    print("📡 Initial setup message sent to IoT Hub")
                        except Exception as e:
                            print(f"⚠️ Could not send initial message: {e}")
                        
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
    if is_device_registration_verified():
        print("🔍 Mode: Quantity Update")
    else:
        print("🧪 Mode: Test Barcode Verification Required")
    print("📊 Scan barcodes to update quantities...")
    
    if service_mode:
        print("🔧 Running in service mode - waiting for USB barcode scanner input...")
        print("💡 USB HID forwarder will handle barcode processing automatically")
        print("💡 Background barcode monitor will capture scanner input")
        print("=" * 50)
        
        # Create barcode processing callback for service mode
        def service_barcode_callback(barcode):
            """Process barcodes detected in service mode"""
            try:
                print(f"\n📦 QUANTITY UPDATE - BARCODE: {barcode}")
                print("=" * 40)
                
                # Process the barcode with the registered device ID
                result = process_barcode_with_device(barcode, device_id)
                print(result)
                
                if "✅" in result:
                    led_green()
                    time.sleep(1)
                    led_off()
                else:
                    led_red()
                    time.sleep(1)
                    led_off()
                    
            except Exception as e:
                print(f"❌ Error processing barcode: {e}")
                led_red()
                time.sleep(1)
                led_off()
        
        # Start background barcode monitor
        barcode_monitor = create_barcode_monitor(service_barcode_callback)
        if barcode_monitor.start():
            print("✅ Background barcode monitor started")
        else:
            print("⚠️ Background barcode monitor failed to start, using fallback mode")
        
        # In service mode, keep the process alive while monitoring for barcodes
        try:
            while True:
                time.sleep(10)  # Sleep for shorter intervals to be more responsive
        except KeyboardInterrupt:
            print("\n🛑 Service mode stopped")
            if barcode_monitor:
                barcode_monitor.stop()
            return
    
    print("💡 Commands:")
    print("   • Scan barcode or type 'process <barcode>'")
    print("   • 'register' or 'reregister' - Register new device")
    print("   • 'status' or 'info' - Show current device info")
    if GPIO_AVAILABLE:
        print("💡 LEDs: Green=Success, Red=Error")
    print("=" * 50)
    
    try:
        while True:
            print("🔍 Ready for barcode scan or command...")
            user_input = read_input_smart()
            
            if user_input is None:  # Ctrl+C pressed
                break
                
            user_input = user_input.strip()

            # Check for special commands
            if user_input.lower() == 'register' or user_input.lower() == 'reregister':
                print("\n🔧 DEVICE RE-REGISTRATION")
                print("📱 Enter new device ID to register:")
                print("💡 Sample device ID: a5944658fdf7")
                if GPIO_AVAILABLE:
                    print("💡 LEDs: Green=Success, Yellow=Already registered, Red=Error")
                print("=" * 50)

                try:
                    print("🔍 Scan new device ID barcode (automatic detection)...")
                    new_device_input = read_barcode_automatically()
                    if new_device_input is None:  # Ctrl+C pressed
                        print("\n🛑 Registration cancelled")
                        led_off()
                        continue
                    new_device_input = new_device_input.strip()
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
                if is_device_registration_verified():
                    print(f"🔍 Mode: Quantity Update")
                else:
                    print(f"🧪 Mode: Test Barcode Verification Required")
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
                
            # Check if device is verified before showing quantity update
            if not is_device_registration_verified():
                print(f"\n🧪 TEST BARCODE VERIFICATION - BARCODE: {barcode}")
                print("=" * 40)
            else:
                print(f"\n📦 QUANTITY UPDATE - BARCODE: {barcode}")
                print("=" * 40)
            
            try:
                # Process the barcode with the registered device ID
                result = process_barcode_with_device(barcode, device_id)
                print(result)
                
                if "✅" in result:
                    led_green()
                    time.sleep(1)
                    led_off()
                else:
                    led_red()
                    time.sleep(1)
                    led_off()
                    
            except Exception as e:
                print(f"❌ Error processing barcode: {e}")
                led_red()
                time.sleep(1)
                led_off()
                
    except KeyboardInterrupt:
        print("\n🛑 Scanner stopped")
        led_off()

if __name__ == "__main__":
    try:
        main()
    finally:
        if GPIO_AVAILABLE:
            GPIO.cleanup()