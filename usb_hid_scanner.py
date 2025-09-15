#!/usr/bin/env python3
"""
USB HID Barcode Scanner with Basic Processing
Integrates HID scanner functionality with minimal dependencies
"""

import os
import sys
import time
import threading
import queue
from datetime import datetime

# Add src directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

# HID key mapping for normal keys
hid_key_map = {
    4: 'a', 5: 'b', 6: 'c', 7: 'd', 8: 'e', 9: 'f', 10: 'g', 11: 'h', 12: 'i', 13: 'j',
    14: 'k', 15: 'l', 16: 'm', 17: 'n', 18: 'o', 19: 'p', 20: 'q', 21: 'r', 22: 's',
    23: 't', 24: 'u', 25: 'v', 26: 'w', 27: 'x', 28: 'y', 29: 'z',
    30: '1', 31: '2', 32: '3', 33: '4', 34: '5', 35: '6', 36: '7', 37: '8', 38: '9', 39: '0',
    40: 'ENTER', 44: ' ', 45: '-', 46: '=', 47: '[', 48: ']', 49: '\\',
    51: ';', 52: "'", 53: '`', 54: ',', 55: '.', 56: '/'
}

# HID key mapping for shifted characters
hid_shift_map = {
    4: 'A', 5: 'B', 6: 'C', 7: 'D', 8: 'E', 9: 'F', 10: 'G', 11: 'H', 12: 'I', 13: 'J',
    14: 'K', 15: 'L', 16: 'M', 17: 'N', 18: 'O', 19: 'P', 20: 'Q', 21: 'R', 22: 'S',
    23: 'T', 24: 'U', 25: 'V', 26: 'W', 27: 'X', 28: 'Y', 29: 'Z',
    30: '!', 31: '@', 32: '#', 33: '$', 34: '%', 35: '^', 36: '&', 37: '*', 38: '(', 39: ')',
    44: ' ', 45: '_', 46: '+', 47: '{', 48: '}', 49: '|', 51: ':', 52: '"', 53: '~', 54: '<',
    55: '>', 56: '?'
}

# Global variables
SCANNER_RUNNING = False
barcode_queue = queue.Queue()
scanned_barcodes_count = 0

# Try to import barcode processing functions (optional)
try:
    from barcode_scanner_app import process_barcode_scan_auto
    BARCODE_PROCESSOR_AVAILABLE = True
    print("✅ Barcode processor available - will use full processing")
except ImportError:
    BARCODE_PROCESSOR_AVAILABLE = False
    print("⚠️ Barcode processor not available - will use basic processing")

def find_hid_scanner_device():
    """Find HID barcode scanner device"""
    hid_devices = ['/dev/hidraw0', '/dev/hidraw1', '/dev/hidraw2', '/dev/hidraw3']
    
    for device_path in hid_devices:
        if os.path.exists(device_path):
            try:
                # Test if we can open the device
                with open(device_path, 'rb') as test_fp:
                    print(f"✅ Found HID device: {device_path}")
                    return device_path
            except PermissionError:
                print(f"⚠️ Permission denied for {device_path}. May need sudo.")
                return device_path  # Return it anyway, let caller handle permission
            except Exception as e:
                print(f"Cannot access {device_path}: {e}")
                continue
    
    print("❌ No HID scanner device found")
    return None

