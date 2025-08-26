#!/usr/bin/env python3
"""
Quick Pi IoT Hub Setup - Updates heartbeat client with real connection string
"""

def update_heartbeat_client():
    print("🚀 Quick Pi IoT Hub Setup")
    print("=" * 40)
    
    print("\n📋 Steps to get your device connection string:")
    print("1. Go to Azure Portal → IoT Hub → Devices")
    print("2. Click on your Pi device (or create new if needed)")
    print("3. Copy the 'Primary connection string'")
    print("\nExample format:")
    print("HostName=CaleffiIoT.azure-devices.net;DeviceId=your-device-id;SharedAccessKey=ACTUAL_KEY_HERE")
    
    connection_string = input("\n📝 Paste your device connection string: ").strip()
    
    if not connection_string or "YOUR_DEVICE_KEY" in connection_string:
        print("❌ Please provide a real connection string from Azure Portal")
        return False
    
    # Extract device ID
    device_id = "unknown"
    for part in connection_string.split(";"):
        if part.startswith("DeviceId="):
            device_id = part.split("=", 1)[1]
            break
    
    # Update pi_heartbeat_client.py
    try:
        with open("pi_heartbeat_client.py", "r") as f:
            content = f.read()
        
        # Replace connection string
        content = content.replace(
            'CONNECTION_STRING = "HostName=CaleffiIoT.azure-devices.net;DeviceId=pi-5284d8ff;SharedAccessKey=YOUR_DEVICE_KEY"',
            f'CONNECTION_STRING = "{connection_string}"'
        )
        
        # Replace device ID references
        content = content.replace('"deviceId": "pi-5284d8ff"', f'"deviceId": "{device_id}"')
        content = content.replace('Device ID: pi-5284d8ff', f'Device ID: {device_id}')
        
        with open("pi_heartbeat_client.py", "w") as f:
            f.write(content)
        
        print(f"✅ Updated pi_heartbeat_client.py with device: {device_id}")
        
        print(f"\n🚀 Now start the heartbeat client:")
        print(f"python3 pi_heartbeat_client.py")
        
        print(f"\n🧪 Then test detection:")
        print(f"python3 test_iot_hub_pi_detection.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating file: {e}")
        return False

if __name__ == "__main__":
    update_heartbeat_client()
