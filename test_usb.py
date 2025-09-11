#!/usr/bin/env python3
"""
Simple USB Scanner Test
Tests if USB scanner input can be captured
"""

import sys
import time

print("🔌 USB Scanner Test")
print("==================")
print("")
print("This will test if your USB scanner input can be captured.")
print("Scan a barcode with your USB scanner now...")
print("The barcode should appear below:")
print("")

try:
    # Wait for input with timeout
    print("⏳ Waiting for USB scanner input (10 seconds)...")
    
    # Set a timeout for input
    import signal
    
    def timeout_handler(signum, frame):
        raise TimeoutError("No input received")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)  # 10 second timeout
    
    try:
        barcode = input("📱 Scan now: ")
        signal.alarm(0)  # Cancel timeout
        
        if barcode.strip():
            print(f"✅ SUCCESS! Captured barcode: {barcode}")
            print("🎉 Your USB scanner is working correctly!")
            
            # Test if this looks like the barcode you scanned
            if barcode == "098b581a7f38":
                print("🔍 This matches the barcode from your console output!")
        else:
            print("⚠️ Empty input received")
            
    except TimeoutError:
        print("⏰ Timeout - no input received")
        print("💡 Try scanning the barcode again")
        
except KeyboardInterrupt:
    print("\n👋 Test cancelled")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n📋 Next steps:")
print("1. If the test worked, run: ./usb_register.sh")
print("2. Or use the web interface USB Monitor controls")
print("3. Or run: python3 src/usb_auto_register.py")