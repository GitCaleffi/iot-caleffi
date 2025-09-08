#!/usr/bin/env python3
"""
Plug and Play Scanner using System LEDs
Uses built-in Pi LEDs: ACT (activity) and PWR (power)
"""

import time
import json
import sqlite3
from datetime import datetime
import requests

class SystemLEDController:
    def __init__(self):
        self.act_led = '/sys/class/leds/ACT/brightness'
        self.pwr_led = '/sys/class/leds/PWR/brightness'
    
    def set_led(self, led_path, state):
        try:
            with open(led_path, 'w') as led:
                led.write(str(state))
        except:
            pass
    
    def all_off(self):
        self.set_led(self.act_led, 0)
        self.set_led(self.pwr_led, 1)  # Keep power LED on
    
    def red_solid(self):
        """PWR LED solid (red)"""
        self.set_led(self.pwr_led, 1)
        self.set_led(self.act_led, 0)
        print("🔴 RED LED: Solid")
    
    def yellow_blinking(self):
        """ACT LED blinking (yellow/green)"""
        print("🟡 YELLOW LED: Blinking")
        for _ in range(10):
            self.set_led(self.act_led, 1)
            time.sleep(0.25)
            self.set_led(self.act_led, 0)
            time.sleep(0.25)
    
    def green_flash_then_solid(self):
        """ACT LED flash 3 times then solid"""
        print("🟢 GREEN LED: Flash 3x then solid")
        # Flash 3 times
        for _ in range(3):
            self.set_led(self.act_led, 1)
            time.sleep(0.5)
            self.set_led(self.act_led, 0)
            time.sleep(0.5)
        # Then solid
        self.set_led(self.act_led, 1)

class LocalDB:
    def __init__(self):
        self.conn = sqlite3.connect('/tmp/scanner_db.sqlite', check_same_thread=False)
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
        # Accept DEV prefix, 8179 prefix, or specific device ID pattern
        return (barcode.startswith('DEV') or 
                (len(barcode) >= 8 and barcode.startswith('8179')) or
                barcode == '36455ca562da')  # Your specific device
    
    def is_device_registered(self, device_barcode):
        cursor = self.conn.execute('SELECT * FROM devices WHERE device_barcode = ?', (device_barcode,))
        return cursor.fetchone() is not None
    
    def register_device(self, device_barcode):
        self.conn.execute('INSERT OR IGNORE INTO devices (device_barcode, registered_at) VALUES (?, ?)',
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
        self.led = SystemLEDController()
        self.db = LocalDB()
        self.server_url = "https://iot.caleffionline.it"
    
    def process_barcode(self, barcode):
        print(f"\n📱 BARCODE SCANNED: {barcode}")
        
        # IS IT A DEVICE BARCODE?
        if self.db.is_device_barcode(barcode):
            print("🔧 DEVICE BARCODE DETECTED")
            
            if self.db.is_device_registered(barcode):
                print("✅ Device already in local DB")
                
                if self.db.is_test_completed(barcode):
                    print("🟢 Test completed → Flash green 3s + solid green")
                    self.led.green_flash_then_solid()
                    return "✅ Test completed - Green LED solid"
                else:
                    print("🟡 Test not completed → Yellow blinking")
                    self.led.yellow_blinking()
                    return "⚠️ Test pending - Yellow LED blinking"
            else:
                print("📝 Registering device in local DB")
                self.db.register_device(barcode)
                print("🟡 Device registered → Yellow blinking")
                self.led.yellow_blinking()
                return "📝 Device registered - Yellow LED blinking"
        
        else:
            print("📦 REGULAR BARCODE (not device)")
            
            if self.db.has_registered_device():
                print("✅ Device registered locally → Save as test")
                self.db.save_scan(barcode)
                
                # Mark test completed
                cursor = self.db.conn.execute('SELECT device_barcode FROM devices LIMIT 1')
                device = cursor.fetchone()
                if device:
                    self.db.mark_test_completed(device[0])
                
                print("🟢 Test saved → Flash green 3s + solid green")
                self.led.green_flash_then_solid()
                return "✅ Test completed - Green LED solid"
            else:
                print("🟡 No device registered → Yellow LED")
                self.led.yellow_blinking()
                return "⚠️ No device registered - Yellow LED"
        
        # Normal EAN - send to POS/IoT
        print("📊 NORMAL EAN → Send to IoT/POS")
        self.db.save_scan(barcode)
        self.led.red_solid()
        return "🔴 Stored locally - Red LED solid"
    
    def start_scanning(self):
        print("🚀 PLUG AND PLAY SCANNER STARTED")
        print("💡 LED Status: ACT=Activity, PWR=Power")
        print("📱 Scan barcodes to test...")
        
        try:
            while True:
                barcode = input("\n🎯 Scan barcode: ").strip()
                if barcode:
                    result = self.process_barcode(barcode)
                    print(f"📋 RESULT: {result}")
        except KeyboardInterrupt:
            print("\n🛑 Scanner stopped")
        finally:
            self.led.all_off()

if __name__ == "__main__":
    scanner = PlugAndPlayScanner()
    scanner.start_scanning()
