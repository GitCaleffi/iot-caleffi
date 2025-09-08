#!/usr/bin/env python3
"""
LED Test Script - Diagnose LED blinking issues on Raspberry Pi
"""

import time
import sys
import os

def test_gpio_availability():
    """Test if GPIO is available"""
    try:
        import RPi.GPIO as GPIO
        print("✅ RPi.GPIO imported successfully")
        return True
    except ImportError as e:
        print(f"❌ RPi.GPIO import failed: {e}")
        print("💡 Install with: sudo apt install python3-rpi.gpio")
        return False
    except RuntimeError as e:
        print(f"❌ GPIO runtime error: {e}")
        print("💡 Run with sudo or add user to gpio group")
        return False

def test_pi_detection():
    """Test Raspberry Pi detection"""
    print("\n🔍 Testing Pi Detection Methods:")
    
    # Method 1: Check /proc/device-tree/model
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
            print(f"📋 Device model: {model}")
            if 'raspberry pi' in model.lower():
                print("✅ Detected as Raspberry Pi via device model")
                return True
    except Exception as e:
        print(f"❌ Device model check failed: {e}")
    
    # Method 2: Check /proc/cpuinfo
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read().lower()
            if 'bcm' in cpuinfo or 'arm' in cpuinfo:
                print("✅ ARM/BCM processor detected")
                return True
    except Exception as e:
        print(f"❌ CPU info check failed: {e}")
    
    print("❌ Not detected as Raspberry Pi")
    return False

def test_gpio_permissions():
    """Test GPIO permissions"""
    print("\n🔐 Testing GPIO Permissions:")
    
    # Check if running as root
    if os.geteuid() == 0:
        print("✅ Running as root - GPIO access should work")
        return True
    
    # Check gpio group membership
    try:
        import grp
        gpio_group = grp.getgrnam('gpio')
        current_user = os.getenv('USER', 'unknown')
        
        if current_user in gpio_group.gr_mem:
            print(f"✅ User '{current_user}' is in gpio group")
            return True
        else:
            print(f"❌ User '{current_user}' not in gpio group")
            print(f"💡 Add to group: sudo usermod -a -G gpio {current_user}")
            return False
    except Exception as e:
        print(f"⚠️ Could not check gpio group: {e}")
        return False

def test_led_hardware(pin, color):
    """Test individual LED on specific GPIO pin"""
    try:
        import RPi.GPIO as GPIO
        
        print(f"\n🔴 Testing {color} LED on GPIO {pin}")
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(pin, GPIO.OUT)
        
        # Blink test
        for i in range(3):
            print(f"  Blink {i+1}/3...")
            GPIO.output(pin, GPIO.HIGH)
            time.sleep(0.5)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(0.5)
        
        GPIO.cleanup()
        print(f"✅ {color} LED test completed")
        return True
        
    except Exception as e:
        print(f"❌ {color} LED test failed: {e}")
        return False

def main():
    """Main LED diagnostic function"""
    print("🔴🟡🟢 LED Diagnostic Tool for Raspberry Pi")
    print("=" * 50)
    
    # Test 1: GPIO availability
    if not test_gpio_availability():
        print("\n❌ CRITICAL: GPIO not available - cannot continue")
        return False
    
    # Test 2: Pi detection
    is_pi = test_pi_detection()
    if not is_pi:
        print("\n⚠️ WARNING: Not detected as Pi - LEDs may not work")
    
    # Test 3: Permissions
    has_permissions = test_gpio_permissions()
    if not has_permissions:
        print("\n❌ CRITICAL: No GPIO permissions")
        return False
    
    # Test 4: Hardware LEDs
    led_pins = {
        'Red': 17,
        'Yellow': 18, 
        'Green': 24
    }
    
    print(f"\n🔧 Testing LED Hardware (Connect LEDs to these pins):")
    for color, pin in led_pins.items():
        print(f"  {color}: GPIO {pin} (Physical pin {get_physical_pin(pin)})")
    
    input("\nPress Enter when LEDs are connected...")
    
    all_leds_work = True
    for color, pin in led_pins.items():
        if not test_led_hardware(pin, color):
            all_leds_work = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_leds_work:
        print("✅ ALL TESTS PASSED - LEDs should work!")
    else:
        print("❌ SOME TESTS FAILED - Check connections and permissions")
    
    return all_leds_work

def get_physical_pin(gpio_pin):
    """Convert GPIO pin to physical pin number"""
    gpio_to_physical = {
        17: 11, 18: 12, 24: 18, 23: 16, 25: 22
    }
    return gpio_to_physical.get(gpio_pin, "Unknown")

if __name__ == "__main__":
    main()
