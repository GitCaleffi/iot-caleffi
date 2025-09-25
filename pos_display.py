#!/usr/bin/env python3
"""
POS Display Terminal - Shows received barcodes in real-time
Run this in a separate terminal window to see barcodes appear
"""

import os
import time
import subprocess
import threading
from datetime import datetime

def clear_screen():
    os.system('clear')

def display_header():
    clear_screen()
    print("🖥️  POS TERMINAL DISPLAY")
    print("=" * 60)
    print("📱 Waiting for barcode scans...")
    print("🕒 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    print()

def monitor_clipboard():
    """Monitor clipboard for new barcodes"""
    last_clipboard = ""
    
    while True:
        try:
            # Check clipboard content
            result = subprocess.run(['xclip', '-o'], capture_output=True, text=True, timeout=1)
            current_clipboard = result.stdout.strip()
            
            if current_clipboard != last_clipboard and current_clipboard and len(current_clipboard) >= 8:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"📋 [{timestamp}] CLIPBOARD BARCODE: {current_clipboard}")
                print("   " + "=" * 50)
                last_clipboard = current_clipboard
                
        except Exception:
            pass
        time.sleep(0.5)

def monitor_file():
    """Monitor file for new barcodes"""
    pos_file = '/tmp/pos_output.txt'
    last_content = ""
    
    while True:
        try:
            if os.path.exists(pos_file):
                with open(pos_file, 'r') as f:
                    current_content = f.read().strip()
                
                if current_content != last_content and current_content and len(current_content) >= 8:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"📄 [{timestamp}] FILE BARCODE: {current_content}")
                    print("   " + "=" * 50)
                    last_content = current_content
                    
        except Exception:
            pass
        time.sleep(0.5)

def monitor_keyboard_input():
    """Monitor for direct keyboard input (simulated POS input)"""
    print("⌨️  Also monitoring direct keyboard input...")
    print("   Type barcodes here to simulate POS input:")
    print()
    
    while True:
        try:
            barcode_input = input().strip()
            if barcode_input and len(barcode_input) >= 8:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"⌨️  [{timestamp}] KEYBOARD INPUT: {barcode_input}")
                print("   " + "=" * 50)
        except KeyboardInterrupt:
            break
        except EOFError:
            break

def main():
    display_header()
    
    print("🔍 Monitoring multiple POS input methods:")
    print("   📋 Clipboard (xclip)")
    print("   📄 File (/tmp/pos_output.txt)")
    print("   ⌨️  Direct keyboard input")
    print()
    print("🚀 Ready! Scan barcodes now...")
    print("=" * 60)
    print()
    
    # Start monitoring threads
    clipboard_thread = threading.Thread(target=monitor_clipboard, daemon=True)
    file_thread = threading.Thread(target=monitor_file, daemon=True)
    
    clipboard_thread.start()
    file_thread.start()
    
    try:
        # Monitor keyboard input in main thread
        monitor_keyboard_input()
    except KeyboardInterrupt:
        print("\n\n🛑 POS Display stopped")

if __name__ == "__main__":
    main()
