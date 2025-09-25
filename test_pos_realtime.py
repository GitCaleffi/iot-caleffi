#!/usr/bin/env python3
"""
Real-Time POS Testing Script
Test barcode forwarding to different screens/terminals
"""

import sys
import os
import time
import threading
import subprocess
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from utils.usb_hid_forwarder import get_hid_forwarder

def monitor_pos_output():
    """Monitor POS output in real-time"""
    print("🖥️  POS OUTPUT MONITOR")
    print("=" * 50)
    
    # Monitor clipboard
    def monitor_clipboard():
        print("📋 Monitoring clipboard for barcodes...")
        last_clipboard = ""
        while True:
            try:
                # Check clipboard content
                result = subprocess.run(['xclip', '-o'], capture_output=True, text=True, timeout=1)
                current_clipboard = result.stdout.strip()
                
                if current_clipboard != last_clipboard and current_clipboard:
                    print(f"📋 CLIPBOARD: {current_clipboard}")
                    last_clipboard = current_clipboard
                    
            except Exception:
                pass
            time.sleep(0.5)
    
    # Monitor file output
    def monitor_file():
        print("📄 Monitoring /tmp/pos_output.txt for barcodes...")
        last_content = ""
        while True:
            try:
                if os.path.exists('/tmp/pos_output.txt'):
                    with open('/tmp/pos_output.txt', 'r') as f:
                        current_content = f.read().strip()
                    
                    if current_content != last_content and current_content:
                        print(f"📄 FILE: {current_content}")
                        last_content = current_content
                        
            except Exception:
                pass
            time.sleep(0.5)
    
    # Start monitoring threads
    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    file_thread = threading.Thread(target=monitor_file, daemon=True)
    
    clipboard_thread.start()
    file_thread.start()
    
    return clipboard_thread, file_thread

def test_barcode_forwarding(barcode):
    """Test forwarding a specific barcode"""
    print(f"\n🚀 TESTING BARCODE FORWARDING: {barcode}")
    print("=" * 50)
    
    try:
        hid_forwarder = get_hid_forwarder()
        
        print(f"📱 Available POS methods: {hid_forwarder.available_methods}")
        
        # Test forwarding
        success = hid_forwarder.forward_barcode(barcode)
        
        if success:
            print(f"✅ Barcode {barcode} forwarded successfully!")
        else:
            print(f"❌ Failed to forward barcode {barcode}")
            
        return success
        
    except Exception as e:
        print(f"❌ Error testing barcode forwarding: {e}")
        return False

def main():
    print("🎯 REAL-TIME POS TESTING")
    print("=" * 50)
    print("This will test barcode forwarding to POS systems")
    print("Open another terminal to see the output!")
    print("")
    
    # Start monitoring
    monitor_threads = monitor_pos_output()
    
    # Test the specific barcode
    test_barcode = "8906044234994"
    
    print(f"\n⏰ Starting test in 3 seconds...")
    time.sleep(3)
    
    # Test forwarding
    success = test_barcode_forwarding(test_barcode)
    
    if success:
        print(f"\n✅ SUCCESS! Check the output above for your barcode: {test_barcode}")
        print("📋 If using clipboard method, the barcode should appear in clipboard")
        print("📄 If using file method, check /tmp/pos_output.txt")
    else:
        print(f"\n❌ FAILED! Barcode forwarding did not work")
    
    print("\n🔄 Testing again in 5 seconds...")
    time.sleep(5)
    
    # Test again
    test_barcode_forwarding(test_barcode)
    
    print("\n🛑 Test completed. Check the output above!")

if __name__ == "__main__":
    main()
