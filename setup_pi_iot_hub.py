#!/usr/bin/env python3
"""
Setup script for configuring Pi IoT Hub connection
Helps generate the correct device connection string and setup heartbeat client
"""

import json
import os
import sys

def setup_pi_device():
    """Interactive setup for Pi IoT Hub connection"""
    print("🚀 Pi IoT Hub Setup")
    print("=" * 40)
    
    print("\n📋 Steps to complete before running this setup:")
    print("1. Go to Azure Portal → IoT Hub → Devices → + New")
    print("2. Set Device ID (e.g., 'live-server-pi' or 'pi-yourname')")
    print("3. Choose Authentication: Symmetric Key")
    print("4. Copy the Device Connection String")
    print("\nThe connection string should look like:")
    print("HostName=YourIoTHub.azure-devices.net;DeviceId=your-device-id;SharedAccessKey=XXXXX")
    
    print("\n" + "-" * 40)
    
    # Get device connection string from user
    connection_string = input("\n📝 Paste your device connection string here: ").strip()
    
    if not connection_string:
        print("❌ No connection string provided. Exiting.")
        return False
    
    # Validate connection string format
    required_parts = ["HostName=", "DeviceId=", "SharedAccessKey="]
    if not all(part in connection_string for part in required_parts):
        print("❌ Invalid connection string format. Please check and try again.")
        return False
    
    # Extract device ID from connection string
    try:
        device_id = None
        for part in connection_string.split(";"):
            if part.startswith("DeviceId="):
                device_id = part.split("=", 1)[1]
                break
        
        if not device_id:
            print("❌ Could not extract DeviceId from connection string.")
            return False
            
        print(f"✅ Detected Device ID: {device_id}")
        
    except Exception as e:
        print(f"❌ Error parsing connection string: {e}")
        return False
    
    # Update pi_heartbeat_client.py with the connection string
    heartbeat_file = "pi_heartbeat_client.py"
    
    try:
        # Read current file
        with open(heartbeat_file, 'r') as f:
            content = f.read()
        
        # Replace the connection string line
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('CONNECTION_STRING = '):
                lines[i] = f'CONNECTION_STRING = "{connection_string}"'
                break
        
        # Replace device ID references
        for i, line in enumerate(lines):
            if '"deviceId": "pi-5284d8ff"' in line:
                lines[i] = line.replace('"deviceId": "pi-5284d8ff"', f'"deviceId": "{device_id}"')
            elif 'f"📡 Device ID: pi-5284d8ff"' in line:
                lines[i] = line.replace('pi-5284d8ff', device_id)
        
        # Write updated file
        with open(heartbeat_file, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"✅ Updated {heartbeat_file} with your device connection string")
        
    except Exception as e:
        print(f"❌ Error updating heartbeat client: {e}")
        return False
    
    # Create systemd service file for auto-start
    service_content = f"""[Unit]
Description=Pi IoT Hub Heartbeat Client
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory={os.getcwd()}
ExecStart=/usr/bin/python3 {os.path.join(os.getcwd(), heartbeat_file)}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = "pi-iot-heartbeat.service"
    try:
        with open(service_file, 'w') as f:
            f.write(service_content)
        print(f"✅ Created systemd service file: {service_file}")
    except Exception as e:
        print(f"⚠️ Could not create service file: {e}")
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Test the heartbeat client:")
    print(f"   python3 {heartbeat_file}")
    print("\n2. Install as system service (optional):")
    print(f"   sudo cp {service_file} /etc/systemd/system/")
    print("   sudo systemctl daemon-reload")
    print("   sudo systemctl enable pi-iot-heartbeat")
    print("   sudo systemctl start pi-iot-heartbeat")
    print("\n3. Check service status:")
    print("   sudo systemctl status pi-iot-heartbeat")
    print("\n4. View logs:")
    print("   sudo journalctl -u pi-iot-heartbeat -f")
    
    return True

if __name__ == "__main__":
    success = setup_pi_device()
    sys.exit(0 if success else 1)
