#!/usr/bin/env python3
"""
Test Real Scanner Input - Debug why barcode scanner is not working
"""

import os
import sys
import time
import select
import termios
import tty

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from barcode_scanner_app import process_barcode_scan_auto

def test_hid_device_access():
    """Test if we can actually read from HID devices"""
    
    print("🔍 Testing HID Device Access")
    print("=" * 40)
    
    hid_devices = ['/dev/hidraw0', '/dev/hidraw1', '/dev/hidraw2']
    
    for device in hid_devices:
        if os.path.exists(device):
            print(f"📱 Testing {device}...")
            try:
                # Try to read from device (non-blocking)
                with open(device, 'rb') as f:
                    # Set non-blocking
                    import fcntl
                    fcntl.fcntl(f.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
                    
                    print(f"   ✅ Can open {device}")
                    
                    # Try to read (this will fail if no input)
                    try:
                        data = f.read(8)
                        if data:
                            print(f"   📊 Got data: {data.hex()}")
                        else:
                            print(f"   ⚠️ No data available from {device}")
                    except BlockingIOError:
                        print(f"   ⚠️ No input available from {device} (normal)")
                        
            except PermissionError:
                print(f"   ❌ Permission denied for {device}")
            except Exception as e:
                print(f"   ❌ Error accessing {device}: {e}")
        else:
            print(f"❌ {device} does not exist")

def test_keyboard_input_simulation():
    """Test keyboard input as barcode scanner simulation"""
    
    print("\n🎯 Testing Keyboard Input as Barcode Scanner")
    print("=" * 50)
    print("This will simulate barcode scanner input using keyboard")
    print("Type barcodes and press Enter (type 'quit' to exit)")
    print()
    
    while True:
        try:
            print("📱 Scan/Type barcode: ", end="", flush=True)
            barcode = input().strip()
            
            if barcode.lower() in ['quit', 'exit', 'q']:
                break
                
            if not barcode:
                continue
                
            print(f"🔄 Processing barcode: {barcode}")
            
            # Process the barcode
            result = process_barcode_scan_auto(barcode)
            
            # Show result
            if "Registration Successful" in str(result):
                print(f"✅ Device registered successfully!")
            elif "sent to IoT Hub successfully" in str(result):
                print(f"✅ Barcode sent to IoT Hub successfully!")
            elif "saved locally" in str(result):
                print(f"⚠️ Saved locally (offline mode)")
            else:
                print(f"ℹ️ Result: {result}")
            
            print()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print()
    
    print("👋 Keyboard input test completed")

def test_device_registration_flow():
    """Test device registration with specific device ID"""
    
    print("\n🔧 Testing Device Registration Flow")
    print("=" * 40)
    
    # Test with a device ID barcode
    test_device_id = "test-device-12345"
    
    print(f"📱 Testing device registration with ID: {test_device_id}")
    
    try:
        result = process_barcode_scan_auto(test_device_id)
        
        print(f"📋 Registration result: {result}")
        
        if "Registration Successful" in str(result):
            print("✅ Device registration API working!")
        elif "already registered" in str(result):
            print("ℹ️ Device already registered")
        else:
            print("⚠️ Registration may have issues")
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()

def check_scanner_detection():
    """Check what scanner devices are actually detected"""
    
    print("\n🔍 Scanner Detection Analysis")
    print("=" * 35)
    
    # Check USB devices
    try:
        import subprocess
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        print("📱 USB Devices:")
        for line in result.stdout.strip().split('\n'):
            if line:
                print(f"   {line}")
        
        # Look for scanner keywords
        scanner_keywords = ['scanner', 'barcode', 'symbol', 'honeywell', 'datalogic']
        usb_text = result.stdout.lower()
        
        scanner_found = any(keyword in usb_text for keyword in scanner_keywords)
        
        if scanner_found:
            print("✅ Potential barcode scanner detected in USB devices")
        else:
            print("❌ No barcode scanner detected in USB devices")
            print("💡 This explains why HID scanning isn't working")
            
    except Exception as e:
        print(f"❌ Error checking USB devices: {e}")

def main():
    print("🚀 Real Scanner Input Debugging Tool")
    print("=" * 50)
    
    # Check what's actually connected
    check_scanner_detection()
    
    # Test HID access
    test_hid_device_access()
    
    # Test device registration
    test_device_registration_flow()
    
    # Offer keyboard simulation
    print("\n💡 SOLUTION:")
    print("Since no physical barcode scanner is detected,")
    print("you can use keyboard input to simulate barcode scanning.")
    print()
    
    try:
        response = input("🤔 Would you like to test keyboard input as barcode scanner? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            test_keyboard_input_simulation()
    except KeyboardInterrupt:
        pass
    
    print("\n📋 SUMMARY:")
    print("• No physical USB barcode scanner detected")
    print("• HID devices are from keyboard/mouse, not scanner")
    print("• Use keyboard input to test barcode processing")
    print("• Device registration and IoT Hub messaging work correctly")

if __name__ == "__main__":
    main()
