#!/usr/bin/env python3
"""
Watch the continuous internet monitoring in action
"""

import subprocess
import time
import sys

def watch_logs():
    """Watch the barcode scanner service logs for internet monitoring"""
    print("🔍 Watching barcode scanner service for internet monitoring...")
    print("💡 You should see LED status changes every 5 seconds")
    print("🔴 To test: Disconnect WiFi/Ethernet and watch for 'Status changed' to 'error'")
    print("🟢 Then reconnect and watch for 'Status changed' to 'online'")
    print("⏹️  Press Ctrl+C to stop watching")
    print("-" * 60)
    
    try:
        # Follow the service logs in real-time
        process = subprocess.Popen([
            'journalctl', '-u', 'barcode-scanner.service', '-f', '--since', 'now'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        for line in process.stdout:
            # Filter for relevant log messages
            if any(keyword in line for keyword in ['Status changed', 'LED', 'Internet', 'connectivity', 'disconnected', 'connected']):
                print(line.strip())
                
    except KeyboardInterrupt:
        print("\n🛑 Stopped watching logs")
        process.terminate()

if __name__ == "__main__":
    watch_logs()
