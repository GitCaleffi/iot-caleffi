#!/usr/bin/env python3
"""
USB Keyboard Barcode Scanner Input Handler
Captures USB barcode scanner input (which acts as keyboard) and processes automatically
"""

import sys
import os
import time
import threading
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir / 'src'))

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True
except ImportError:
    print("❌ evdev not available - installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "evdev"])
    import evdev
    from evdev import InputDevice, categorize, ecodes
    EVDEV_AVAILABLE = True

class USBKeyboardBarcodeScanner:
    def __init__(self):
        self.running = False
        self.scanner_device = None
        self.barcode_buffer = ""
        self.last_scan_time = 0
        self.scan_timeout = 2  # 2 seconds timeout for barcode completion
        
    def find_barcode_scanner_keyboard(self):
        """Find USB barcode scanner that acts as keyboard"""
        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            print(f"🔍 Found {len(devices)} input devices:")
            
            potential_scanners = []
            
            for device in devices:
                device_name = device.name.lower()
                print(f"  - {device.name} ({device.path})")
                
                # Check for common barcode scanner names
                scanner_keywords = [
                    'barcode', 'scanner', 'honeywell', 'symbol', 
                    'datalogic', 'zebra', 'usb barcode', 'hid', 'usb'
                ]
                
                if any(keyword in device_name for keyword in scanner_keywords):
                    print(f"    ✅ Matches scanner keyword")
                    potential_scanners.append((device, "keyword_match"))
                    continue
                
                # Check if device has keyboard capabilities
                try:
                    caps = device.capabilities()
                    if ecodes.EV_KEY in caps:
                        keys = caps[ecodes.EV_KEY]
                        
                        # Must have numeric keys and Enter
                        has_numbers = any(key in keys for key in [
                            ecodes.KEY_0, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4,
                            ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9
                        ])
                        has_enter = ecodes.KEY_ENTER in keys
                        
                        if has_numbers and has_enter:
                            print(f"    ✅ Has keyboard capabilities (keys: {len(keys)})")
                            potential_scanners.append((device, f"keyboard_like_{len(keys)}_keys"))
                except Exception as e:
                    print(f"    ⚠️  Could not check capabilities: {e}")
            
            # Return the best match
            if potential_scanners:
                # Prefer keyword matches first
                for device, reason in potential_scanners:
                    if "keyword_match" in reason:
                        print(f"✅ Selected scanner: {device.name} (reason: {reason})")
                        return device
                
                # Then prefer devices with fewer keys (more likely to be scanners)
                potential_scanners.sort(key=lambda x: int(x[1].split('_')[-2]) if 'keyboard_like' in x[1] else 999)
                device, reason = potential_scanners[0]
                print(f"✅ Selected scanner: {device.name} (reason: {reason})")
                return device
            
            return None
            
        except Exception as e:
            print(f"❌ Error finding barcode scanner: {e}")
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
        """Process completed barcode using existing barcode_scanner_app logic"""
        try:
            from barcode_scanner_app import process_barcode_scan
            
            print(f"\n📱 USB Scanner Input: {barcode}")
            print("🔄 Processing barcode...")
            
            # Use the existing process_barcode_scan function
            result = process_barcode_scan(barcode)
            
            print(f"✅ Result: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Error processing barcode: {e}")
            return f"Error: {e}"
    
    def monitor_scanner_input(self):
        """Monitor USB scanner for keyboard input"""
        if not self.scanner_device:
            print("❌ No scanner device available")
            return
        
        print(f"🔍 Monitoring USB scanner: {self.scanner_device.name}")
        print("📱 Ready to scan barcodes...")
        
        try:
            for event in self.scanner_device.read_loop():
                if not self.running:
                    break
                
                # Only process key press events
                if event.type == ecodes.EV_KEY and event.value == 1:  # Key press
                    current_time = time.time()
                    
                    # Check for Enter key (end of barcode)
                    if event.code == ecodes.KEY_ENTER:
                        if self.barcode_buffer and len(self.barcode_buffer) >= 6:
                            barcode = self.barcode_buffer.strip()
                            print(f"\n🎯 Complete barcode scanned: {barcode}")
                            
                            # Process the barcode
                            self.process_barcode(barcode)
                            
                        # Reset buffer
                        self.barcode_buffer = ""
                        self.last_scan_time = current_time
                        
                    else:
                        # Add character to buffer
                        char = self.key_to_char(event.code)
                        if char:
                            # Reset buffer if too much time passed (new scan)
                            if current_time - self.last_scan_time > self.scan_timeout:
                                self.barcode_buffer = ""
                            
                            self.barcode_buffer += char
                            self.last_scan_time = current_time
                            
                            # Show progress
                            if len(self.barcode_buffer) % 3 == 0:  # Every 3 characters
                                print(f"📝 Scanning: {self.barcode_buffer}...")
        
        except Exception as e:
            print(f"❌ Scanner monitoring error: {e}")
    
    def simulation_mode(self):
        """Run in simulation mode for testing without physical scanner"""
        print("\n🎮 SIMULATION MODE ACTIVATED")
        print("=" * 60)
        print("You can test barcode processing by typing barcodes manually")
        print("Type 'quit' or 'exit' to stop")
        print("=" * 60)
        
        test_barcodes = [
            "7079fa7ab32e",    # Device ID for registration
            "5901234123457",   # EAN-13 product barcode
            "8978456598745",   # Another EAN-13 barcode
            "1234567890123"    # Test EAN-13 barcode
        ]
        
        print("💡 Suggested test barcodes:")
        for i, barcode in enumerate(test_barcodes, 1):
            print(f"  {i}. {barcode}")
        print()
        
        while self.running:
            try:
                user_input = input("📱 Enter barcode (or 'quit'): ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    break
                
                if user_input:
                    print(f"🔄 Processing barcode: {user_input}")
                    result = self.process_barcode(user_input)
                    print("-" * 40)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("🛑 Simulation mode stopped")

    def start(self):
        """Start USB keyboard barcode scanner"""
        print("=" * 60)
        print("🚀 USB KEYBOARD BARCODE SCANNER")
        print("=" * 60)
        
        # Find scanner device
        print("🔌 Looking for USB barcode scanner...")
        self.scanner_device = self.find_barcode_scanner_keyboard()
        
        if not self.scanner_device:
            print("\n❌ No USB barcode scanner found")
            print("\n🎮 Would you like to run in simulation mode? (y/n)")
            
            try:
                choice = input("Choice: ").strip().lower()
                if choice in ['y', 'yes', '1']:
                    self.running = True
                    self.simulation_mode()
                    return True
                else:
                    print("Please connect your USB barcode scanner and try again")
                    return False
            except KeyboardInterrupt:
                print("\n🛑 Cancelled by user")
                return False
        
        print(f"✅ Found scanner: {self.scanner_device.name}")
        print(f"📍 Device path: {self.scanner_device.path}")
        
        # Start monitoring
        self.running = True
        
        try:
            self.monitor_scanner_input()
        except KeyboardInterrupt:
            print("\n🛑 Scanner stopped by user")
        except Exception as e:
            print(f"❌ Scanner error: {e}")
        finally:
            self.running = False
        
        return True
    
    def stop(self):
        """Stop the scanner"""
        self.running = False

def main():
    """Main function to run USB keyboard barcode scanner"""
    scanner = USBKeyboardBarcodeScanner()
    
    try:
        scanner.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    finally:
        scanner.stop()

if __name__ == "__main__":
    main()
