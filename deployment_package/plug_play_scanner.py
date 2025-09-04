#!/usr/bin/env python3

import os
import json
import uuid
import time
import requests
import socket
import subprocess
from datetime import datetime
import threading

# Mock GPIO for non-Pi systems
try:
    import RPi.GPIO as GPIO
    IS_PI = True
except ImportError:
    class MockGPIO:
        BCM = 11
        OUT = 1
        def setmode(self, mode): pass
        def setup(self, pins, mode): pass
        def output(self, pin, state): pass
    GPIO = MockGPIO()
    IS_PI = False

# Configuration
CONFIG = {
    "device_name": f"scanner-{uuid.uuid4().hex[:8]}",
    "server_url": "https://your-live-server.com/api",
    "heartbeat_interval": 30,
    "scan_endpoint": "/device/scan",
    "register_endpoint": "/device/register",
    "status_endpoint": "/device/status"
}

LED_GREEN, LED_RED, LED_BLUE = 17, 27, 22
GPIO.setmode(GPIO.BCM)
GPIO.setup([LED_GREEN, LED_RED, LED_BLUE], GPIO.OUT)

class PlugPlayScanner:
    def __init__(self):
        self.device_id = self.get_device_id()
        self.server_url = CONFIG["server_url"]
        self.registered = False
        self.running = True
        
    def get_device_id(self):
        """Get or create unique device ID"""
        config_file = "/tmp/scanner_config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)["device_id"]
        
        device_id = f"pi-{uuid.uuid4().hex[:8]}"
        with open(config_file, 'w') as f:
            json.dump({"device_id": device_id}, f)
        return device_id
    
    def get_system_info(self):
        """Get system information"""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except:
            ip = "127.0.0.1"
            
        return {
            "device_id": self.device_id,
            "hostname": socket.gethostname(),
            "ip": ip,
            "platform": "raspberry_pi" if IS_PI else "linux",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def register_device(self):
        """Register device with live server"""
        try:
            data = self.get_system_info()
            data["device_type"] = "barcode_scanner"
            
            response = requests.post(
                f"{self.server_url}{CONFIG['register_endpoint']}", 
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                self.registered = True
                GPIO.output(LED_GREEN, True)
                GPIO.output(LED_RED, False)
                print(f"✓ Device registered: {self.device_id}")
                return True
            else:
                print(f"✗ Registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Registration error: {e}")
            GPIO.output(LED_RED, True)
            GPIO.output(LED_GREEN, False)
            return False
    
    def send_heartbeat(self):
        """Send periodic heartbeat to server"""
        while self.running:
            try:
                if self.registered:
                    data = self.get_system_info()
                    requests.post(
                        f"{self.server_url}{CONFIG['status_endpoint']}", 
                        json=data,
                        timeout=5
                    )
                    GPIO.output(LED_BLUE, True)
                    time.sleep(0.1)
                    GPIO.output(LED_BLUE, False)
                    
            except Exception as e:
                print(f"Heartbeat failed: {e}")
                
            time.sleep(CONFIG["heartbeat_interval"])
    
    def scan_barcode(self, barcode):
        """Send barcode scan to server"""
        try:
            data = {
                "device_id": self.device_id,
                "barcode": barcode,
                "timestamp": datetime.utcnow().isoformat(),
                "ip": self.get_system_info()["ip"]
            }
            
            response = requests.post(
                f"{self.server_url}{CONFIG['scan_endpoint']}", 
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"✓ Scan sent: {barcode}")
                # Flash green LED
                for _ in range(3):
                    GPIO.output(LED_GREEN, True)
                    time.sleep(0.1)
                    GPIO.output(LED_GREEN, False)
                    time.sleep(0.1)
                return True
            else:
                print(f"✗ Scan failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Scan error: {e}")
            GPIO.output(LED_RED, True)
            time.sleep(0.5)
            GPIO.output(LED_RED, False)
            return False
    
    def simulate_scanner_input(self):
        """Simulate barcode scanner input"""
        barcodes = [
            "1234567890123",
            "9876543210987", 
            "5555666677778",
            "1111222233334"
        ]
        
        while self.running:
            if self.registered:
                barcode = barcodes[int(time.time()) % len(barcodes)]
                self.scan_barcode(barcode)
                time.sleep(5)  # Scan every 5 seconds
            else:
                time.sleep(1)
    
    def run(self):
        """Main run loop"""
        print(f"Starting Plug & Play Scanner: {self.device_id}")
        
        # Try to register
        if not self.register_device():
            print("Retrying registration in 10 seconds...")
            time.sleep(10)
            self.register_device()
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
        # Start scanner simulation
        scanner_thread = threading.Thread(target=self.simulate_scanner_input)
        scanner_thread.daemon = True
        scanner_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.running = False

if __name__ == "__main__":
    scanner = PlugPlayScanner()
    scanner.run()
