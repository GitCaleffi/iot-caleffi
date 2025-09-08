#!/usr/bin/env python3
"""
LED Simulator for Non-Raspberry Pi Systems
Provides visual LED feedback in terminal when GPIO is not available
"""

import time
import threading
import sys
import os

class LEDSimulator:
    """Simulate LED behavior on non-Pi systems with terminal output"""
    
    def __init__(self):
        self.gpio_available = False
        self.led_pins = {
            'red': 17,
            'yellow': 18, 
            'green': 24
        }
        self.led_states = {
            'red': False,
            'yellow': False,
            'green': False
        }
        
        # Try to detect if we're on a Pi
        self.is_pi = self._detect_raspberry_pi()
        
        if self.is_pi:
            try:
                import RPi.GPIO as GPIO
                self.GPIO = GPIO
                self._setup_gpio()
                self.gpio_available = True
                print("🔴🟡🟢 Real GPIO LED controller initialized")
            except Exception as e:
                print(f"⚠️ GPIO setup failed: {e}")
                self.gpio_available = False
        else:
            print("💡 LED Simulator initialized (not on Raspberry Pi)")
            print("🖥️ LED status will be shown in terminal")
    
    def _detect_raspberry_pi(self):
        """Detect if running on Raspberry Pi"""
        try:
            # Check device model
            if os.path.exists('/proc/device-tree/model'):
                with open('/proc/device-tree/model', 'r') as f:
                    if 'raspberry pi' in f.read().lower():
                        return True
            
            # Check CPU info
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read().lower()
                if 'bcm' in cpuinfo and 'arm' in cpuinfo:
                    return True
                    
        except Exception:
            pass
        
        return False
    
    def _setup_gpio(self):
        """Setup GPIO pins for real Pi"""
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)
        
        for color, pin in self.led_pins.items():
            self.GPIO.setup(pin, self.GPIO.OUT)
            self.GPIO.output(pin, self.GPIO.LOW)
    
    def _print_led_status(self, color, action):
        """Print LED status to terminal"""
        color_emojis = {
            'red': '🔴',
            'yellow': '🟡', 
            'green': '🟢'
        }
        
        emoji = color_emojis.get(color, '💡')
        timestamp = time.strftime('%H:%M:%S')
        
        if action == 'blink':
            print(f"[{timestamp}] {emoji} {color.upper()} LED BLINK")
        elif action == 'on':
            print(f"[{timestamp}] {emoji} {color.upper()} LED ON")
            self.led_states[color] = True
        elif action == 'off':
            print(f"[{timestamp}] ⚫ {color.upper()} LED OFF")
            self.led_states[color] = False
        
        # Show current LED status bar
        status_bar = ""
        for led_color in ['red', 'yellow', 'green']:
            if self.led_states[led_color]:
                status_bar += color_emojis[led_color]
            else:
                status_bar += "⚫"
        
        print(f"LED Status: {status_bar}")
    
    def blink_led(self, color, duration=0.5, times=1):
        """Blink LED - works on both Pi and simulator"""
        if self.gpio_available:
            # Real GPIO blinking
            try:
                pin = self.led_pins.get(color)
                if pin:
                    for _ in range(times):
                        self.GPIO.output(pin, self.GPIO.HIGH)
                        time.sleep(duration)
                        self.GPIO.output(pin, self.GPIO.LOW)
                        time.sleep(0.1)
            except Exception as e:
                print(f"❌ GPIO blink error: {e}")
        else:
            # Simulated blinking
            for i in range(times):
                self._print_led_status(color, 'on')
                time.sleep(duration)
                self._print_led_status(color, 'off')
                if i < times - 1:  # Don't sleep after last blink
                    time.sleep(0.1)
    
    def set_led(self, color, state):
        """Set LED on/off - works on both Pi and simulator"""
        if self.gpio_available:
            # Real GPIO control
            try:
                pin = self.led_pins.get(color)
                if pin:
                    self.GPIO.output(pin, self.GPIO.HIGH if state else self.GPIO.LOW)
            except Exception as e:
                print(f"❌ GPIO control error: {e}")
        else:
            # Simulated control
            action = 'on' if state else 'off'
            self._print_led_status(color, action)
    
    def test_all_leds(self):
        """Test all LEDs in sequence"""
        print("🔍 Testing all LEDs...")
        
        for color in ['red', 'yellow', 'green']:
            print(f"Testing {color} LED...")
            self.blink_led(color, 0.5, 3)
            time.sleep(0.5)
        
        print("✅ LED test complete")
    
    def cleanup(self):
        """Clean up resources"""
        if self.gpio_available:
            try:
                self.GPIO.cleanup()
                print("🔌 GPIO cleanup completed")
            except Exception as e:
                print(f"❌ GPIO cleanup error: {e}")
        else:
            print("🔌 LED simulator cleanup completed")

def main():
    """Test the LED simulator"""
    print("🔴🟡🟢 LED Simulator Test")
    print("=" * 30)
    
    led_controller = LEDSimulator()
    
    try:
        # Test individual LEDs
        print("\n1. Testing individual LEDs:")
        led_controller.blink_led('red', 0.5, 2)
        time.sleep(1)
        led_controller.blink_led('yellow', 0.5, 2)
        time.sleep(1)
        led_controller.blink_led('green', 0.5, 2)
        time.sleep(1)
        
        # Test LED states
        print("\n2. Testing LED states:")
        led_controller.set_led('red', True)
        time.sleep(1)
        led_controller.set_led('yellow', True)
        time.sleep(1)
        led_controller.set_led('green', True)
        time.sleep(1)
        
        # Turn all off
        print("\n3. Turning all LEDs off:")
        for color in ['red', 'yellow', 'green']:
            led_controller.set_led(color, False)
        
        # Test all LEDs
        print("\n4. Testing all LEDs:")
        led_controller.test_all_leds()
        
    finally:
        led_controller.cleanup()

if __name__ == "__main__":
    main()
