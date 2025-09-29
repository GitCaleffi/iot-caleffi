#!/usr/bin/env python3
"""
Mobile Screen POS Integration
Configure mobile screen to display barcodes
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def detect_mobile_screen():
    """Detect connected mobile screen/display"""
    print("🔍 Detecting Mobile Screen...")
    print("=" * 40)
    
    # Check for display devices
    displays = []
    
    # Method 1: Check HDMI/Display outputs
    try:
        result = subprocess.run(['xrandr'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if ' connected' in line and 'primary' not in line:
                    display_name = line.split()[0]
                    displays.append(('HDMI/Display', display_name))
                    print(f"📺 Found display: {display_name}")
    except:
        pass
    
    # Method 2: Check USB displays
    try:
        result = subprocess.run(['lsusb'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['display', 'screen', 'monitor', 'stmicro']):
                    device_id = line.split()[5] if len(line.split()) > 5 else "Unknown"
                    displays.append(('USB', device_id))
                    print(f"🔌 Found USB device: {line.strip()}")
    except:
        pass
    
    # Method 3: Check framebuffer devices
    fb_devices = list(Path('/dev').glob('fb*'))
    for fb in fb_devices:
        displays.append(('Framebuffer', str(fb)))
        print(f"🖼️ Found framebuffer: {fb}")
    
    return displays

def create_mobile_pos_display():
    """Create mobile POS display application"""
    
    display_app = '''#!/usr/bin/env python3
"""
Mobile POS Display - Shows barcodes on mobile screen
"""

import tkinter as tk
from tkinter import font
import json
import time
import threading
from pathlib import Path

class MobilePOSDisplay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("POS Display")
        self.root.configure(bg='black')
        
        # Make fullscreen
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', self.exit_fullscreen)
        
        # Create display elements
        self.setup_display()
        
        # Start barcode monitoring
        self.monitor_barcodes()
    
    def setup_display(self):
        """Setup the display interface"""
        # Title
        title_font = font.Font(family="Arial", size=24, weight="bold")
        self.title_label = tk.Label(
            self.root, 
            text="POS DISPLAY", 
            font=title_font,
            fg='white', 
            bg='black'
        )
        self.title_label.pack(pady=20)
        
        # Barcode display
        barcode_font = font.Font(family="Courier", size=48, weight="bold")
        self.barcode_label = tk.Label(
            self.root,
            text="Ready for barcode...",
            font=barcode_font,
            fg='lime',
            bg='black',
            wraplength=800
        )
        self.barcode_label.pack(expand=True)
        
        # Status display
        status_font = font.Font(family="Arial", size=16)
        self.status_label = tk.Label(
            self.root,
            text="Waiting for barcode scan...",
            font=status_font,
            fg='yellow',
            bg='black'
        )
        self.status_label.pack(pady=20)
        
        # Instructions
        instruction_font = font.Font(family="Arial", size=12)
        self.instruction_label = tk.Label(
            self.root,
            text="Press ESC to exit fullscreen",
            font=instruction_font,
            fg='gray',
            bg='black'
        )
        self.instruction_label.pack(side=tk.BOTTOM, pady=10)
    
    def display_barcode(self, barcode):
        """Display a barcode on screen"""
        self.barcode_label.config(text=barcode, fg='lime')
        self.status_label.config(text=f"Scanned: {time.strftime('%H:%M:%S')}")
        
        # Flash effect
        self.root.configure(bg='darkgreen')
        self.root.after(200, lambda: self.root.configure(bg='black'))
        
        # Auto-clear after 5 seconds
        self.root.after(5000, self.clear_display)
    
    def clear_display(self):
        """Clear the display"""
        self.barcode_label.config(text="Ready for barcode...", fg='lime')
        self.status_label.config(text="Waiting for barcode scan...")
    
    def monitor_barcodes(self):
        """Monitor for new barcodes"""
        def check_files():
            while True:
                try:
                    # Check for barcode files
                    barcode_files = [
                        '/tmp/pos_barcode.txt',
                        '/tmp/latest_barcode.txt',
                        '/tmp/current_barcode.txt'
                    ]
                    
                    for file_path in barcode_files:
                        if Path(file_path).exists():
                            try:
                                with open(file_path, 'r') as f:
                                    content = f.read().strip()
                                    if content and ':' in content:
                                        # Extract barcode from "timestamp: barcode" format
                                        barcode = content.split(':', 1)[1].strip()
                                        if barcode and len(barcode) > 5:
                                            self.root.after(0, lambda b=barcode: self.display_barcode(b))
                                            break
                            except:
                                pass
                    
                    time.sleep(1)
                except:
                    time.sleep(1)
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=check_files, daemon=True)
        monitor_thread.start()
    
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.root.attributes('-fullscreen', False)
    
    def run(self):
        """Run the display"""
        self.root.mainloop()

if __name__ == "__main__":
    print("🖥️ Starting Mobile POS Display...")
    display = MobilePOSDisplay()
    display.run()
'''
    
    with open('mobile_pos_display.py', 'w') as f:
        f.write(display_app)
    
    print("✅ Created mobile_pos_display.py")
    return 'mobile_pos_display.py'

def test_mobile_display():
    """Test the mobile display"""
    print("\n🧪 Testing Mobile Display...")
    
    # Create test barcode file
    test_barcode = f"TEST_MOBILE_{int(time.time())}"
    test_content = f"{time.strftime('%Y-%m-%d %H:%M:%S')}: {test_barcode}"
    
    try:
        with open('/tmp/pos_barcode.txt', 'w') as f:
            f.write(test_content)
        
        print(f"✅ Created test barcode: {test_barcode}")
        print("📱 The mobile display should show this barcode!")
        return True
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("📱 Mobile Screen POS Setup")
    print("=" * 40)
    
    # Detect mobile screen
    displays = detect_mobile_screen()
    
    if displays:
        print(f"\n✅ Found {len(displays)} display device(s)")
        for display_type, device in displays:
            print(f"   📺 {display_type}: {device}")
    else:
        print("\n⚠️ No additional displays detected")
        print("💡 Make sure your mobile screen is connected")
    
    # Create mobile display app
    display_file = create_mobile_pos_display()
    
    # Test the display
    test_mobile_display()
    
    print(f"\n🎯 Mobile POS Display Setup Complete!")
    print(f"📁 Created: {display_file}")
    
    print(f"\n📋 Next Steps:")
    print(f"1. Connect your mobile screen to Raspberry Pi")
    print(f"2. Copy {display_file} to your Raspberry Pi")
    print(f"3. On Raspberry Pi, run: python3 {display_file}")
    print(f"4. Run your barcode scanner: python3 keyboard_scanner.py")
    print(f"5. Scan barcodes - they'll appear on the mobile screen!")
    
    print(f"\n💻 Commands for Raspberry Pi:")
    print(f"   # Terminal 1 - Start mobile display")
    print(f"   python3 {display_file}")
    print(f"   ")
    print(f"   # Terminal 2 - Start barcode scanner")
    print(f"   python3 keyboard_scanner.py")

if __name__ == "__main__":
    main()
