#!/usr/bin/env python3
"""
Plug and Play Barcode Scanner with LED Flow Control
Implements the exact algorithmic flow chart provided
"""

import RPi.GPIO as GPIO
import time
import json
import sqlite3
from datetime import datetime
import requests

# LED Pins
RED_LED = 17
YELLOW_LED = 18
GREEN_LED = 24

class LEDController:
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(RED_LED, GPIO.OUT)
        GPIO.setup(YELLOW_LED, GPIO.OUT)
        GPIO.setup(GREEN_LED, GPIO.OUT)
        self.all_off()
    
    def all_off(self):
        GPIO.output(RED_LED, GPIO.LOW)
        GPIO.output(YELLOW_LED, GPIO.LOW)
        GPIO.output(GREEN_LED, GPIO.LOW)
    
    def red_solid(self):
        self.all_off()
        GPIO.output(RED_LED, GPIO.HIGH)
    
    def yellow_blinking(self):
        self.all_off()
        for _ in range(10):  # Blink for ~5 seconds
            GPIO.output(YELLOW_LED, GPIO.HIGH)
            time.sleep(0.25)
            GPIO.output(YELLOW_LED, GPIO.LOW)
            time.sleep(0.25)
    
    def green_flash_then_solid(self):
        self.all_off()
        # Flash green 3 times
        for _ in range(3):
            GPIO.output(GREEN_LED, GPIO.HIGH)
            time.sleep(0.5)
            GPIO.output(GREEN_LED, GPIO.LOW)
            time.sleep(0.5)
        # Then solid green
        GPIO.output(GREEN_LED, GPIO.HIGH)

class LocalDB:
    def __init__(self):
        self.conn = sqlite3.connect('scanner_db.sqlite', check_same_thread=False)
        self.init_db()
    
    def init_db(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                device_barcode TEXT PRIMARY KEY,
                registered_at TEXT,
                test_completed INTEGER DEFAULT 0
            )
        ''')
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY,
                barcode TEXT,
                timestamp TEXT,
                sent_to_pos INTEGER DEFAULT 0
            )
        ''')
        self.conn.commit()
    
    def is_device_barcode(self, barcode):
        """Check if barcode is a device barcode (starts with 'DEV' or specific pattern)"""
        return barcode.startswith('DEV') or len(barcode) == 12 and barcode.startswith('8179')
    
    def is_device_registered(self, device_barcode):
        cursor = self.conn.execute('SELECT * FROM devices WHERE device_barcode = ?', (device_barcode,))
        return cursor.fetchone() is not None
    
    def register_device(self, device_barcode):
        self.conn.execute('INSERT INTO devices (device_barcode, registered_at) VALUES (?, ?)',
                         (device_barcode, datetime.now().isoformat()))
        self.conn.commit()
    
    def is_test_completed(self, device_barcode):
        cursor = self.conn.execute('SELECT test_completed FROM devices WHERE device_barcode = ?', (device_barcode,))
        result = cursor.fetchone()
        return result and result[0] == 1
    
    def mark_test_completed(self, device_barcode):
        self.conn.execute('UPDATE devices SET test_completed = 1 WHERE device_barcode = ?', (device_barcode,))
        self.conn.commit()
    
    def save_scan(self, barcode):
        self.conn.execute('INSERT INTO scans (barcode, timestamp) VALUES (?, ?)',
                         (barcode, datetime.now().isoformat()))
        self.conn.commit()
    
    def has_registered_device(self):
        cursor = self.conn.execute('SELECT COUNT(*) FROM devices')
        return cursor.fetchone()[0] > 0

