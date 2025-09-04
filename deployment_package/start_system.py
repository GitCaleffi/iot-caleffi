#!/usr/bin/env python3

import subprocess
import time
import sys
import os

def start_server():
    """Start the live server"""
    print("🚀 Starting Live Server...")
    server_process = subprocess.Popen([
        sys.executable, 'live_server.py'
    ], cwd=os.getcwd())
    return server_process

def start_scanner():
    """Start the scanner client"""
    print("📱 Starting Scanner Client...")
    # Update server URL to localhost
    with open('plug_play_scanner.py', 'r') as f:
        content = f.read()
    
    content = content.replace(
        '"server_url": "https://your-live-server.com/api"',
        '"server_url": "http://localhost:3000/api"'
    )
    
    with open('plug_play_scanner_local.py', 'w') as f:
        f.write(content)
    
    time.sleep(3)  # Wait for server to start
    
    scanner_process = subprocess.Popen([
        sys.executable, 'plug_play_scanner_local.py'
    ])
    return scanner_process

def main():
    print("🔍 Starting Plug & Play Barcode Scanner System")
    print("=" * 50)
    
    try:
        # Start server
        server = start_server()
        
        # Start scanner
        scanner = start_scanner()
        
        print("\n✅ System Started Successfully!")
        print("📊 Dashboard: http://localhost:3000")
        print("🔌 API: http://localhost:3000/api")
        print("\nPress Ctrl+C to stop...")
        
        # Wait for processes
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down system...")
        try:
            server.terminate()
            scanner.terminate()
        except:
            pass
        print("✅ System stopped")

if __name__ == "__main__":
    main()
