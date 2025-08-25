import requests
import json
import time

# Base URL of the web application
BASE_URL = "http://127.0.0.1:5000"

# --- Test Data ---
PI_DEVICE_1 = {
    "device_id": "pi-device-001",
    "mac_address": "b8:27:eb:01:02:03",
    "ip_address": "192.168.1.101"
}

PI_DEVICE_2 = {
    "device_id": "pi-device-002",
    "mac_address": "b8:27:eb:04:05:06",
    "ip_address": "192.168.1.102"
}

# --- Helper Functions ---

def print_response(response):
    """Prints the HTTP response in a readable format."""
    print(f"Status Code: {response.status_code}")
    try:
        print(f"Response JSON: {response.json()}")
    except json.JSONDecodeError:
        print(f"Response Text: {response.text}")
    print("-" * 20)

# --- Test Functions ---

def test_register_device(device_data):
    """Tests the device registration endpoint."""
    print(f"[*] Testing device registration for: {device_data['device_id']}")
    url = f"{BASE_URL}/api/pi-device-register"
    try:
        response = requests.post(url, json=device_data)
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"[!] Request failed: {e}")
        return False

def test_send_heartbeat(device_id, ip_address):
    """Tests the device heartbeat endpoint."""
    print(f"[*] Sending heartbeat for: {device_id}")
    url = f"{BASE_URL}/api/pi-device-heartbeat"
    payload = {"device_id": device_id, "ip_address": ip_address}
    try:
        response = requests.post(url, json=payload)
        print_response(response)
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"[!] Request failed: {e}")
        return False

# --- Main Execution ---

if __name__ == "__main__":
    print("--- Starting Pi Device API Test Suite ---")

    # Test Case 1: Register a new device
    print("\n--- Test Case 1: Register a new device ---")
    test_register_device(PI_DEVICE_1)

    # Test Case 2: Register another new device
    print("\n--- Test Case 2: Register another new device ---")
    test_register_device(PI_DEVICE_2)

    # Test Case 3: Send a heartbeat for the first device
    print("\n--- Test Case 3: Send a heartbeat for the first device ---")
    test_send_heartbeat(PI_DEVICE_1["device_id"], PI_DEVICE_1["ip_address"])

    # Test Case 4: Send a heartbeat for the second device with a new IP
    print("\n--- Test Case 4: Send a heartbeat with a new IP ---")
    test_send_heartbeat(PI_DEVICE_2["device_id"], "192.168.1.103")

    # Test Case 5: Re-register an existing device (should update)
    print("\n--- Test Case 5: Re-register an existing device ---")
    updated_device_1 = PI_DEVICE_1.copy()
    updated_device_1["ip_address"] = "192.168.1.104"
    test_register_device(updated_device_1)

    # Test Case 6: Send heartbeat for a non-existent device
    print("\n--- Test Case 6: Send heartbeat for non-existent device ---")
    test_send_heartbeat("pi-device-999", "192.168.1.200")

    print("\n--- Test Suite Finished ---")
