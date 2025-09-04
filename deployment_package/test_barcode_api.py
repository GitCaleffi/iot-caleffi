#!/usr/bin/env python3

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import tempfile
import os

# Mock RPi.GPIO before importing the main module
import sys
sys.modules['RPi.GPIO'] = MagicMock()

# Import after mocking GPIO
import barcode_scanner_app as barcode_scanner

class TestBarcodeScanner(unittest.TestCase):
    
    def setUp(self):
        self.test_config = {
            "device_id": "pi-test123",
            "api_key": "test-key"
        }
    
    @patch('subprocess.check_output')
    def test_internet_ok_success(self, mock_subprocess):
        mock_subprocess.return_value = b"PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data."
        self.assertTrue(barcode_scanner.internet_ok())
    
    @patch('subprocess.check_output')
    def test_internet_ok_failure(self, mock_subprocess):
        mock_subprocess.side_effect = Exception("Network unreachable")
        self.assertFalse(barcode_scanner.internet_ok())
    
    @patch('builtins.open', mock_open(read_data="1"))
    def test_ethernet_connected_true(self):
        self.assertTrue(barcode_scanner.ethernet_connected())
    
    @patch('builtins.open', mock_open(read_data="0"))
    def test_ethernet_connected_false(self):
        self.assertFalse(barcode_scanner.ethernet_connected())
    
    @patch('socket.socket')
    def test_get_ip(self, mock_socket):
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        mock_socket.return_value = mock_sock
        
        ip = barcode_scanner.get_ip()
        self.assertEqual(ip, "192.168.1.100")
    
    @patch('requests.post')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_or_register_new_device(self, mock_file, mock_exists, mock_post):
        mock_exists.return_value = False
        mock_post.return_value.json.return_value = self.test_config
        
        result = barcode_scanner.load_or_register()
        
        self.assertEqual(result["device_id"], "pi-test123")
        mock_post.assert_called_once()
    
    @patch('os.path.exists')
    @patch('json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_existing_config(self, mock_file, mock_json_load, mock_exists):
        mock_exists.return_value = True
        mock_json_load.return_value = self.test_config
        
        result = barcode_scanner.load_or_register()
        
        self.assertEqual(result["device_id"], "pi-test123")
        mock_json_load.assert_called_once()
    
    @patch('barcode_scanner.get_ip')
    @patch('barcode_scanner.GPIO')
    def test_send_scan(self, mock_gpio, mock_get_ip):
        mock_get_ip.return_value = "192.168.1.100"
        mock_client = MagicMock()
        
        barcode_scanner.send_scan(mock_client, "pi-test123", "1234567890")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args[0]
        self.assertEqual(call_args[0], "barcode/scan")
        
        payload = json.loads(call_args[1])
        self.assertEqual(payload["device_id"], "pi-test123")
        self.assertEqual(payload["barcode"], "1234567890")
        self.assertEqual(payload["ip"], "192.168.1.100")

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
