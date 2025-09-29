#!/bin/bash

echo "🔧 Barcode Scanner Client Configuration Fix"
echo "=========================================="

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if we're on a Raspberry Pi
if [ -f /proc/device-tree/model ]; then
    PI_MODEL=$(cat /proc/device-tree/model)
    echo "🍓 Detected Raspberry Pi: $PI_MODEL"
else
    echo "⚠️ Not running on Raspberry Pi hardware"
fi

echo ""
echo "🔍 Searching for config.json files..."

# Find all config.json files
CONFIG_FILES=$(find /home /opt /var/www 2>/dev/null -name "config.json" -type f | head -20)

if [ -z "$CONFIG_FILES" ]; then
    echo "❌ No config.json files found!"
    exit 1
fi

echo "📄 Found config files:"
echo "$CONFIG_FILES" | nl

echo ""
echo "🔍 Analyzing config files for barcode scanner configuration..."

BEST_CONFIG=""
BEST_SCORE=0

while IFS= read -r config_file; do
    if [ -f "$config_file" ]; then
        # Check if it contains barcode scanner configuration
        SCORE=0
        
        if grep -q '"iot_hub"' "$config_file" 2>/dev/null; then
            SCORE=$((SCORE + 1))
        fi
        
        if grep -q '"barcode_scanner"' "$config_file" 2>/dev/null; then
            SCORE=$((SCORE + 1))
        fi
        
        if grep -q '"api"' "$config_file" 2>/dev/null; then
            SCORE=$((SCORE + 1))
        fi
        
        if grep -q '"deployment"' "$config_file" 2>/dev/null; then
            SCORE=$((SCORE + 1))
        fi
        
        if grep -q 'SharedAccessKeyName' "$config_file" 2>/dev/null; then
            SCORE=$((SCORE + 2))  # Prefer owner connections
        fi
        
        echo "  📊 $config_file (score: $SCORE)"
        
        if [ $SCORE -gt $BEST_SCORE ]; then
            BEST_CONFIG="$config_file"
            BEST_SCORE=$SCORE
        fi
    fi
done <<< "$CONFIG_FILES"

if [ -z "$BEST_CONFIG" ] || [ $BEST_SCORE -eq 0 ]; then
    echo "❌ No valid barcode scanner config found!"
    exit 1
fi

echo ""
echo "🏆 Best config selected: $BEST_CONFIG (score: $BEST_SCORE)"

# Find potential client deployment directories
CLIENT_DIRS=(
    "$HOME/azure-iot-hub-python/deployment_package"
    "$HOME/barcode_scanner_clean/deployment_package"
    "/opt/barcode_scanner/deployment_package"
    "$(pwd)/deployment_package"
    "$(dirname "$(pwd)")/deployment_package"
)

echo ""
echo "📋 Updating client deployment directories..."

UPDATED_COUNT=0

for client_dir in "${CLIENT_DIRS[@]}"; do
    if [ -d "$client_dir" ]; then
        echo ""
        echo "📁 Found client directory: $client_dir"
        
        # Create backup if config exists
        if [ -f "$client_dir/config.json" ]; then
            cp "$client_dir/config.json" "$client_dir/config.json.backup.$(date +%Y%m%d_%H%M%S)"
            echo "  📦 Backup created: config.json.backup.$(date +%Y%m%d_%H%M%S)"
        fi
        
        # Copy the best config
        if cp "$BEST_CONFIG" "$client_dir/config.json"; then
            echo "  ✅ Config updated successfully"
            UPDATED_COUNT=$((UPDATED_COUNT + 1))
        else
            echo "  ❌ Failed to update config"
        fi
    else
        echo "  ⚠️ Directory not found: $client_dir"
    fi
done

echo ""
echo "🎉 Configuration update complete!"
echo "✅ Updated $UPDATED_COUNT client directories"
echo "🔧 Using config: $BEST_CONFIG"

# Check if barcode scanner service is running
echo ""
echo "🔍 Checking barcode scanner service status..."

if command_exists systemctl; then
    if systemctl is-active --quiet caleffi-barcode-scanner.service; then
        echo "🔄 Barcode scanner service is running - restart recommended"
        echo "   Run: sudo systemctl restart caleffi-barcode-scanner.service"
    else
        echo "⚪ Barcode scanner service is not running"
        echo "   Run: sudo systemctl start caleffi-barcode-scanner.service"
    fi
else
    echo "⚠️ systemctl not available - manual service restart may be needed"
fi

# Show next steps
echo ""
echo "📋 Next Steps:"
echo "1. Restart the barcode scanner service"
echo "2. Check logs: journalctl -u caleffi-barcode-scanner.service -f"
echo "3. Verify the correct config path is being used"
echo "4. Test barcode scanning functionality"

echo ""
echo "🔧 To check current config status, run:"
echo "   python3 check_config_status.py"
