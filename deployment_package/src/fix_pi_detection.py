#!/usr/bin/env python3
"""Fix Pi detection - force recognition as Raspberry Pi"""

import os

def fix_pi_detection():
    # Check if we're actually on a Pi
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read()
            if 'BCM' in cpuinfo or 'ARM' in cpuinfo:
                print("✅ This IS a Raspberry Pi")
                
                # Force Pi recognition
                os.environ['FORCE_PI_MODE'] = '1'
                
                # Test LED access
                try:
                    with open('/sys/class/leds/ACT/brightness', 'w') as led:
                        led.write('1')
                    print("✅ LED access works")
                    
                    # Run the scanner directly
                    import subprocess
                    subprocess.run(['python3', 'system_led_scanner.py'])
                    
                except PermissionError:
                    print("❌ Need sudo for LED access")
                    print("Run: sudo python3 system_led_scanner.py")
                    
            else:
                print("❌ Not a Raspberry Pi")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_pi_detection()
