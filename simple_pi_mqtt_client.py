#!/usr/bin/env python3
"""
Simple MQTT Pi Client - Standalone version
Copy this file to your Raspberry Pi and run it directly
"""

import json
import time
import socket
import subprocess
import sys

# Try to import paho-mqtt, install if not available
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("📦 Installing paho-mqtt...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paho-mqtt"])
    import paho.mqtt.client as mqtt

class SimplePiClient:
    def __init__(self, server_host="iot.caleffionline.it"):
        self.server_host = server_host
        self.mqtt_port = 1883
        self.device_id = self.get_device_id()
        self.client = None
        self.connected = False
        
        print(f"🍓 Simple Pi MQTT Client")
        print(f"   Device ID: {self.device_id}")
        print(f"   Server: {server_host}")
    
    def get_device_id(self):
        """Generate device ID from system info"""
        try:
            # Try to get CPU serial (Pi-specific)
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()[-12:]
        except:
            pass
        
        # Fallback to hostname
        return socket.gethostname().lower()
    
    def get_device_info(self):
        """Get device information"""
        try:
            # Get primary IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "unknown"
        
        return {
            "device_id": self.device_id,
            "ip_address": ip,
            "hostname": socket.gethostname(),
            "device_type": "raspberry_pi",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "services": {
                "ssh": {"port": 22, "status": "available" if self.check_port(22) else "unavailable"},
                "web": {"port": 5000, "status": "available" if self.check_port(5000) else "unavailable"}
            }
        }
    
    def check_port(self, port):
        """Check if a port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            print("✅ Connected to MQTT broker")
            self.announce_device()
        else:
            print(f"❌ Failed to connect to MQTT broker (code: {rc})")
    
    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.connected = False
        print("📡 Disconnected from MQTT broker")
    
    def announce_device(self):
        """Announce device to server"""
        try:
            device_info = self.get_device_info()
            message = json.dumps(device_info)
            
            self.client.publish("devices/announce", message)
            print(f"📢 Announced device: {self.device_id} at {device_info['ip_address']}")
            
        except Exception as e:
            print(f"❌ Error announcing device: {e}")
    
    def send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            if not self.connected:
                return
                
            heartbeat = {
                "device_id": self.device_id,
                "ip_address": self.get_device_info()["ip_address"],
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "status": "online"
            }
            
            self.client.publish("devices/heartbeat", json.dumps(heartbeat))
            print(f"💓 Sent heartbeat: {self.device_id}")
            
        except Exception as e:
            print(f"❌ Error sending heartbeat: {e}")
    
    def connect_and_run(self):
        """Connect to MQTT and run"""
        try:
            print(f"🔌 Connecting to MQTT broker at {self.server_host}:{self.mqtt_port}")
            
            self.client = mqtt.Client()
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            
            self.client.connect(self.server_host, self.mqtt_port, 60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while not self.connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
            
            if not self.connected:
                print("❌ Failed to connect to MQTT broker")
                return False
            
            print("🎉 Pi MQTT client started successfully!")
            print("💓 Sending heartbeats every 30 seconds...")
            print("Press Ctrl+C to stop")
            
            # Main loop - send heartbeats every 30 seconds
            try:
                while True:
                    time.sleep(30)
                    if self.connected:
                        self.send_heartbeat()
                    else:
                        print("⚠️ Connection lost, attempting to reconnect...")
                        self.client.reconnect()
            except KeyboardInterrupt:
                print("\n🛑 Stopping Pi MQTT client...")
                self.client.loop_stop()
                self.client.disconnect()
                return True
                
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

if __name__ == "__main__":
    print("🚀 Starting Simple Pi MQTT Client...")
    
    # Allow custom server host
    server_host = sys.argv[1] if len(sys.argv) > 1 else "iot.caleffionline.it"
    
    client = SimplePiClient(server_host)
    success = client.connect_and_run()
    
    if success:
        print("✅ Pi MQTT client completed successfully")
    else:
        print("❌ Pi MQTT client failed")
        sys.exit(1)
