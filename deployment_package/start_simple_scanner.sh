#!/bin/bash

# Simple Barcode Scanner Startup Script
# =====================================
# Plug-and-play barcode scanner for device 7079fa7ab32e

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/src"

echo -e "${BLUE}🎯 SIMPLE BARCODE SCANNER${NC}"
echo -e "${BLUE}=========================${NC}"
echo ""

# Check if running in the correct directory
if [[ ! -f "$SRC_DIR/auto_barcode_processor.py" ]]; then
    echo "❌ Auto barcode processor not found at $SRC_DIR/auto_barcode_processor.py"
    exit 1
fi

echo -e "${GREEN}✅ Found auto barcode processor${NC}"

# Check configuration
CONFIG_FILE="$SCRIPT_DIR/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "❌ Configuration file not found at $CONFIG_FILE"
    exit 1
fi

echo -e "${GREEN}✅ Configuration file found${NC}"

# Change to the script directory
cd "$SCRIPT_DIR"

echo ""
echo -e "${BLUE}🚀 Starting Simple Barcode Scanner...${NC}"
echo -e "${BLUE}Device ID: 7079fa7ab32e${NC}"
echo ""

# Run the auto barcode processor
python3 "$SRC_DIR/auto_barcode_processor.py"
