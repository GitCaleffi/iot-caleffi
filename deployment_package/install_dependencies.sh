#!/bin/bash

# Automated Barcode Scanner Dependencies Installer
# ===============================================
# This script installs all required dependencies for the automated barcode scanner

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📦 INSTALLING BARCODE SCANNER DEPENDENCIES${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""

# Function to print status
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root for system packages
if [[ $EUID -ne 0 ]] && command -v apt-get &> /dev/null; then
    print_warning "Some system packages may require sudo privileges"
fi

# Update package list (if using apt)
if command -v apt-get &> /dev/null; then
    print_status "Updating package list..."
    sudo apt-get update -qq
fi

# Install system dependencies
print_status "Installing system dependencies..."

# For camera support
if command -v apt-get &> /dev/null; then
    sudo apt-get install -y \
        python3-pip \
        python3-dev \
        libzbar0 \
        libzbar-dev \
        libopencv-dev \
        python3-opencv \
        v4l-utils \
        || print_warning "Some system packages failed to install"
elif command -v yum &> /dev/null; then
    sudo yum install -y \
        python3-pip \
        python3-devel \
        zbar-devel \
        opencv-python3 \
        v4l-utils \
        || print_warning "Some system packages failed to install"
fi

# Install Python dependencies
print_status "Installing Python dependencies..."

# Core dependencies
pip3 install --user \
    azure-iot-device \
    azure-iot-hub \
    requests \
    || print_error "Failed to install core dependencies"

# USB scanning dependencies
pip3 install --user evdev || print_warning "evdev installation failed (USB scanning may not work)"

# Camera scanning dependencies
pip3 install --user \
    opencv-python \
    pyzbar \
    || print_warning "Camera dependencies failed (camera scanning may not work)"

# Optional dependencies for better performance
pip3 install --user \
    numpy \
    pillow \
    || print_warning "Optional dependencies failed"

print_status "Checking installations..."

# Test imports
python3 -c "
import sys
packages = [
    ('azure.iot.device', 'Azure IoT Device SDK'),
    ('azure.iot.hub', 'Azure IoT Hub SDK'),
    ('requests', 'HTTP Requests'),
    ('json', 'JSON Support'),
    ('threading', 'Threading Support'),
    ('queue', 'Queue Support'),
    ('logging', 'Logging Support')
]

optional_packages = [
    ('evdev', 'USB Input Device Support'),
    ('cv2', 'OpenCV Camera Support'),
    ('pyzbar', 'Barcode Detection'),
    ('numpy', 'Numerical Computing')
]

print('✅ Core Dependencies:')
for package, name in packages:
    try:
        __import__(package)
        print(f'  ✅ {name}')
    except ImportError:
        print(f'  ❌ {name} - MISSING')

print()
print('📦 Optional Dependencies:')
for package, name in optional_packages:
    try:
        __import__(package)
        print(f'  ✅ {name}')
    except ImportError:
        print(f'  ⚠️  {name} - Not available')
"

echo ""
print_status "Dependencies installation completed!"
echo ""
echo -e "${BLUE}📋 NEXT STEPS:${NC}"
echo "1. Ensure config.json has your IoT Hub connection string"
echo "2. Connect your USB barcode scanner or camera"
echo "3. Run: ./start_automated_scanner.sh"
echo ""
echo -e "${BLUE}🔧 USAGE EXAMPLES:${NC}"
echo "./start_automated_scanner.sh              # USB scanning"
echo "./start_automated_scanner.sh --camera     # Camera scanning"
echo "./start_automated_scanner.sh --both       # Both modes"
echo "./start_automated_scanner.sh --background # Run in background"
echo ""
