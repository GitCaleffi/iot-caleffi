#!/usr/bin/env python3
"""
Test script to verify POS forwarding functionality
"""

import sys
import os
sys.path.append('/var/www/html/abhimanyu/barcode_scanner_clean/src')

from utils.usb_hid_forwarder import get_hid_forwarder
import subprocess
import time

def test_pos_forwarding():
    """Test POS forwarding with sample barcodes"""
    print("🧪 Testing POS forwarding functionality...")
    
    # Get HID forwarder instance
    forwarder = get_hid_forwarder()
    
    # Test barcodes
    test_barcodes = [
        "8906044234994",  # Real barcode from your logs
        "1234567890123",  # Test EAN-13
        "12345678",       # Test EAN-8
    ]
    
    for i, barcode in enumerate(test_barcodes, 1):
        print(f"\n📦 Test {i}: Forwarding barcode {barcode}")
        
        # Clear clipboard first
        try:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=b'', timeout=2)
        except:
            pass
        
        # Forward barcode
        success = forwarder.forward_barcode(barcode)
        
        if success:
            print(f"✅ Forwarding reported success")
            
            # Check if barcode is in clipboard
            try:
                result = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], 
                                      capture_output=True, text=True, timeout=2)
                clipboard_content = result.stdout.strip()
                
                if clipboard_content == barcode:
                    print(f"✅ POS forwarding working! Barcode {barcode} found in clipboard")
                elif clipboard_content:
                    print(f"⚠️  Clipboard contains: '{clipboard_content}' (expected: '{barcode}')")
                else:
                    print(f"⚠️  Clipboard is empty")
                    
            except Exception as e:
                print(f"❌ Could not check clipboard: {e}")
        else:
            print(f"❌ Forwarding failed")
        
        time.sleep(1)

def test_clipboard_tools():
    """Test if clipboard tools are available"""
    print("\n🔧 Testing clipboard tools availability...")
    
    tools = ['xclip', 'xsel']
    available_tools = []
    
    for tool in tools:
        try:
            result = subprocess.run(['which', tool], capture_output=True, timeout=2)
            if result.returncode == 0:
                print(f"✅ {tool} is available")
                available_tools.append(tool)
            else:
                print(f"❌ {tool} is not available")
        except:
            print(f"❌ {tool} check failed")
    
    return available_tools

if __name__ == "__main__":
    print("🚀 POS Forwarding Test Suite")
    print("=" * 50)
    
    # Test clipboard tools
    available_tools = test_clipboard_tools()
    
    if not available_tools:
        print("\n❌ No clipboard tools available. Installing xclip...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'xclip'], check=True)
            print("✅ xclip installed successfully")
        except:
            print("❌ Failed to install xclip. POS forwarding may not work.")
    
    # Test POS forwarding
    test_pos_forwarding()
    
    print("\n🎉 Test completed!")
