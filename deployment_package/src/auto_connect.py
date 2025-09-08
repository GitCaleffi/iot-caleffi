#!/usr/bin/env python3
"""Auto-connect Pi to live server on boot"""

import requests
import socket
import time
import subprocess
import json
import os
from typing import List, Dict

def load_config() -> Dict:
    """Load configuration from config.json"""
    config_paths = [
        "config.json",
        "../config.json", 
        "/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/config.json"
    ]
    
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config from {config_path}: {e}")
    
    return {}

def discover_servers() -> List[str]:
    """Dynamically discover available servers"""
    servers = []
    config = load_config()
    
    # Get servers from config
    raspberry_pi_config = config.get("raspberry_pi", {})
    server_urls = raspberry_pi_config.get("server_urls", [])
    
    # Add configured servers
    for url in server_urls:
        if url not in servers:
            servers.append(url)
    
    # Add web server config if available
    web_config = config.get("web_server", {})
    if web_config:
        host = web_config.get("host", "localhost")
        port = web_config.get("port", 5000)
        
        # Try different host variations
        local_servers = [
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
            f"http://{get_local_ip()}:{port}"
        ]
        
        for server in local_servers:
            if server not in servers:
                servers.append(server)
    
    # Add common server endpoints
    common_servers = [
        "https://iot.caleffionline.it",
        "https://api2.caleffionline.it"
    ]
    
    for server in common_servers:
        if server not in servers:
            servers.append(server)
    
    print(f"🔍 Discovered {len(servers)} potential servers: {servers}")
    return servers

def get_local_ip() -> str:
    """Get local IP address dynamically"""
    try:
        # Connect to external IP to determine local IP
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

def test_server_connectivity(server_url: str) -> bool:
    """Test if server is reachable"""
    try:
        # Try a simple GET request to test connectivity
        response = requests.get(f"{server_url}/", timeout=5)
        return True
    except Exception:
        try:
            # Try the specific API endpoint
            response = requests.get(f"{server_url}/api/health", timeout=5)
            return True
        except Exception:
            return False

def get_pi_info():
    """Get Pi device info"""
    try:
        # Get MAC address from multiple sources
        mac = "unknown"
        mac_sources = [
            "/sys/class/net/eth0/address",
            "/sys/class/net/wlan0/address",
            "/sys/class/net/enp0s3/address"
        ]
        
        for mac_source in mac_sources:
            try:
                result = subprocess.run(['cat', mac_source], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    mac = result.stdout.strip()
                    break
            except Exception:
                continue
        
        # Get IP dynamically
        ip = get_local_ip()
        hostname = socket.gethostname()
        
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
    """Auto-register Pi with live server using dynamic discovery"""
    pi_info = get_pi_info()
    if not pi_info:
        return False
    
    # Discover servers dynamically
    servers = discover_servers()
    
    # Test connectivity and register with first available server
    for server_url in servers:
        try:
            print(f"🔄 Testing connectivity to {server_url}...")
            
            # Test basic connectivity first
            if not test_server_connectivity(server_url):
                print(f"❌ {server_url} not reachable")
                continue
            
            print(f"✅ {server_url} is reachable, attempting registration...")
            
            # Try registration
            response = requests.post(
                f"{server_url}/api/pi-auto-register",
                json=pi_info,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✅ Successfully registered with {server_url}")
                return True
            else:
                print(f"⚠️ Registration failed with {server_url}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ Failed to connect to {server_url}: {e}")
    
    return False

if __name__ == "__main__":
    print("🚀 Auto-connecting Pi to server with dynamic discovery...")
    
    # Wait for network
    print("⏳ Waiting for network connectivity...")
    time.sleep(5)
    
    # Try to register
    if register_with_server():
        print("✅ Pi auto-registered with server")
        # Start main app using current Python interpreter and correct path
        try:
            subprocess.run(["python3", "barcode_scanner_app.py", "--cli"])
        except Exception as e:
            print(f"Error starting barcode scanner: {e}")
    else:
        print("❌ Could not connect to any server")
        print("🔄 Will retry in 30 seconds...")
        time.sleep(30)
