import cv2
import numpy as np
from pyzbar import pyzbar
import threading
import time
import logging

logger = logging.getLogger(__name__)

class CameraBarcodeScanner:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.scanning = False
        self.last_barcode = None
        self.last_scan_time = 0
        self.scan_cooldown = 2  # seconds between scans
        
    def start_camera(self):
        """Initialize camera"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                logger.error(f"Cannot open camera {self.camera_index}")
                return False
            
            # Set camera properties for better barcode detection
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            return True
        except Exception as e:
            logger.error(f"Error starting camera: {str(e)}")
            return False
    
    def stop_camera(self):
        """Release camera"""
        if self.cap:
            self.cap.release()
            self.cap = None
        cv2.destroyAllWindows()
    
    def scan_frame(self, frame):
        """Scan a single frame for barcodes"""
        try:
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect barcodes
            barcodes = pyzbar.decode(gray)
            
            for barcode in barcodes:
                # Extract barcode data
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                # Get barcode location
                (x, y, w, h) = barcode.rect
                
                # Draw rectangle around barcode
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Add text
                text = f"{barcode_type}: {barcode_data}"
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                
                return barcode_data, frame
            
            return None, frame
            
        except Exception as e:
            logger.error(f"Error scanning frame: {str(e)}")
            return None, frame
    
    def continuous_scan(self, callback=None):
        """Continuously scan for barcodes"""
        if not self.start_camera():
            return False
        
        self.scanning = True
        
        try:
            while self.scanning:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Scan for barcodes
                barcode_data, processed_frame = self.scan_frame(frame)
                
                # If barcode detected and cooldown passed
                if barcode_data and time.time() - self.last_scan_time > self.scan_cooldown:
                    if barcode_data != self.last_barcode:
                        self.last_barcode = barcode_data
                        self.last_scan_time = time.time()
                        
                        logger.info(f"Barcode detected: {barcode_data}")
                        
                        # Call callback if provided
                        if callback:
                            callback(barcode_data)
                
                # Display frame (optional - can be disabled for headless)
                cv2.imshow('Barcode Scanner', processed_frame)
                
                # Break on 'q' key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            logger.error(f"Error in continuous scan: {str(e)}")
        finally:
            self.stop_camera()
        
        return True
    
    def single_scan(self, timeout=10):
        """Scan for a single barcode with timeout"""
        if not self.start_camera():
            return None
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                ret, frame = self.cap.read()
                if not ret:
                    continue
                
                barcode_data, processed_frame = self.scan_frame(frame)
                
                if barcode_data:
                    logger.info(f"Barcode detected: {barcode_data}")
                    return barcode_data
                
                # Display frame
                cv2.imshow('Barcode Scanner - Press Q to quit', processed_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
        except Exception as e:
            logger.error(f"Error in single scan: {str(e)}")
        finally:
            self.stop_camera()
        
        return None
    
    def stop_scanning(self):
        """Stop continuous scanning"""
        self.scanning = False