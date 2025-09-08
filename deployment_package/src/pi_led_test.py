#!/usr/bin/env python3
import time
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)  # Red LED
    
    for i in range(5):
        GPIO.output(17, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(17, GPIO.LOW)
        time.sleep(0.5)
        print(f"Blink {i+1}")
    
    GPIO.cleanup()
    print("✅ LED test complete")
except Exception as e:
    print(f"❌ LED test failed: {e}")
