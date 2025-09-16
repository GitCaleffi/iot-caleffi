#!/bin/bash

# Automated Barcode Scanner Startup Script
# ========================================
# This script provides plug-and-play startup for the automated barcode scanner

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo -e "${BLUE}🚀 AUTOMATED BARCODE SCANNER${NC}"
echo -e "${BLUE}=============================${NC}"
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root. Consider running as regular user for security."
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is required but not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
print_status "Python version: $PYTHON_VERSION"

# Check working directory
if [[ ! -f "$SRC_DIR/automated_barcode_service.py" ]]; then
    print_error "Automated barcode service not found at $SRC_DIR/automated_barcode_service.py"
    exit 1
fi

print_status "Found automated barcode service"

# Check configuration
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Configuration file not found at $CONFIG_FILE"
    print_error "Please ensure config.json exists with IoT Hub connection string"
    exit 1
fi

print_status "Configuration file found"

# Check dependencies
print_status "Checking dependencies..."

# Check required Python packages
REQUIRED_PACKAGES=("evdev" "opencv-python" "pyzbar" "azure-iot-device")
MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! python3 -c "import ${package//-/_}" &> /dev/null; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [[ ${#MISSING_PACKAGES[@]} -gt 0 ]]; then
    print_warning "Missing optional packages: ${MISSING_PACKAGES[*]}"
    print_warning "Some scanning modes may not work. Install with:"
    print_warning "pip3 install ${MISSING_PACKAGES[*]}"
fi

# Detect available scanning modes
SCAN_MODES=()

# Check for USB input devices
if ls /dev/input/event* &> /dev/null; then
    SCAN_MODES+=("USB")
fi

# Check for camera
if ls /dev/video* &> /dev/null; then
    SCAN_MODES+=("Camera")
fi

if [[ ${#SCAN_MODES[@]} -eq 0 ]]; then
    print_warning "No input devices detected. Service will start but may not scan barcodes."
else
    print_status "Available scanning modes: ${SCAN_MODES[*]}"
fi

# Parse command line arguments
SCAN_MODE="usb"
DEVICE_ID=""
BACKGROUND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --camera)
            SCAN_MODE="camera"
            shift
            ;;
        --usb)
            SCAN_MODE="usb"
            shift
            ;;
        --both)
            SCAN_MODE="both"
            shift
            ;;
        --device-id)
            DEVICE_ID="$2"
            shift 2
            ;;
        --background)
            BACKGROUND=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --usb          Use USB barcode scanner (default)"
            echo "  --camera       Use camera for barcode scanning"
            echo "  --both         Use both USB and camera scanning"
            echo "  --device-id    Custom device ID"
            echo "  --background   Run in background"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Start with USB scanning"
            echo "  $0 --camera                 # Start with camera scanning"
            echo "  $0 --both                   # Start with both modes"
            echo "  $0 --device-id my-scanner   # Use custom device ID"
            echo "  $0 --background             # Run in background"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build command
CMD="python3 $SRC_DIR/automated_barcode_service.py"

case $SCAN_MODE in
    "camera")
        CMD="$CMD --camera"
        ;;
    "usb")
        CMD="$CMD --usb"
        ;;
    "both")
        CMD="$CMD --both"
        ;;
esac

if [[ -n "$DEVICE_ID" ]]; then
    CMD="$CMD --device-id $DEVICE_ID"
fi

print_status "Scan mode: ${SCAN_MODE^^}"
if [[ -n "$DEVICE_ID" ]]; then
    print_status "Device ID: $DEVICE_ID"
fi

echo ""
echo -e "${BLUE}🎯 STARTING AUTOMATED BARCODE SCANNER...${NC}"
echo ""

# Change to the script directory
cd "$SCRIPT_DIR"

# Run the service
if [[ "$BACKGROUND" == true ]]; then
    print_status "Starting in background mode..."
    nohup $CMD > /tmp/automated_barcode_scanner.log 2>&1 &
    PID=$!
    echo $PID > /tmp/automated_barcode_scanner.pid
    print_status "Service started with PID: $PID"
    print_status "Log file: /tmp/automated_barcode_scanner.log"
    print_status "To stop: kill $PID"
else
    print_status "Starting in foreground mode (Press Ctrl+C to stop)..."
    exec $CMD
fi
