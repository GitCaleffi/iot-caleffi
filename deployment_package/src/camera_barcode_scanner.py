"""
Camera-based barcode scanner module for automated barcode detection
Supports real-time camera feed and image file processing
"""

import cv2
import numpy as np
import logging
from pyzbar import pyzbar
import time
from datetime import datetime
from typing import Optional, List, Tuple, Dict
import threading
import queue
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class CameraBarcodeScanner:
    """Camera-based barcode scanner with real-time detection"""
    
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.is_scanning = False
        self.barcode_queue = queue.Queue()
        self.scan_thread = None
        self.last_barcode = None
        self.last_scan_time = 0
        self.duplicate_threshold = 2.0  # seconds to avoid duplicate scans
        
    def initialize_camera(self) -> bool:
        """Initialize camera for barcode scanning"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                logger.error(f"❌ Cannot open camera {self.camera_index}")
                return False
            
            # Set camera properties for better barcode detection
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            logger.info(f"✅ Camera {self.camera_index} initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Camera initialization error: {e}")
            return False
    
    def scan_barcode_from_image(self, image_path: str) -> List[Dict]:
        """Scan barcode from image file"""
        try:
            if not os.path.exists(image_path):
                logger.error(f"❌ Image file not found: {image_path}")
                return []
            
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"❌ Cannot read image: {image_path}")
                return []
            
            # Detect barcodes
            barcodes = self._detect_barcodes_in_frame(image)
            
            if barcodes:
                logger.info(f"✅ Found {len(barcodes)} barcode(s) in image: {image_path}")
            else:
                logger.info(f"❌ No barcodes found in image: {image_path}")
            
            return barcodes
            
        except Exception as e:
            logger.error(f"❌ Error scanning image {image_path}: {e}")
            return []
    
    def scan_barcode_from_frame(self, frame) -> List[Dict]:
        """Scan barcode from camera frame"""
        try:
            return self._detect_barcodes_in_frame(frame)
        except Exception as e:
            logger.error(f"❌ Error scanning frame: {e}")
            return []
    
    def _detect_barcodes_in_frame(self, frame) -> List[Dict]:
        """Detect barcodes in a given frame"""
        try:
            # Convert to grayscale for better detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply image preprocessing for better barcode detection
            # Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Adaptive threshold for better contrast
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Detect barcodes in both original and processed images
            barcodes_original = pyzbar.decode(gray)
            barcodes_processed = pyzbar.decode(thresh)
            
            # Combine results and remove duplicates
            all_barcodes = list(barcodes_original) + list(barcodes_processed)
            unique_barcodes = {}
            
            for barcode in all_barcodes:
                barcode_data = barcode.data.decode('utf-8')
                if barcode_data not in unique_barcodes:
                    unique_barcodes[barcode_data] = barcode
            
            # Convert to our format
            detected_barcodes = []
            for barcode_data, barcode_obj in unique_barcodes.items():
                detected_barcodes.append({
                    'data': barcode_data,
                    'type': barcode_obj.type,
                    'rect': barcode_obj.rect,
                    'polygon': barcode_obj.polygon,
                    'timestamp': datetime.now().isoformat()
                })
            
            return detected_barcodes
            
        except Exception as e:
            logger.error(f"❌ Barcode detection error: {e}")
            return []
    
    def start_continuous_scanning(self, callback=None) -> bool:
        """Start continuous barcode scanning from camera"""
        try:
            if not self.initialize_camera():
                return False
            
            self.is_scanning = True
            self.scan_thread = threading.Thread(
                target=self._continuous_scan_worker, 
                args=(callback,), 
                daemon=True
            )
            self.scan_thread.start()
            
            logger.info("🎥 Started continuous barcode scanning")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting continuous scanning: {e}")
            return False
    
    def _continuous_scan_worker(self, callback=None):
        """Worker thread for continuous barcode scanning"""
        logger.info("🔄 Continuous barcode scanning worker started")
        
        while self.is_scanning and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning("⚠️ Failed to read frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Detect barcodes in frame
                barcodes = self.scan_barcode_from_frame(frame)
                
                for barcode_info in barcodes:
                    barcode_data = barcode_info['data']
                    current_time = time.time()
                    
                    # Avoid duplicate scans
                    if (self.last_barcode != barcode_data or 
                        current_time - self.last_scan_time > self.duplicate_threshold):
                        
                        self.last_barcode = barcode_data
                        self.last_scan_time = current_time
                        
                        logger.info(f"📊 Barcode detected: {barcode_data} ({barcode_info['type']})")
                        
                        # Add to queue
                        self.barcode_queue.put(barcode_info)
                        
                        # Call callback if provided
                        if callback:
                            try:
                                callback(barcode_info)
                            except Exception as e:
                                logger.error(f"❌ Callback error: {e}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Scanning worker error: {e}")
                time.sleep(1)
        
        logger.info("🛑 Continuous barcode scanning worker stopped")
    
    def get_next_barcode(self, timeout=1.0) -> Optional[Dict]:
        """Get next barcode from queue"""
        try:
            return self.barcode_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def stop_scanning(self):
        """Stop continuous barcode scanning"""
        self.is_scanning = False
        
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=2.0)
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        logger.info("🛑 Barcode scanning stopped")
    
    def capture_and_scan(self) -> List[Dict]:
        """Capture single frame and scan for barcodes"""
        try:
            if not self.cap or not self.cap.isOpened():
                if not self.initialize_camera():
                    return []
            
            ret, frame = self.cap.read()
            if not ret:
                logger.error("❌ Failed to capture frame")
                return []
            
            barcodes = self.scan_barcode_from_frame(frame)
            
            if barcodes:
                logger.info(f"✅ Captured and found {len(barcodes)} barcode(s)")
            else:
                logger.info("❌ No barcodes found in captured frame")
            
            return barcodes
            
        except Exception as e:
            logger.error(f"❌ Capture and scan error: {e}")
            return []
    
    def save_frame_with_barcodes(self, frame, barcodes, output_path):
        """Save frame with barcode annotations"""
        try:
            annotated_frame = frame.copy()
            
            for barcode_info in barcodes:
                # Draw rectangle around barcode
                rect = barcode_info['rect']
                cv2.rectangle(
                    annotated_frame,
                    (rect.left, rect.top),
                    (rect.left + rect.width, rect.top + rect.height),
                    (0, 255, 0), 2
                )
                
                # Add barcode text
                cv2.putText(
                    annotated_frame,
                    f"{barcode_info['data']} ({barcode_info['type']})",
                    (rect.left, rect.top - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
            
            cv2.imwrite(output_path, annotated_frame)
            logger.info(f"✅ Saved annotated frame: {output_path}")
            
        except Exception as e:
            logger.error(f"❌ Error saving annotated frame: {e}")

def test_camera_barcode_scanner():
    """Test camera barcode scanner functionality"""
    print("🧪 Testing Camera Barcode Scanner")
    print("=" * 50)
    
    scanner = CameraBarcodeScanner()
    
    try:
        # Test camera initialization
        print("1️⃣ Testing camera initialization...")
        if scanner.initialize_camera():
            print("✅ Camera initialized successfully")
        else:
            print("❌ Camera initialization failed")
            return False
        
        # Test single frame capture
        print("\n2️⃣ Testing single frame capture...")
        barcodes = scanner.capture_and_scan()
        
        if barcodes:
            print(f"✅ Found {len(barcodes)} barcode(s):")
            for barcode in barcodes:
                print(f"   📊 {barcode['data']} ({barcode['type']})")
        else:
            print("❌ No barcodes found in frame")
        
        # Test continuous scanning for 10 seconds
        print("\n3️⃣ Testing continuous scanning (10 seconds)...")
        print("📱 Point camera at barcode...")
        
        def barcode_callback(barcode_info):
            print(f"🎯 DETECTED: {barcode_info['data']} ({barcode_info['type']})")
        
        scanner.start_continuous_scanning(callback=barcode_callback)
        
        # Wait for 10 seconds
        time.sleep(10)
        
        scanner.stop_scanning()
        print("✅ Continuous scanning test completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        scanner.stop_scanning()

if __name__ == "__main__":
    # Test the camera barcode scanner
    test_camera_barcode_scanner()