class PlugAndPlayScanner:
    def __init__(self):
        self.led = LEDController()
        self.db = LocalDB()
        self.server_url = "https://iot.caleffionline.it"  # Your live server
    
    def send_to_pos(self, barcode):
        """Send normal EAN barcode to POS system"""
        try:
            response = requests.post(f"{self.server_url}/api/pos/barcode", 
                                   json={"barcode": barcode}, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def send_to_iot(self, barcode):
        """Send barcode to IoT Hub"""
        try:
            response = requests.post(f"{self.server_url}/api/iot/barcode", 
                                   json={"barcode": barcode}, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def send_notification_to_frontend(self, message):
        """Send notification to frontend"""
        try:
            requests.post(f"{self.server_url}/api/notifications", 
                         json={"message": message}, timeout=5)
        except:
            pass
    
    def process_barcode(self, barcode):
        """Main algorithmic flow as per flowchart"""
        print(f"📱 Processing barcode: {barcode}")
        
        # IS IT A DEVICE BARCODE?
        if self.db.is_device_barcode(barcode):
            print("🔧 Device barcode detected")
            
            # IS DEVICE ALREADY IN LOCAL DB?
            if self.db.is_device_registered(barcode):
                print("✅ Device already registered")
                
                # IS TEST COMPLETED?
                if self.db.is_test_completed(barcode):
                    print("🟢 Test completed - Flash green and maintain")
                    self.led.green_flash_then_solid()
                    # NOT PASS EAN TO POS
                    return "Test completed - Green LED solid"
                else:
                    print("🟡 Test not completed - Yellow blinking")
                    self.led.yellow_blinking()
                    # NOT PASS EAN TO POS
                    return "Test pending - Yellow LED blinking"
            else:
                print("📝 Registering new device")
                self.db.register_device(barcode)
                print("🟡 Device registered - Yellow blinking")
                self.led.yellow_blinking()
                # NOT PASS EAN TO POS
                return "Device registered - Yellow LED blinking"
        
        else:
            print("📦 Regular barcode (not device)")
            
            # IS A DEVICE ALREADY REGISTERED LOCALLY?
            if self.db.has_registered_device():
                print("✅ Device registered - Processing as test")
                self.db.save_scan(barcode)
                
                # Mark test as completed for the registered device
                cursor = self.db.conn.execute('SELECT device_barcode FROM devices LIMIT 1')
                device = cursor.fetchone()
                if device:
                    self.db.mark_test_completed(device[0])
                
                self.send_notification_to_frontend(f"Test scan completed: {barcode}")
                print("🟢 Test saved - Flash green and maintain")
                self.led.green_flash_then_solid()
                # NOT PASS TO POS
                return "Test scan saved - Green LED solid"
            else:
                print("🟡 No device registered - Yellow LED")
                self.led.yellow_blinking()
                # NOT PASS TO POS
                return "No device registered - Yellow LED blinking"
        
        # IF NOT DEVICE BARCODE OR TEST BARCODE - NORMAL EAN
        print("📊 Normal EAN barcode - Send to POS")
        
        # SENT TO IOT
        if self.send_to_iot(barcode):
            print("📡 Sent to IoT successfully")
            if self.send_to_pos(barcode):
                print("🏪 Sent to POS successfully")
                self.led.all_off()  # Success - no LED
                return "Sent to IoT and POS"
            else:
                print("❌ Failed to send to POS")
                self.led.red_solid()
                return "Sent to IoT, failed POS - Red LED"
        else:
            print("🔴 Store locally - Solid red")
            self.db.save_scan(barcode)
            self.led.red_solid()
            return "Stored locally - Red LED solid"
    
    def start_scanning(self):
        """Start the plug and play scanner"""
        print("🚀 Plug and Play Scanner Started")
        print("📱 Scan barcodes to test the flow...")
        
        try:
            while True:
                barcode = input("Scan barcode (or type): ").strip()
                if barcode:
                    result = self.process_barcode(barcode)
                    print(f"Result: {result}\n")
                    time.sleep(1)  # Brief pause
        except KeyboardInterrupt:
            print("\n🛑 Scanner stopped")
        finally:
            self.led.all_off()
            GPIO.cleanup()

if __name__ == "__main__":
    scanner = PlugAndPlayScanner()
    scanner.start_scanning()
