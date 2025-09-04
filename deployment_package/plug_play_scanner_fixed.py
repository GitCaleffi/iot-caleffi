#!/usr/bin/env python3

import os
import json
import uuid
import time
import requests
import socket
from datetime import datetime
import threading

# Mock GPIO for non-Pi systems
try:
    import RPi.GPIO as GPIO
    IS_PI = True
    print("Running on Raspberry Pi")
except (ImportError, RuntimeError):
    class MockGPIO:
        BCM = 11
        OUT = 1
        def setmode(self, mode): 
            print("Mock GPIO: setmode")
        def setup(self, pins, mode): 
            print(f"Mock GPIO: setup pins {pins}")
        def output(self, pin, state): 
            print(f"Mock GPIO: pin {pin} = {state}")
    GPIO = MockGPIO()
    IS_PI = False
    print("Running on Linux (GPIO mocked)")

# Configuration
CONFIG = {
    "device_name": f"scanner-{uuid.uuid4().hex[:8]}",
    "server_url": "http://localhost:3000/api",
    "heartbeat_interval": 10,
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
        
        device_id = f"scanner-{uuid.uuid4().hex[:8]}"
        with open(config_file, 'w') as f:
            json.dump({"device_id": device_id}, f)
        return device_id
    
    def get_system_info(self):
        """Get system information"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
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
            
            print(f"Registering device: {self.device_id}")
            response = requests.post(
                f"{self.server_url}{CONFIG['register_endpoint']}", 
                json=data,
                timeout=5
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
                        timeout=3
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
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✓ Scan sent: {barcode}")
                GPIO.output(LED_GREEN, True)
                time.sleep(0.2)
                GPIO.output(LED_GREEN, False)
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
        
        scan_count = 0
        while self.running:
            if self.registered:
                barcode = barcodes[scan_count % len(barcodes)]
                self.scan_barcode(barcode)
                scan_count += 1
                time.sleep(8)  # Scan every 8 seconds
            else:
                time.sleep(2)
    
    def run(self):
        """Main run loop"""
        print(f"🔍 Starting Scanner: {self.device_id}")
        print(f"🌐 Server: {self.server_url}")
        
        # Try to register
        for attempt in range(3):
            if self.register_device():
                break
            print(f"Retry {attempt + 1}/3 in 5 seconds...")
            time.sleep(5)
        
        if not self.registered:
            print("❌ Failed to register after 3 attempts")
            return
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        heartbeat_thread.daemon = True
        heartbeat_thread.start()
        
        # Start scanner simulation
        scanner_thread = threading.Thread(target=self.simulate_scanner_input)
        scanner_thread.daemon = True
        scanner_thread.start()
        
        print("✅ Scanner running! Press Ctrl+C to stop")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.running = False

if __name__ == "__main__":
    scanner = PlugPlayScanner()
    scanner.run()