def hid_scanner_worker():
    """HID scanner monitoring worker thread"""
    global SCANNER_RUNNING, scanned_barcodes_count
    
    print("🔌 Starting HID scanner detection...")
    
    while SCANNER_RUNNING:
        try:
            device_path = find_hid_scanner_device()
            if not device_path:
                print("📱 No HID scanner found, retrying in 5 seconds...")
                time.sleep(5)
                continue
            
            print(f"📱 Reading from HID device: {device_path}")
            print("🔍 Scan a barcode now...")
            
            with open(device_path, 'rb') as fp:
                barcode = ''
                shift = False
                
                while SCANNER_RUNNING:
                    try:
                        buffer = fp.read(8)
                        if not buffer:
                            continue
                            
                        for b in buffer:
                            code = b if isinstance(b, int) else ord(b)
                            
                            if code == 0:
                                continue
                            
                            if code == 40:  # ENTER key - end of barcode
                                if barcode.strip():
                                    scanned_barcodes_count += 1
                                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    
                                    print("=" * 50)
                                    print(f"📦 Scanned Barcode: {barcode}")
                                    print(f"🕒 Time: {timestamp}")
                                    print(f"📊 Scan Count: {scanned_barcodes_count}")
                                    print("=" * 50)
                                    
                                    # Add to queue for processing
                                    barcode_queue.put(barcode)
                                    barcode = ''
                            elif code == 2:  # SHIFT key
                                shift = True
                            else:
                                if shift:
                                    barcode += hid_shift_map.get(code, '')
                                    shift = False
                                else:
                                    barcode += hid_key_map.get(code, '')
                                    
                    except Exception as e:
                        print(f"Error reading HID data: {e}")
                        break
                        
        except PermissionError:
            print(f"❌ Permission denied for {device_path}. Try running with sudo.")
            time.sleep(10)
        except Exception as e:
            print(f"HID scanner error: {e}")
            time.sleep(5)

def basic_barcode_processor(barcode):
    """Basic barcode processing without IoT dependencies"""
    print(f"🔄 Processing barcode: {barcode}")
    print(f"📏 Length: {len(barcode)} characters")
    
    # Basic validation
    if len(barcode) < 6:
        print("⚠️ Barcode too short (less than 6 characters)")
        return False
    
    if len(barcode) > 20:
        print("⚠️ Barcode too long (more than 20 characters)")
        return False
    
    # Here you could add basic barcode format validation
    # For now, just accept any alphanumeric barcode
    print(f"✅ Barcode {barcode} validated successfully!")
    
    # You could save to a local file, database, or send to an API here
    # For now, just log it
    with open('scanned_barcodes.log', 'a') as f:
        f.write(f"{datetime.now().isoformat()},{barcode}\n")
    
    print(f"💾 Barcode saved to scanned_barcodes.log")
    return True

def barcode_processor_worker():
    """Process barcodes from the queue"""
    global SCANNER_RUNNING
    
    print("🔄 Starting barcode processor...")
    
    while SCANNER_RUNNING:
        try:
            # Get barcode from queue (blocks until available)
            barcode = barcode_queue.get(timeout=1)
            
            if barcode:
                if BARCODE_PROCESSOR_AVAILABLE:
                    # Use full barcode processing from main app
                    try:
                        result = process_barcode_scan_auto(barcode)
                        print(f"✅ Full processing result: {result}")
                    except Exception as e:
                        print(f"❌ Full processing failed: {e}")
                        print("🔄 Falling back to basic processing")
                        basic_barcode_processor(barcode)
                else:
                    # Use basic processing
                    basic_barcode_processor(barcode)
                
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Error processing barcode: {e}")

def main():
    global SCANNER_RUNNING
    
    print("🚀 Starting USB HID Barcode Scanner...")
    print("📱 Connect your USB barcode scanner and start scanning!")
    print("🔍 The system will automatically detect and process barcodes")
    
    if BARCODE_PROCESSOR_AVAILABLE:
        print("✅ Full barcode processing enabled (IoT Hub + API)")
    else:
        print("⚠️ Basic processing mode (local logging only)")
    
    print("=" * 60)
    
    SCANNER_RUNNING = True
    
    # Start HID scanner monitoring thread
    scanner_thread = threading.Thread(target=hid_scanner_worker, daemon=True)
    scanner_thread.start()
    
    # Start barcode processor thread
    processor_thread = threading.Thread(target=barcode_processor_worker, daemon=True)
    processor_thread.start()
    
    print("✅ HID scanner service started successfully")
    print("📱 Ready for automatic barcode scanning...")
    print("Press Ctrl+C to stop")
    
    try:
        # Keep main thread alive
        while SCANNER_RUNNING:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping HID scanner service...")
        SCANNER_RUNNING = False
        print("🛑 HID scanner service stopped")

if __name__ == "__main__":
    main()
