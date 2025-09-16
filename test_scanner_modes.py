#!/usr/bin/env python3
"""
Test different barcode scanner modes and configurations
"""
import sys
import os
import time
import subprocess

def test_basic_input():
    """Test if scanner works as basic keyboard input"""
    print("🧪 Test 1: Basic Keyboard Input")
    print("=" * 40)
    print("📱 Scan a barcode now (should appear as you type)")
    print("Then press Enter:")
    
    try:
        result = input(">>> ")
        if result.strip():
            print(f"✅ SUCCESS: Got '{result}'")
            return True
        else:
            print("❌ No input received")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_scanner_connection():
    """Test if scanner is physically connected"""
    print("\n🧪 Test 2: Physical Connection Check")
    print("=" * 40)
    
    # Check USB devices before and after
    print("📱 Current USB devices:")
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'keyboard' in line.lower() or 'scanner' in line.lower() or 'barcode' in line.lower():
                print(f"  🎯 {line}")
            else:
                print(f"     {line}")
    except Exception as e:
        print(f"Error checking USB: {e}")
    
    print("\n💡 Unplug and reconnect your scanner, then press Enter...")
    input()
    
    print("📱 USB devices after reconnection:")
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        print(result.stdout)
    except Exception as e:
        print(f"Error checking USB: {e}")

def test_event_devices():
    """Test input event devices"""
    print("\n🧪 Test 3: Input Event Monitoring")
    print("=" * 40)
    
    # List current input devices
    input_devices = []
    for i in range(20):
        event_path = f'/dev/input/event{i}'
        if os.path.exists(event_path):
            input_devices.append(event_path)
    
    print(f"📱 Found {len(input_devices)} input event devices")
    
    if input_devices:
        print("💡 Try scanning while monitoring events...")
        print("Press Ctrl+C to stop monitoring")
        
        try:
            # Monitor the first few event devices
            for device in input_devices[:3]:
                print(f"Checking {device}...")
                try:
                    result = subprocess.run(['timeout', '2', 'cat', device], 
                                          capture_output=True)
                    if result.returncode == 124:  # timeout
                        print(f"  {device}: No activity detected")
                    else:
                        print(f"  {device}: Activity detected!")
                except Exception as e:
                    print(f"  {device}: Error - {e}")
        except KeyboardInterrupt:
            print("Monitoring stopped")

def scanner_configuration_guide():
    """Provide scanner configuration guidance"""
    print("\n📋 Scanner Configuration Guide")
    print("=" * 40)
    print("If your scanner isn't working, try these steps:")
    print()
    print("1. 🔧 Scanner Mode Configuration:")
    print("   • Look for a mode switch on your scanner")
    print("   • Try different modes: HID, Keyboard, Serial")
    print("   • Some scanners need configuration barcodes")
    print()
    print("2. 📱 Common Scanner Types:")
    print("   • USB HID Mode: Acts like mouse/keyboard")
    print("   • Keyboard Emulation: Types like keyboard")
    print("   • Serial Mode: Requires special drivers")
    print()
    print("3. 🔍 Testing Methods:")
    print("   • Open a text editor (like notepad)")
    print("   • Scan a barcode - does text appear?")
    print("   • If yes: Scanner works in keyboard mode")
    print("   • If no: Check scanner configuration")
    print()
    print("4. 🛠️ Configuration Barcodes:")
    print("   • Many scanners use configuration barcodes")
    print("   • Look for 'Enable Keyboard Mode' barcode")
    print("   • Check scanner manual or manufacturer website")

def main():
    print("🔍 Barcode Scanner Troubleshooting Tool")
    print("=" * 50)
    
    # Test 1: Basic input
    basic_works = test_basic_input()
    
    if basic_works:
        print("\n🎉 Your scanner works in keyboard mode!")
        print("You can use the keyboard_mode_scanner.py for scanning")
        return
    
    # Test 2: Connection check
    test_scanner_connection()
    
    # Test 3: Event monitoring
    test_event_devices()
    
    # Configuration guide
    scanner_configuration_guide()
    
    print("\n" + "=" * 50)
    print("📋 TROUBLESHOOTING SUMMARY")
    print("=" * 50)
    print("If scanner still doesn't work:")
    print("1. Check scanner manual for keyboard mode setup")
    print("2. Try different USB ports")
    print("3. Look for configuration barcodes online")
    print("4. Test scanner on another computer")

if __name__ == "__main__":
    main()
