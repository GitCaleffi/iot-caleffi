#!/usr/bin/env python3
"""Auto-connect Pi to live server on boot"""

import requests
import socket
import time
import subprocess

def get_pi_info():
    """Get Pi device info"""
    try:
        # Get MAC address
        result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                              capture_output=True, text=True)
        mac = result.stdout.strip() if result.returncode == 0 else "unknown"
        
        # Get IP
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        
        return {
            "device_id": f"pi-{mac.replace(':', '')[-8:]}",
            "mac_address": mac,
            "ip_address": ip,
            "hostname": hostname,
            "device_type": "raspberry_pi_auto"
        }
    except Exception as e:
        print(f"Error getting Pi info: {e}")
        return None

def register_with_server():
    """Auto-register Pi with live server"""
    pi_info = get_pi_info()
    if not pi_info:
        return False
    
    servers = [
        "https://iot.caleffionline.it",
        "http://192.168.1.100:7860"  # Add your server IP
    ]
    
    for server_url in servers:
        try:
            print(f"🔄 Connecting to {server_url}...")
            response = requests.post(
                f"{server_url}/api/pi-auto-register",
                json=pi_info,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Connected to {server_url}")
                return True
                
        except Exception as e:
            print(f"❌ Failed to connect to {server_url}: {e}")
    
    return False

if __name__ == "__main__":
    print("🚀 Auto-connecting Pi to server...")
    
    # Wait for network
    time.sleep(10)
    
    # Try to register
    if register_with_server():
        print("✅ Pi auto-registered with server")
        # Start main app
        subprocess.run(["/home/Geektech/src/iot-caleffi/venv310/bin/python3", 
                       "barcode_scanner_app.py", "--cli"])
    else:
        print("❌ Could not connect to server")
        time.sleep(30)  # Wait and retry
