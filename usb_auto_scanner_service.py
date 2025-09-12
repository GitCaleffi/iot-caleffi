
import sys
import os
import time
import threading
import signal
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir / 'src'))

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    print("Installing evdev...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True

class AutomaticUSBScannerService:
    def __init__(self):
        self.running = False
        self.scanner_device = None
        self.barcode_buffer = ""
        self.last_scan_time = 0
        self.scan_timeout = 2
        self.device_check_interval = 5  # Check for new devices every 5 seconds
        self.scan_count = 0
        
    def find_usb_scanner(self):
        """Find USB barcode scanner automatically"""
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            for device in devices:
                device_name = device.name.lower()
                
                # Check for barcode scanner keywords
                scanner_keywords = [
                    'barcode', 'scanner', 'honeywell', 'symbol', 
                    'datalogic', 'zebra', 'usb barcode', 'hid'
                ]
                
                if any(keyword in device_name for keyword in scanner_keywords):
                    return device
                
                # Check for keyboard-like devices with numeric capabilities
                try:
                    caps = device.capabilities()
                    if ecodes.EV_KEY in caps:
                        keys = caps[ecodes.EV_KEY]
                        
                        # Must have numbers and Enter
                        has_numbers = any(key in keys for key in [
                            ecodes.KEY_0, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4,
                            ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9
                        ])
                        has_enter = ecodes.KEY_ENTER in keys
                        
                        if has_numbers and has_enter and len(keys) < 50:
                            return device
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error finding USB scanner: {e}")
            return None
    
    def key_to_char(self, key_code):
        """Convert key code to character"""
        key_map = {
            ecodes.KEY_0: '0', ecodes.KEY_1: '1', ecodes.KEY_2: '2', ecodes.KEY_3: '3',
            ecodes.KEY_4: '4', ecodes.KEY_5: '5', ecodes.KEY_6: '6', ecodes.KEY_7: '7',
            ecodes.KEY_8: '8', ecodes.KEY_9: '9',
            ecodes.KEY_A: 'a', ecodes.KEY_B: 'b', ecodes.KEY_C: 'c', ecodes.KEY_D: 'd',
            ecodes.KEY_E: 'e', ecodes.KEY_F: 'f', ecodes.KEY_G: 'g', ecodes.KEY_H: 'h',
            ecodes.KEY_I: 'i', ecodes.KEY_J: 'j', ecodes.KEY_K: 'k', ecodes.KEY_L: 'l',
            ecodes.KEY_M: 'm', ecodes.KEY_N: 'n', ecodes.KEY_O: 'o', ecodes.KEY_P: 'p',
            ecodes.KEY_Q: 'q', ecodes.KEY_R: 'r', ecodes.KEY_S: 's', ecodes.KEY_T: 't',
            ecodes.KEY_U: 'u', ecodes.KEY_V: 'v', ecodes.KEY_W: 'w', ecodes.KEY_X: 'x',
            ecodes.KEY_Y: 'y', ecodes.KEY_Z: 'z'
        }
        return key_map.get(key_code, '')
    
    def process_barcode(self, barcode):
        """Process barcode automatically using existing system"""
        try:
            from barcode_scanner_app import process_barcode_scan
            
            self.scan_count += 1
            print(f"\n📱 USB Scan #{self.scan_count}: {barcode}")
            
            # Process using existing logic
            result = process_barcode_scan(barcode)
            
            # Extract key information from result
            if "Registration Successful" in str(result):
                print(f"✅ Device registered automatically")
            elif "sent to IoT Hub successfully" in str(result):
                print(f"✅ Barcode sent to IoT Hub")
            elif "saved locally" in str(result):
                print(f"⚠️  Saved locally (offline mode)")
            else:
                print(f"ℹ️  Result: {result}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error processing barcode: {e}")
            return False
    
    def monitor_scanner(self):
        """Monitor USB scanner for input"""
        print(f"🔍 Monitoring: {self.scanner_device.name}")
        print("📱 Ready for automatic barcode scanning...")
        
        try:
            for event in self.scanner_device.read_loop():
                if not self.running:
                    break
                
                if event.type == ecodes.EV_KEY and event.value == 1:
                    current_time = time.time()
                    
                    if event.code == ecodes.KEY_ENTER:
                        if self.barcode_buffer and len(self.barcode_buffer) >= 6:
                            barcode = self.barcode_buffer.strip()
                            self.process_barcode(barcode)
                        
                        self.barcode_buffer = ""
                        self.last_scan_time = current_time
                        
                    else:
                        char = self.key_to_char(event.code)
                        if char:
                            if current_time - self.last_scan_time > self.scan_timeout:
                                self.barcode_buffer = ""
                            
                            self.barcode_buffer += char
                            self.last_scan_time = current_time
        
        except Exception as e:
            print(f"❌ Scanner monitoring error: {e}")
    
    def device_detection_loop(self):
        """Continuously check for USB scanner devices"""
        while self.running:
            try:
                if not self.scanner_device:
                    print("🔌 Checking for USB barcode scanner...")
                    new_device = self.find_usb_scanner()
                    
                    if new_device:
                        self.scanner_device = new_device
                        print(f"✅ USB Scanner connected: {new_device.name}")
                        
                        # Start monitoring in separate thread
                        monitor_thread = threading.Thread(target=self.monitor_scanner, daemon=True)
                        monitor_thread.start()
                    else:
                        print("⏳ No USB scanner found, checking again in 5 seconds...")
                
                time.sleep(self.device_check_interval)
                
            except Exception as e:
                print(f"❌ Device detection error: {e}")
                time.sleep(self.device_check_interval)
    
    def start_service(self):
        """Start the automatic USB scanner service"""
        print("=" * 60)
        print("🚀 AUTOMATIC USB SCANNER SERVICE")
        print("=" * 60)
        print("This service will automatically:")
        print("• Detect USB barcode scanners")
        print("• Register devices on first scan")
        print("• Send all barcodes to IoT Hub")
        print("• Work without manual intervention")
        print("=" * 60)
        
        self.running = True
        
        # Set up signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        try:
            # Start device detection loop
            self.device_detection_loop()
            
        except KeyboardInterrupt:
            print("\n🛑 Service stopped by user")
        except Exception as e:
            print(f"❌ Service error: {e}")
        finally:
            self.running = False
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.running = False
    
    def stop_service(self):
        """Stop the service"""
        self.running = False

def main():
    """Main function"""
    service = AutomaticUSBScannerService()
    
    try:
        service.start_service()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down service...")
    finally:
        service.stop_service()

if __name__ == "__main__":
    main()
