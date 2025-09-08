#!/bin/bash
# Raspberry Pi dependency installer

echo "Installing Azure IoT dependencies on Raspberry Pi..."

# Install system dependencies
sudo apt update
sudo apt install -y build-essential cmake libssl-dev

# Install Python packages with correct names
pip install --prefer-binary azure-iot-hub==2.6.1
pip install --prefer-binary azure-iot-device==2.12.0

echo "✅ Installation complete"
