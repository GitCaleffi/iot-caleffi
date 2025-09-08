#!/usr/bin/env python3
"""
Simple LED Test Script
Tests the LED functionality of the barcode scanner system
"""

import sys
import os
import time

# Add the src directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_leds():
    """Test LED functionality"""
    print("🔴🟡🟢 LED Test Starting...")
    print("=" * 40)
    
    try:
        # Import the LED controller from the main app
        from barcode_scanner_app import led_controller
        
        print("✅ LED Controller imported successfully")
        print(f"🔧 GPIO Available: {led_controller.gpio_available}")
        print(f"🔧 Is Raspberry Pi: {led_controller.is_pi}")
        
        print("\n1. Testing individual LED blinks:")
        print("   🔴 Red LED (3 blinks)...")
        led_controller.blink_led('red', 0.5, 3)
        time.sleep(1)
        
        print("   🟡 Yellow LED (3 blinks)...")
        led_controller.blink_led('yellow', 0.5, 3)
        time.sleep(1)
        
        print("   🟢 Green LED (3 blinks)...")
        led_controller.blink_led('green', 0.5, 3)
        time.sleep(1)
        
        print("\n2. Testing LED on/off states:")
        print("   Turning all LEDs ON...")
        led_controller.set_led('red', True)
        led_controller.set_led('yellow', True)
        led_controller.set_led('green', True)
        time.sleep(2)
        
        print("   Turning all LEDs OFF...")
        led_controller.set_led('red', False)
        led_controller.set_led('yellow', False)
        led_controller.set_led('green', False)
        time.sleep(1)
        
        print("\n3. Testing all LEDs sequence:")
        led_controller.test_all_leds()
        
        print("\n✅ All LED tests completed successfully!")
        
        if not led_controller.gpio_available:
            print("\n💡 Note: LEDs are simulated in terminal because:")
            if not led_controller.is_pi:
                print("   - This is not a Raspberry Pi (no GPIO pins)")
            else:
                print("   - GPIO is not available (permission/hardware issue)")
            print("   - On a real Pi with proper setup, LEDs would blink physically")
        
    except Exception as e:
        print(f"❌ LED test failed: {e}")
        return False
    
    return True

def main():
    """Main function"""
    success = test_leds()
    
    if success:
        print("\n🎉 LED test completed successfully!")
        exit(0)
    else:
        print("\n❌ LED test failed!")
        exit(1)

if __name__ == "__main__":
    main()
