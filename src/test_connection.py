#!/usr/bin/env python3
"""
Raspberry Pi Connection Test Script
-----------------------------------
This script tests the connection to your Raspberry Pi and local storage functionality.
Run this script directly to diagnose connection issues.
"""

import subprocess
import platform
import os
import socket
import time
import sys
import json

def load_config():
    """Load configuration from config.json file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading config: {str(e)}")
    return {}

def test_raspberry_pi_connection():
    """Test Raspberry Pi connection using multiple methods"""
    print("\n===== RASPBERRY PI CONNECTION TEST =====\n")
    print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Running on: {platform.system()} {platform.release()}")
    
    # Get Raspberry Pi IP from config or use defaults
    config = load_config()
    raspberry_pi_ip = None
    
    if config and 'raspberry_pi' in config:
        raspberry_pi_ip = config.get('raspberry_pi', {}).get('ip_address')
        print(f"Found Raspberry Pi IP in config: {raspberry_pi_ip}")
    
    # If not in config, check environment variable
    if not raspberry_pi_ip:
        raspberry_pi_ip = os.environ.get('RASPBERRY_PI_IP')
        if raspberry_pi_ip:
            print(f"Found Raspberry Pi IP in environment variable: {raspberry_pi_ip}")
    
    # Define test IPs - starting with the known working IP, then config/env IP if different
    test_ips = ["192.168.1.18"]
    if raspberry_pi_ip and raspberry_pi_ip not in test_ips:
        test_ips.insert(0, raspberry_pi_ip)
    
    test_ips.extend(["raspberrypi.local", "192.168.0.18"])
    
    # Check if we're running ON a Raspberry Pi
    print("\n1. Checking if we are running directly on a Raspberry Pi...")
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            print(f"✅ Device model: {model}")
            if 'raspberry pi' in model.lower():
                print("✅ This IS a Raspberry Pi device")
                return True
            else:
                print("❌ This is NOT a Raspberry Pi device")
    except Exception as e:
        print(f"❌ Not running on a Raspberry Pi: {str(e)}")
    
    # Test each IP address
    success = False
    for ip in test_ips:
        print(f"\n2. Testing connection to {ip}...")
        
        # Test ping
        print(f"   Testing ping to {ip}...")
        try:
            if platform.system().lower() == 'windows':
                ping_cmd = ['ping', '-n', '1', '-w', '1000', ip]
            else:
                ping_cmd = ['ping', '-c', '1', '-W', '1', ip]
                
            result = subprocess.run(ping_cmd, capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                print(f"   ✅ Ping successful to {ip}")
                print(f"   Response: {result.stdout.splitlines()[-1] if result.stdout else 'No output'}")
                success = True
            else:
                print(f"   ❌ Ping failed to {ip}")
                print(f"   Error: {result.stderr if result.stderr else 'No error output'}")
        except Exception as e:
            print(f"   ❌ Ping error: {str(e)}")
        
        # Test common ports
        common_ports = [22, 80, 8000, 5000]
        for port in common_ports:
            print(f"   Testing port {port} on {ip}...")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, port))
                sock.close()
                
                if result == 0:
                    print(f"   ✅ Port {port} is open on {ip}")
                    success = True
                else:
                    print(f"   ❌ Port {port} is closed on {ip}")
            except Exception as e:
                print(f"   ❌ Port {port} check error: {str(e)}")
    
    # Test MQTT connection
    print("\n3. Testing MQTT connection...")
    try:
        import paho.mqtt.client as mqtt
        client = mqtt.Client()
        client.connect("192.168.1.18", 1883, 60)
        print("✅ MQTT connection successful")
        client.disconnect()
        success = True
    except ImportError:
        print("❌ MQTT library not installed. Run: pip install paho-mqtt")
    except Exception as e:
        print(f"❌ MQTT connection error: {str(e)}")
    
    # Check local storage
    print("\n4. Testing local storage...")
    try:
        test_file = "pi_connection_test.txt"
        with open(test_file, "w") as f:
            f.write("Test data")
        
        with open(test_file, "r") as f:
            content = f.read()
            
        if content == "Test data":
            print("✅ Local storage is working properly")
        else:
            print("❌ Local storage read/write mismatch")
            
        os.remove(test_file)
    except Exception as e:
        print(f"❌ Local storage error: {str(e)}")
    
    # Final recommendation
    print("\n===== TEST SUMMARY =====")
    if success:
        print("✅ Raspberry Pi connection test PASSED!")
        print("At least one connection method was successful.")
    else:
        print("❌ Raspberry Pi connection test FAILED!")
        print("All connection methods failed.")
    
    print("\nTo bypass the connection check in your application, you can:")
    print("1. Set environment variable: BYPASS_RPI_CHECK=true")
    print("2. Add to config.json: \"raspberry_pi\": {\"bypass_check\": true}")
    print("\n===== END OF TEST =====\n")
    
    return success

if __name__ == "__main__":
    test_raspberry_pi_connection()