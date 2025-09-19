#!/bin/bash
# launcher.sh - Black Box Barcode Scanner Service Launcher
# Runs the keyboard scanner as a background daemon service

# Automatically detect project directory from script location
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_DIR/barcode_scanner.pid"

echo "🚀 Starting Barcode Scanner Service"
echo "📁 Project Directory: $PROJECT_DIR"
echo "📋 PID File: $PID_FILE"

cd "$PROJECT_DIR"

# Kill any existing process
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        echo "🛑 Stopping existing process (PID: $OLD_PID)"
        kill "$OLD_PID" 2>/dev/null
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# Run the scanner in the background, detached from terminal
echo "▶️ Starting keyboard_scanner.py..."
nohup python3 keyboard_scanner.py > /dev/null 2>&1 &

# Save the process ID for monitoring
NEW_PID=$!
echo $NEW_PID > "$PID_FILE"

echo "✅ Service started with PID: $NEW_PID"
echo "📝 PID saved to: $PID_FILE"