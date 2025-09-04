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
except (ImportError, RuntimeError):
    class MockGPIO:
        BCM = 11
        OUT = 1
        def setmode(self, mode): pass
        def setup(self, pins, mode): pass
        def output(self, pin, state): pass
    GPIO = MockGPIO()
    IS_PI = False

# Configuration for your IoT server
CONFIG = {
    "server_url": "https://iot.caleffionline.it/api",
    "heartbeat_interval": 30,
    "scan_endpoint": "/device/scan",
    "register_endpoint": "/device/register",
    "status_endpoint": "/device/status"
}

LED_GREEN, LED_RED, LED_BLUE = 17, 27, 22
GPIO.setmode(GPIO.BCM)
GPIO.setup([LED_GREEN, LED_RED, LED_BLUE], GPIO.OUT)

class IoTScanner:
    def __init__(self):
        self.device_id = self.get_device_id()
        self.server_url = CONFIG["server_url"]
        self.registered = False
        self.running = True
        
    def get_device_id(self):
        config_file = "/tmp/iot_scanner_config.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)["device_id"]
        
        device_id = f"pi-{uuid.uuid4().hex[:8]}"
        with open(config_file, 'w') as f:
            json.dump({"device_id": device_id}, f)
        return device_id
    
    def get_system_info(self):
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
        try:
            data = self.get_system_info()
            data["device_type"] = "barcode_scanner"
            
            print(f"Registering with IoT server: {self.device_id}")
            response = requests.post(
                f"{self.server_url}{CONFIG['register_endpoint']}", 
                json=data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"Registration response: {response.status_code}")
            if response.status_code in [200, 201]:
                self.registered = True
                GPIO.output(LED_GREEN, True)
                print(f"✓ Registered with IoT server: {self.device_id}")
                return True
            else:
                print(f"✗ Registration failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Registration error: {e}")
            GPIO.output(LED_RED, True)
            return False
    
    def scan_barcode(self, barcode):
        try:
            data = {
                "device_id": self.device_id,
                "barcode": barcode,
                "quantity": 1,
                "timestamp": datetime.utcnow().isoformat(),
                "ip": self.get_system_info()["ip"]
            }
            
            print(f"Sending scan to IoT server: {barcode}")
            response = requests.post(
                f"{self.server_url}{CONFIG['scan_endpoint']}", 
                json=data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"Scan response: {response.status_code}")
            if response.status_code in [200, 201]:
                print(f"✓ Scan sent to IoT: {barcode}")
                GPIO.output(LED_GREEN, True)
                time.sleep(0.2)
                GPIO.output(LED_GREEN, False)
                return True
            else:
                print(f"✗ Scan failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Scan error: {e}")
            GPIO.output(LED_RED, True)
            time.sleep(0.5)
            GPIO.output(LED_RED, False)
            return False
    
    def simulate_scanner_input(self):
        barcodes = [
            "8901234567890",  # Real EAN-13 format
            "1234567890123",
            "9876543210987", 
            "5555666677778"
        ]
        
        scan_count = 0
        while self.running:
            if self.registered:
                barcode = barcodes[scan_count % len(barcodes)]
                self.scan_barcode(barcode)
                scan_count += 1
                time.sleep(10)  # Scan every 10 seconds
            else:
                time.sleep(5)
    
    def run(self):
        print(f"🔍 Starting IoT Scanner: {self.device_id}")
        print(f"🌐 IoT Server: {self.server_url}")
        
        # Try to register
        for attempt in range(5):
            if self.register_device():
                break
            print(f"Retry {attempt + 1}/5 in 10 seconds...")
            time.sleep(10)
        
        if not self.registered:
            print("❌ Failed to register with IoT server")
            return
        
        # Start scanner simulation
        scanner_thread = threading.Thread(target=self.simulate_scanner_input)
        scanner_thread.daemon = True
        scanner_thread.start()
        
        print("✅ IoT Scanner running! Press Ctrl+C to stop")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.running = False

if __name__ == "__main__":
    scanner = IoTScanner()
    scanner.run()
