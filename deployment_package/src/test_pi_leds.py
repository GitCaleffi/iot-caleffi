#!/usr/bin/env python3
"""
Simple Raspberry Pi LED Test
Connect LEDs to: Red=GPIO17, Yellow=GPIO18, Green=GPIO24
"""

import RPi.GPIO as GPIO
import time

# LED pins
RED = 17
YELLOW = 18
GREEN = 24

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RED, GPIO.OUT)
    GPIO.setup(YELLOW, GPIO.OUT)
    GPIO.setup(GREEN, GPIO.OUT)

def blink_led(pin, times=3):
    for i in range(times):
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(pin, GPIO.LOW)
        time.sleep(0.5)

def test_leds():
    print("🔴 Testing Red LED (GPIO 17)...")
    blink_led(RED, 3)
    
    print("🟡 Testing Yellow LED (GPIO 18)...")
    blink_led(YELLOW, 3)
    
    print("🟢 Testing Green LED (GPIO 24)...")
    blink_led(GREEN, 3)
    
    print("🌈 All LEDs together...")
    GPIO.output(RED, GPIO.HIGH)
    GPIO.output(YELLOW, GPIO.HIGH)
    GPIO.output(GREEN, GPIO.HIGH)
    time.sleep(2)
    
    GPIO.output(RED, GPIO.LOW)
    GPIO.output(YELLOW, GPIO.LOW)
    GPIO.output(GREEN, GPIO.LOW)

if __name__ == "__main__":
    try:
        setup()
        test_leds()
        print("✅ LED test complete!")
    finally:
        GPIO.cleanup()
