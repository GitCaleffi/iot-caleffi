#!/usr/bin/env python3
"""
Barcode Input Monitor for Caleffi Barcode Scanner
Monitors for barcode scanner input from USB HID devices
"""

import os
import sys
import time
import logging
import threading
import select
import subprocess
from pathlib import Path

try:
    import evdev
    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BarcodeInputMonitor:
    def __init__(self, callback=None):
        self.callback = callback
        self.running = False
        self.monitor_thread = None
        self.is_raspberry_pi = self._detect_raspberry_pi()
        self.barcode_buffer = ""
        self.last_input_time = 0
        
    def _detect_raspberry_pi(self):
        """Detect if running on Raspberry Pi"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                return 'Raspberry Pi' in f.read()
        except:
            return False
    
    def start(self):
        """Start barcode input monitoring"""
        if self.running:
            return True
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Barcode input monitor started")
        return True
    
    def stop(self):
        """Stop barcode input monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Barcode input monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Barcode monitor loop started - monitoring USB input devices...")
        
        if EVDEV_AVAILABLE:
            self._monitor_evdev_devices()
        else:
            self._monitor_fallback()
    
    def _monitor_evdev_devices(self):
        """Monitor USB input devices using evdev"""
        logger.info("Using evdev to monitor USB barcode scanners...")
        
        while self.running:
            try:
                # Get all input devices
                devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
                keyboard_devices = []
                
                for device in devices:
                    # Look for keyboard-like devices (barcode scanners appear as keyboards)
                    if evdev.ecodes.EV_KEY in device.capabilities():
                        keyboard_devices.append(device)
                
                if keyboard_devices:
                    logger.info(f"Monitoring {len(keyboard_devices)} keyboard devices for barcode input...")
                    
                    # Monitor all keyboard devices
                    device_map = {dev.fd: dev for dev in keyboard_devices}
                    
                    while self.running:
                        # Wait for input on any device
                        ready_devices = select.select(keyboard_devices, [], [], 0.1)[0]
                        
                        for device in ready_devices:
                            try:
                                events = device.read()
                                for event in events:
                                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # Key press
                                        self._process_key_event(event.code, device.name)
                            except (OSError, IOError) as e:
                                logger.debug(f"Device read error: {e}")
                                break
                        
                        # Check for file-based input (for testing)
                        if os.path.exists('/tmp/barcode_input.txt'):
                            self._process_file_input()
                
                time.sleep(1)  # Retry device detection
                
            except Exception as e:
                logger.error(f"Error in evdev monitor: {e}")
                time.sleep(5)
    
    def _monitor_fallback(self):
        """Fallback monitoring without evdev"""
        logger.info("Using fallback monitoring (no evdev)...")
        
        while self.running:
            try:
                # Check for file-based input (for testing)
                if os.path.exists('/tmp/barcode_input.txt'):
                    self._process_file_input()
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in fallback monitor: {e}")
                time.sleep(1)
    
    def _process_file_input(self):
        """Process file-based barcode input"""
        try:
            logger.info("Found barcode input file, processing...")
            with open('/tmp/barcode_input.txt', 'r') as f:
                barcode = f.read().strip()
            os.remove('/tmp/barcode_input.txt')
            logger.info(f"Processing barcode from file: {barcode}")
            if barcode and self.callback:
                logger.info(f"Calling callback for barcode: {barcode}")
                self.callback(barcode)
            else:
                logger.warning(f"No callback or empty barcode: {barcode}")
        except Exception as e:
            logger.error(f"Error processing file input: {e}")
    
    def _check_usb_input(self):
        """Check for USB HID barcode scanner input"""
        try:
            if not EVDEV_AVAILABLE:
                # Fallback: check for keyboard input using xinput
                self._check_keyboard_input()
                return
                
            # Use evdev to monitor input devices
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            for device in devices:
                # Look for keyboard-like devices (barcode scanners appear as keyboards)
                if evdev.ecodes.EV_KEY in device.capabilities():
                    try:
                        # Check if device has recent activity
                        if select.select([device.fd], [], [], 0)[0]:
                            events = device.read()
                            for event in events:
                                if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # Key press
                                    self._process_key_event(event.code)
                    except (OSError, IOError):
                        continue
                        
        except Exception as e:
            logger.debug(f"USB input check error: {e}")
    
    def _check_keyboard_input(self):
        """Fallback method to check keyboard input without evdev"""
        try:
            # Use xinput to detect barcode scanner input
            result = subprocess.run(['xinput', 'list'], capture_output=True, text=True, timeout=1)
            if 'barcode' in result.stdout.lower() or 'scanner' in result.stdout.lower():
                logger.info("Barcode scanner device detected via xinput")
        except:
            pass
    
    def _process_key_event(self, key_code, device_name="Unknown"):
        """Process keyboard events from barcode scanner"""
        current_time = time.time()
        
        # Map key codes to characters
        key_map = {
            evdev.ecodes.KEY_0: '0', evdev.ecodes.KEY_1: '1', evdev.ecodes.KEY_2: '2',
            evdev.ecodes.KEY_3: '3', evdev.ecodes.KEY_4: '4', evdev.ecodes.KEY_5: '5',
            evdev.ecodes.KEY_6: '6', evdev.ecodes.KEY_7: '7', evdev.ecodes.KEY_8: '8',
            evdev.ecodes.KEY_9: '9', evdev.ecodes.KEY_A: 'A', evdev.ecodes.KEY_B: 'B',
            evdev.ecodes.KEY_C: 'C', evdev.ecodes.KEY_D: 'D', evdev.ecodes.KEY_E: 'E',
            evdev.ecodes.KEY_F: 'F'
        }
        
        if key_code == evdev.ecodes.KEY_ENTER:
            if self.barcode_buffer and len(self.barcode_buffer) >= 4:
                logger.info(f"Barcode detected from {device_name}: {self.barcode_buffer}")
                if self.callback:
                    self.callback(self.barcode_buffer)
            self.barcode_buffer = ""
            self.last_input_time = current_time
        elif key_code in key_map:
            # Reset buffer if too much time passed (new scan)
            if current_time - self.last_input_time > 2.0:
                self.barcode_buffer = ""
            
            self.barcode_buffer += key_map[key_code]
            self.last_input_time = current_time
            logger.debug(f"Building barcode: {self.barcode_buffer}")
        else:
            logger.debug(f"Unhandled key code: {key_code} from {device_name}")

def create_barcode_monitor(callback):
    """Create barcode input monitor with callback"""
    return BarcodeInputMonitor(callback)
