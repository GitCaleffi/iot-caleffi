#!/bin/bash

# MQTT Device Discovery Server Setup Script
# This script configures the Ubuntu server for MQTT-based Pi detection

set -e

echo "🚀 Setting up MQTT Device Discovery Server..."

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    echo "✅ Running with root privileges"
else
    echo "❌ This script needs to be run with sudo"
    echo "Usage: sudo ./setup_mqtt_server.sh"
    exit 1
fi

# Install required Python packages
echo "📦 Installing Python MQTT client..."
pip3 install paho-mqtt netifaces

# Copy MQTT configuration
echo "📋 Configuring Mosquitto MQTT broker..."
cp mqtt_device_discovery.conf /etc/mosquitto/conf.d/device-discovery.conf

# Set proper permissions
chown mosquitto:mosquitto /etc/mosquitto/conf.d/device-discovery.conf
chmod 644 /etc/mosquitto/conf.d/device-discovery.conf

# Restart Mosquitto to apply new configuration
echo "🔄 Restarting Mosquitto MQTT broker..."
systemctl restart mosquitto
systemctl enable mosquitto

# Check if Mosquitto is running
if systemctl is-active --quiet mosquitto; then
    echo "✅ Mosquitto MQTT broker is running"
else
    echo "❌ Failed to start Mosquitto MQTT broker"
    systemctl status mosquitto
    exit 1
fi

# Test MQTT connectivity
echo "🧪 Testing MQTT broker connectivity..."
timeout 5 mosquitto_pub -h localhost -t test/connection -m "test" || {
    echo "❌ MQTT broker test failed"
    exit 1
}
echo "✅ MQTT broker is working correctly"

# Create MQTT discovery service for the server
echo "🔧 Creating MQTT discovery service..."
cat > /etc/systemd/system/mqtt-discovery.service << EOF
[Unit]
Description=MQTT Device Discovery Service
After=network.target mosquitto.service
Wants=network.target
Requires=mosquitto.service

[Service]
Type=simple
User=azureuser
Group=azureuser
WorkingDirectory=/var/www/html/iot-caleffi/src/utils
ExecStart=/usr/bin/python3 /var/www/html/iot-caleffi/src/utils/test_mqtt_discovery.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

Environment=PYTHONPATH=/var/www/html/iot-caleffi/

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the discovery service
systemctl daemon-reload
systemctl enable mqtt-discovery.service
systemctl start mqtt-discovery.service

# Check service status
if systemctl is-active --quiet mqtt-discovery; then
    echo "✅ MQTT Discovery Service is running"
else
    echo "❌ Failed to start MQTT Discovery Service"
    systemctl status mqtt-discovery
    exit 1
fi

# Show firewall status and open MQTT ports if needed
echo "🔥 Checking firewall configuration..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 1883/tcp comment "MQTT"
    ufw allow 9001/tcp comment "MQTT WebSocket"
    echo "✅ Opened MQTT ports in firewall"
fi

echo ""
echo "🎉 MQTT Device Discovery Server setup completed successfully!"
echo ""
echo "📊 Service Status:"
echo "   • Mosquitto MQTT Broker: $(systemctl is-active mosquitto)"
echo "   • MQTT Discovery Service: $(systemctl is-active mqtt-discovery)"
echo ""
echo "📡 MQTT Broker Details:"
echo "   • Host: $(hostname -I | awk '{print $1}')"
echo "   • Port: 1883 (MQTT)"
echo "   • WebSocket Port: 9001"
echo ""
echo "📋 Next Steps:"
echo "   1. Install the Pi client on your Raspberry Pi devices"
echo "   2. Run: ./setup_mqtt_pi_client.sh on each Pi"
echo "   3. Pi devices will automatically announce themselves"
echo ""
echo "🔍 Monitor device discovery with:"
echo "   journalctl -u mqtt-discovery -f"
