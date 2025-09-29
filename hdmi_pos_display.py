#!/usr/bin/env python3
"""
HDMI POS Display - Shows barcodes on external HDMI screen
"""

import tkinter as tk
from tkinter import font
import json
import time
import threading
import subprocess
from pathlib import Path

class HDMIPOSDisplay:
    def __init__(self, display_name=None):
        self.display_name = display_name
        self.root = tk.Tk()
        self.root.title("HDMI POS Display")
        self.root.configure(bg='black')
        
        # Position on external display if specified
        if display_name:
            try:
                # Get display geometry
                result = subprocess.run(['xrandr'], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if display_name in line and ' connected' in line:
                            # Extract position (e.g., "1920x1080+1366+0")
                            parts = line.split()
                            for part in parts:
                                if 'x' in part and '+' in part:
                                    geometry = part.split('+')
                                    if len(geometry) >= 3:
                                        width_height = geometry[0]
                                        x_pos = geometry[1]
                                        y_pos = geometry[2]
                                        self.root.geometry(f"{width_height}+{x_pos}+{y_pos}")
                                        break
            except:
                pass
        
        # Make fullscreen on external display
        self.root.attributes('-fullscreen', True)
        self.root.bind('<Escape>', self.exit_fullscreen)
        self.root.bind('<F11>', self.toggle_fullscreen)
        
        # Create display elements
        self.setup_display()
        
        # Start barcode monitoring
        self.monitor_barcodes()
    
    def setup_display(self):
        """Setup the HDMI display interface"""
        # Store name
        store_font = font.Font(family="Arial", size=20, weight="bold")
        self.store_label = tk.Label(
            self.root, 
            text="CALEFFI POS SYSTEM", 
            font=store_font,
            fg='white', 
            bg='black'
        )
        self.store_label.pack(pady=10)
        
        # Title
        title_font = font.Font(family="Arial", size=32, weight="bold")
        self.title_label = tk.Label(
            self.root, 
            text="BARCODE DISPLAY", 
            font=title_font,
            fg='cyan', 
            bg='black'
        )
        self.title_label.pack(pady=20)
        
        # Barcode display - Large and prominent
        barcode_font = font.Font(family="Courier", size=64, weight="bold")
        self.barcode_label = tk.Label(
            self.root,
            text="Ready for scan...",
            font=barcode_font,
            fg='lime',
            bg='black',
            wraplength=1200,
            justify='center'
        )
        self.barcode_label.pack(expand=True, fill='both')
        
        # Status display
        status_font = font.Font(family="Arial", size=24)
        self.status_label = tk.Label(
            self.root,
            text="Waiting for barcode scan...",
            font=status_font,
            fg='yellow',
            bg='black'
        )
        self.status_label.pack(pady=30)
        
        # Instructions
        instruction_font = font.Font(family="Arial", size=14)
        self.instruction_label = tk.Label(
            self.root,
            text="ESC: Exit Fullscreen | F11: Toggle Fullscreen",
            font=instruction_font,
            fg='gray',
            bg='black'
        )
        self.instruction_label.pack(side=tk.BOTTOM, pady=10)
    
    def display_barcode(self, barcode):
        """Display a barcode on HDMI screen"""
        self.barcode_label.config(text=barcode, fg='lime')
        self.status_label.config(
            text=f"✅ SCANNED: {time.strftime('%H:%M:%S')} | Product: {barcode}",
            fg='lightgreen'
        )
        
        # Flash effect - more dramatic for external display
        self.root.configure(bg='darkgreen')
        self.barcode_label.configure(bg='darkgreen')
        self.root.after(300, self.reset_colors)
        
        # Auto-clear after 8 seconds (longer for external viewing)
        self.root.after(8000, self.clear_display)
    
    def reset_colors(self):
        """Reset background colors"""
        self.root.configure(bg='black')
        self.barcode_label.configure(bg='black')
    
    def clear_display(self):
        """Clear the display"""
        self.barcode_label.config(text="Ready for scan...", fg='lime')
        self.status_label.config(text="Waiting for barcode scan...", fg='yellow')
    
    def monitor_barcodes(self):
        """Monitor for new barcodes from scanner"""
        def check_files():
            last_barcode = ""
            while True:
                try:
                    # Check multiple barcode file sources
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
                                        if barcode and len(barcode) > 5 and barcode != last_barcode:
                                            last_barcode = barcode
                                            self.root.after(0, lambda b=barcode: self.display_barcode(b))
                                            print(f"📺 HDMI Display: {barcode}")
                                            break
                            except:
                                pass
                    
                    time.sleep(0.5)  # Check more frequently
                except:
                    time.sleep(1)
        
        # Start monitoring in background thread
        monitor_thread = threading.Thread(target=check_files, daemon=True)
        monitor_thread.start()
    
    def exit_fullscreen(self, event=None):
        """Exit fullscreen mode"""
        self.root.attributes('-fullscreen', False)
    
    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode"""
        current = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current)
    
    def run(self):
        """Run the HDMI display"""
        print(f"🖥️ HDMI POS Display running on {self.display_name or 'default display'}")
        print("📺 Barcode scanner output will appear on external screen")
        self.root.mainloop()

if __name__ == "__main__":
    import sys
    display_name = sys.argv[1] if len(sys.argv) > 1 else None
    print("🖥️ Starting HDMI POS Display...")
    display = HDMIPOSDisplay(display_name)
    display.run()
