#!/usr/bin/env python3
"""
POS Visual Display - Shows barcodes on screen for USB-C connected POS
"""

import tkinter as tk
from tkinter import font
import threading
import time
import os
from pathlib import Path

class POSVisualDisplay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("POS Barcode Display")
        self.root.configure(bg='black')
        
        # Make window large and prominent
        self.root.geometry("800x600")
        self.root.attributes('-topmost', True)  # Always on top
        
        # Setup display
        self.setup_display()
        
        # Monitor for barcodes
        self.monitor_barcodes()
        
        # Auto-position window
        self.center_window()
    
    def setup_display(self):
        """Setup the visual display"""
        # Title
        title_font = font.Font(family="Arial", size=24, weight="bold")
        self.title_label = tk.Label(
            self.root,
            text="🏪 CALEFFI POS DISPLAY",
            font=title_font,
            fg='cyan',
            bg='black'
        )
        self.title_label.pack(pady=20)
        
        # Barcode display - Very large
        barcode_font = font.Font(family="Courier", size=48, weight="bold")
        self.barcode_label = tk.Label(
            self.root,
            text="Ready for scan...",
            font=barcode_font,
            fg='lime',
            bg='black',
            wraplength=700,
            justify='center'
        )
        self.barcode_label.pack(expand=True, fill='both', padx=20)
        
        # Status
        status_font = font.Font(family="Arial", size=18)
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
            text="This window shows barcodes from your scanner • Press ESC to close",
            font=instruction_font,
            fg='gray',
            bg='black'
        )
        self.instruction_label.pack(side=tk.BOTTOM, pady=10)
        
        # Bind escape key
        self.root.bind('<Escape>', self.close_app)
        self.root.focus_set()
    
    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def display_barcode(self, barcode):
        """Display barcode with visual effects"""
        self.barcode_label.config(text=barcode, fg='lime')
        self.status_label.config(
            text=f"✅ SCANNED: {time.strftime('%H:%M:%S')} | Product: {barcode}",
            fg='lightgreen'
        )
        
        # Flash effect
        self.root.configure(bg='darkgreen')
        self.barcode_label.configure(bg='darkgreen')
        self.root.after(300, self.reset_colors)
        
        # Beep sound (if available)
        try:
            os.system('echo -e "\\a"')  # System beep
        except:
            pass
        
        # Auto-clear after 10 seconds
        self.root.after(10000, self.clear_display)
        
        print(f"📺 POS Display: {barcode}")
    
    def reset_colors(self):
        """Reset background colors"""
        self.root.configure(bg='black')
        self.barcode_label.configure(bg='black')
    
    def clear_display(self):
        """Clear the display"""
        self.barcode_label.config(text="Ready for scan...", fg='lime')
        self.status_label.config(text="Waiting for barcode scan...", fg='yellow')
    
    def monitor_barcodes(self):
        """Monitor for new barcodes"""
        def check_files():
            last_barcode = ""
            last_check_time = 0
            
            while True:
                try:
                    # Check multiple sources for barcodes
                    barcode_sources = [
                        '/tmp/pos_barcode.txt',
                        '/tmp/latest_barcode.txt',
                        '/tmp/current_barcode.txt'
                    ]
                    
                    for file_path in barcode_sources:
                        if Path(file_path).exists():
                            try:
                                stat = os.stat(file_path)
                                if stat.st_mtime > last_check_time:
                                    with open(file_path, 'r') as f:
                                        content = f.read().strip()
                                        if content and ':' in content:
                                            barcode = content.split(':', 1)[1].strip()
                                            if barcode and len(barcode) > 5 and barcode != last_barcode:
                                                last_barcode = barcode
                                                last_check_time = stat.st_mtime
                                                self.root.after(0, lambda b=barcode: self.display_barcode(b))
                                                break
                            except:
                                pass
                    
                    time.sleep(0.5)
                except:
                    time.sleep(1)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=check_files, daemon=True)
        monitor_thread.start()
    
    def close_app(self, event=None):
        """Close the application"""
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Run the display"""
        print("📺 Starting POS Visual Display...")
        print("🖥️ Barcode display window opened")
        print("📱 Scanned barcodes will appear in large text")
        print("⌨️ Press ESC in the window to close")
        self.root.mainloop()

if __name__ == "__main__":
    display = POSVisualDisplay()
    display.run()
