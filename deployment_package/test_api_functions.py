#!/usr/bin/env python3

import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import sys

# Mock hardware dependencies
sys.modules['RPi.GPIO'] = MagicMock()

# Recreate the functions from your code snippet for testing
import subprocess
import socket
import requests
import uuid
from datetime import datetime

def ethernet_connected():
    try:
        with open("/sys/class/net/eth0/carrier") as f:
            return f.read().strip() == "1"
    except:
        return False

def internet_ok():
    try:
        subprocess.check_output(["ping", "-c", "1", "8.8.8.8"])
        return True
    except:
        return False

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "0.0.0.0"

def load_or_register():
    CONFIG_FILE = "/home/pi/device_config.json"
    API_URL = "https://iot.caleffionline.it/api/device/register"
    
    if os.path.exists(CONFIG_FILE):
        return json.load(open(CONFIG_FILE))
    device_id = f"pi-{uuid.uuid4().hex[:6]}"
    r = requests.post(API_URL, json={"device_id": device_id})
    cfg = r.json()
    json.dump(cfg, open(CONFIG_FILE, "w"))
    return cfg

def send_scan(client, device_id, barcode):
    payload = {
        "device_id": device_id,
        "barcode": barcode,
        "quantity": 1,
        "timestamp": datetime.utcnow().isoformat(),
        "ip": get_ip()
    }
    client.publish("barcode/scan", json.dumps(payload))

class TestAPIFunctions(unittest.TestCase):
    
    @patch('subprocess.check_output')
    def test_internet_ok_success(self, mock_subprocess):
        mock_subprocess.return_value = b"PING 8.8.8.8"
        self.assertTrue(internet_ok())
    
    @patch('subprocess.check_output')
    def test_internet_ok_failure(self, mock_subprocess):
        mock_subprocess.side_effect = Exception("Network unreachable")
        self.assertFalse(internet_ok())
    
    @patch('builtins.open', mock_open(read_data="1"))
    def test_ethernet_connected_true(self):
        self.assertTrue(ethernet_connected())
    
    @patch('builtins.open', mock_open(read_data="0"))
    def test_ethernet_connected_false(self):
        self.assertFalse(ethernet_connected())
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_ethernet_connected_no_file(self, mock_open_func):
        self.assertFalse(ethernet_connected())
    
    @patch('socket.socket')
    def test_get_ip_success(self, mock_socket):
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        mock_socket.return_value = mock_sock
        
        ip = get_ip()
        self.assertEqual(ip, "192.168.1.100")
    
    @patch('socket.socket')
    def test_get_ip_failure(self, mock_socket):
        mock_socket.side_effect = Exception("Socket error")
        
        ip = get_ip()
        self.assertEqual(ip, "0.0.0.0")
    
    @patch('requests.post')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_load_or_register_new_device(self, mock_json_dump, mock_file, mock_exists, mock_post):
        mock_exists.return_value = False
        test_config = {"device_id": "pi-abc123", "api_key": "test-key"}
        mock_post.return_value.json.return_value = test_config
        
        result = load_or_register()
        
        self.assertEqual(result["device_id"], "pi-abc123")
        mock_post.assert_called_once()
        mock_json_dump.assert_called_once()
    
    @patch('os.path.exists')
    @patch('json.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_load_existing_config(self, mock_file, mock_json_load, mock_exists):
        mock_exists.return_value = True
        test_config = {"device_id": "pi-existing", "api_key": "existing-key"}
        mock_json_load.return_value = test_config
        
        result = load_or_register()
        
        self.assertEqual(result["device_id"], "pi-existing")
        mock_json_load.assert_called_once()
    
    @patch('__main__.get_ip')
    def test_send_scan(self, mock_get_ip):
        mock_get_ip.return_value = "192.168.1.100"
        mock_client = MagicMock()
        
        send_scan(mock_client, "pi-test123", "1234567890")
        
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args[0]
        self.assertEqual(call_args[0], "barcode/scan")
        
        payload = json.loads(call_args[1])
        self.assertEqual(payload["device_id"], "pi-test123")
        self.assertEqual(payload["barcode"], "1234567890")
        self.assertEqual(payload["quantity"], 1)
        self.assertEqual(payload["ip"], "192.168.1.100")
        self.assertIn("timestamp", payload)

if __name__ == '__main__':
    unittest.main(verbosity=2)
