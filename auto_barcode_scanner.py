#!/usr/bin/env python3
"""
Auto Barcode Scanner - Plug and Play Version
"""

import os
import sys
import json
import logging
import sqlite3
import uuid
import hashlib
import queue
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('barcode_scanner.log')
    ]
)
logger = logging.getLogger(__name__)

class BarcodeScanner:
    def __init__(self):
        self.device_id = self._get_device_id()
        self.db_conn = self._init_db()
        self.scan_queue = queue.Queue()
        self.running = True
        self._start_worker()
        logger.info(f"Barcode Scanner started with device ID: {self.device_id}")
    
    def _get_device_id(self) -> str:
        """Generate a unique device ID."""
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) 
                          for i in range(0,8*6,8)][::-1])
            return f"dev-{hashlib.md5(mac.encode()).hexdigest()[:8]}"
        except:
            return f"dev-{uuid.uuid4().hex[:8]}"
