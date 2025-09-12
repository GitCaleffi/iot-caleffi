#!/usr/bin/env python3
"""
USB Device Detection Test
Tests USB device detection logic without requiring physical scanner
"""

import sys
import os
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

def list_all_input_devices():
    """List all available input devices on the system"""
    print("=" * 60)
    print("🔍 USB INPUT DEVICE DETECTION TEST")
    print("=" * 60)
    
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        print(f"Found {len(devices)} input devices:")
        print("-" * 40)
        
        if not devices:
            print("❌ No input devices found")
            print("\nThis could mean:")
            print("• No USB devices connected")
            print("• Permission issues (try running with sudo)")
            print("• evdev not properly installed")
            return []
        
        potential_scanners = []
        
        for i, device in enumerate(devices, 1):
            print(f"\n{i}. Device: {device.name}")
            print(f"   Path: {device.path}")
            print(f"   Physical: {device.phys}")
            
            # Check device capabilities
            try:
                caps = device.capabilities()
                
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    print(f"   Keyboard keys: {len(keys)}")
                    
                    # Check for numeric keys
                    numeric_keys = [
                        ecodes.KEY_0, ecodes.KEY_1, ecodes.KEY_2, ecodes.KEY_3, ecodes.KEY_4,
                        ecodes.KEY_5, ecodes.KEY_6, ecodes.KEY_7, ecodes.KEY_8, ecodes.KEY_9
                    ]
                    has_numbers = sum(1 for key in numeric_keys if key in keys)
                    has_enter = ecodes.KEY_ENTER in keys
                    
                    print(f"   Numeric keys: {has_numbers}/10")
                    print(f"   Has Enter: {has_enter}")
                    
                    # Scanner detection logic
                    device_name = device.name.lower()
                    scanner_keywords = [
                        'barcode', 'scanner', 'honeywell', 'symbol', 
                        'datalogic', 'zebra', 'usb barcode', 'hid'
                    ]
                    
                    keyword_match = any(keyword in device_name for keyword in scanner_keywords)
                    
                    if keyword_match:
                        print("   🎯 SCANNER DETECTED: Keyword match")
                        potential_scanners.append((device, "keyword_match"))
                    elif has_numbers >= 8 and has_enter and len(keys) < 50:
                        print("   🎯 POSSIBLE SCANNER: Keyboard-like with few keys")
                        potential_scanners.append((device, "keyboard_like"))
                    elif has_numbers >= 8 and has_enter:
                        print("   ⚠️  MAYBE SCANNER: Has numeric keys but many total keys")
                        potential_scanners.append((device, "full_keyboard"))
                    else:
                        print("   ❌ Not a scanner")
                
                # Check other capabilities
                other_caps = []
                if ecodes.EV_REL in caps:
                    other_caps.append("Mouse")
                if ecodes.EV_ABS in caps:
                    other_caps.append("Touchpad/Joystick")
                if other_caps:
                    print(f"   Other: {', '.join(other_caps)}")
                    
            except Exception as e:
                print(f"   ❌ Error checking capabilities: {e}")
        
        print("\n" + "=" * 60)
        print("SCANNER DETECTION SUMMARY")
        print("=" * 60)
        
        if potential_scanners:
            print(f"Found {len(potential_scanners)} potential scanner(s):")
            for device, reason in potential_scanners:
                print(f"✅ {device.name} ({reason})")
        else:
            print("❌ No barcode scanners detected")
            
        return potential_scanners
        
    except Exception as e:
        print(f"❌ Error listing devices: {e}")
        return []

def test_keyboard_as_scanner():
    """Test if regular keyboard can work as barcode scanner"""
    print("\n" + "=" * 60)
    print("🎮 KEYBOARD AS SCANNER TEST")
    print("=" * 60)
    
    try:
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        # Find keyboard devices
        keyboards = []
        for device in devices:
            try:
                caps = device.capabilities()
                if ecodes.EV_KEY in caps:
                    keys = caps[ecodes.EV_KEY]
                    if len(keys) > 50:  # Likely a full keyboard
                        keyboards.append(device)
            except:
                continue
        
        if keyboards:
            print(f"Found {len(keyboards)} keyboard(s) that could simulate scanner:")
            for i, kb in enumerate(keyboards, 1):
                print(f"{i}. {kb.name}")
            
            print("\n💡 You can test with your regular keyboard:")
            print("1. Run the USB scanner service")
            print("2. Type barcodes followed by Enter")
            print("3. The system will process them as scanner input")
            
            return True
        else:
            print("❌ No keyboards found for testing")
            return False
            
    except Exception as e:
        print(f"❌ Error testing keyboard: {e}")
        return False

