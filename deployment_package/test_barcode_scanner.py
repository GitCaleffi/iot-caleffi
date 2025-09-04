# test_barcode_scanner.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import after path setup
from barcode_scanner_app import (
    generate_device_id,
    is_scanner_connected,
    process_barcode_scan,
    get_registration_status
)

class TestBarcodeScanner(unittest.TestCase):
    
    def test_generate_device_id(self):
        """Test device ID generation"""
        device_id = generate_device_id()
        self.assertIsNotNone(device_id)
        self.assertGreater(len(device_id), 0)
    
    @patch('barcode_scanner_app.subprocess.check_output')
    def test_is_scanner_connected(self, mock_subprocess):
        """Test scanner connection detection"""
        # Test when scanner is connected
        mock_subprocess.return_value = b'Bus 001 Device 002: ID 1234:5678 Datalogic ADC, Inc. Handheld Barcode Scanner\n'
        self.assertTrue(is_scanner_connected())
        
        # Test when no scanner is connected
        mock_subprocess.return_value = b''
        self.assertFalse(is_scanner_connected())
    
    @patch('barcode_scanner_app.local_db')
    @patch('barcode_scanner_app.led_controller')
    def test_process_barcode_scan(self, mock_led, mock_db):
        """Test barcode scanning process"""
        # Mock database and LED controller
        mock_db.get_device_id.return_value = "test-device-123"
        mock_db.save_barcode.return_value = True
        
        # Test valid barcode
        result = process_barcode_scan("123456789012")
        self.assertIn("success", result.lower())
        
        # Test invalid barcode
        result = process_barcode_scan("invalid")
        self.assertIn("invalid", result.lower())
    
    @patch('barcode_scanner_app.local_db')
    def test_get_registration_status(self, mock_db):
        """Test registration status check"""
        # Test when device is registered
        mock_db.get_device_id.return_value = "test-device-123"
        status = get_registration_status()
        self.assertTrue(status['registered'])
        
        # Test when device is not registered
        mock_db.get_device_id.return_value = None
        status = get_registration_status()
        self.assertFalse(status['registered'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
