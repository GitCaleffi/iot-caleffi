#!/bin/bash
# Simple service wrapper for barcode scanner

# Auto-detect project directory from script location (absolute path)
PROJECT_DIR="$(realpath "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")"
PYTHON_PATH="/usr/bin/python3"
PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR/deployment_package/src"

# Add user Python packages to path for gradio and other dependencies
USER_HOME="$(realpath "$(eval echo ~$(whoami))")"
USER_PYTHON_PATH="$(realpath "$USER_HOME/.local/lib/python3.10/site-packages")"
if [ -d "$USER_PYTHON_PATH" ]; then
    PYTHONPATH="$PYTHONPATH:$USER_PYTHON_PATH"
fi

cd "$PROJECT_DIR"

echo "🚀 Starting Caleffi Barcode Scanner Service..."
echo "📁 Working Directory: $PROJECT_DIR"
echo "🐍 Python Path: $PYTHON_PATH"
echo "📦 PYTHONPATH: $PYTHONPATH"

# Set environment for service mode
export PYTHONPATH="$PYTHONPATH"
export PYTHONUNBUFFERED=1
export HOME="$USER_HOME"

# Start the scanner in service mode
exec "$PYTHON_PATH" "$PROJECT_DIR/keyboard_scanner.py" --service