def simulate_usb_scanner_connection():
    """Simulate what happens when USB scanner is connected"""
    print("\n" + "=" * 60)
    print("🔌 USB SCANNER CONNECTION SIMULATION")
    print("=" * 60)
    
    print("When you connect a USB barcode scanner:")
    print("1. 🔌 Device appears in /dev/input/eventX")
    print("2. 🔍 Scanner service detects it automatically")
    print("3. 📱 Ready to scan barcodes")
    print("4. 🎯 First scan registers device")
    print("5. 📡 Subsequent scans sent to IoT Hub")
    
    print("\nTo test without physical scanner:")
    print("• Use mobile app (see recommendations below)")
    print("• Use regular keyboard for typing barcodes")
    print("• Use simulation mode in scanner service")

def mobile_app_recommendations():
    """Provide mobile app recommendations for barcode scanning"""
    print("\n" + "=" * 60)
    print("📱 MOBILE APP ALTERNATIVES")
    print("=" * 60)
    
    apps = [
        {
            "name": "Barcode to PC",
            "description": "Scans barcodes and sends to PC via WiFi",
            "platform": "Android/iOS",
            "features": ["WiFi connection", "Real-time scanning", "Keyboard simulation"]
        },
        {
            "name": "WiFi Barcode Scanner",
            "description": "Wireless barcode scanner for PC",
            "platform": "Android",
            "features": ["No USB needed", "Network connection", "Multiple formats"]
        },
        {
            "name": "ScanPet Barcode Scanner",
            "description": "Professional barcode scanner app",
            "platform": "Android/iOS", 
            "features": ["Batch scanning", "Export options", "Various formats"]
        },
        {
            "name": "QR & Barcode Scanner",
            "description": "Simple barcode scanner with sharing",
            "platform": "Android/iOS",
            "features": ["Share via text", "Copy to clipboard", "History"]
        }
    ]
    
    for i, app in enumerate(apps, 1):
        print(f"{i}. {app['name']} ({app['platform']})")
        print(f"   {app['description']}")
        print(f"   Features: {', '.join(app['features'])}")
        print()
    
    print("💡 RECOMMENDED SETUP:")
    print("1. Install 'Barcode to PC' on your phone")
    print("2. Connect phone and PC to same WiFi")
    print("3. App sends scanned barcodes to PC automatically")
    print("4. Configure to send to your barcode scanner service")

def create_virtual_scanner_test():
    """Create a virtual scanner for testing"""
    print("\n" + "=" * 60)
    print("🎮 VIRTUAL SCANNER TEST MODE")
    print("=" * 60)
    
    test_script = """
# Virtual Scanner Test
python3 -c "
import sys
sys.path.append('src')
from barcode_scanner_app import process_barcode_scan

# Test device registration
print('Testing device registration...')
result = process_barcode_scan('7079fa7ab32e')
print(f'Registration: {result}')

# Test barcode scanning
test_barcodes = ['5901234123457', '8978456598745', '1234567890123']
for barcode in test_barcodes:
    print(f'Testing barcode: {barcode}')
    result = process_barcode_scan(barcode)
    print(f'Result: {result}')
"
"""
    
    print("You can test the barcode processing logic directly:")
    print(test_script)
    
    return test_script

def main():
    """Main test function"""
    print("USB DEVICE DETECTION & TESTING SUITE")
    
    # Test 1: List all input devices
    potential_scanners = list_all_input_devices()
    
    # Test 2: Test keyboard as scanner
    test_keyboard_as_scanner()
    
    # Test 3: Simulate connection
    simulate_usb_scanner_connection()
    
    # Test 4: Mobile app recommendations
    mobile_app_recommendations()
    
    # Test 5: Virtual scanner test
    create_virtual_scanner_test()
    
    print("\n" + "=" * 60)
    print("🎯 TESTING RECOMMENDATIONS")
    print("=" * 60)
    print("1. Check input devices above for any potential scanners")
    print("2. Try mobile apps for wireless barcode scanning")
    print("3. Use keyboard to simulate scanner input")
    print("4. Run virtual scanner test for direct testing")

if __name__ == "__main__":
    main()
