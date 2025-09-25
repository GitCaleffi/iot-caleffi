#!/bin/bash
# Install POS Forwarding Dependencies
# Fixes "no module named serial" and other missing dependencies

echo "🔧 Installing POS Forwarding Dependencies"
echo "========================================"

# Update package list
echo "📦 Updating package list..."
apt-get update -qq

# Install Python serial communication
echo "📡 Installing Python serial communication..."
pip3 install pyserial || echo "⚠️  pyserial installation failed"

# Install network requests library
echo "🌐 Installing Python requests library..."
pip3 install requests || echo "⚠️  requests installation failed"

# Install clipboard tools
echo "📋 Installing clipboard tools..."
apt-get install -y xclip xsel || echo "⚠️  Clipboard tools installation failed"

# Install keyboard simulation tools
echo "⌨️  Installing keyboard simulation tools..."
apt-get install -y xdotool || echo "⚠️  xdotool installation failed"

# Test installations
echo ""
echo "🧪 Testing installations..."

# Test serial
python3 -c "import serial; print('✅ pyserial: OK')" 2>/dev/null || echo "❌ pyserial: FAILED"

# Test requests
python3 -c "import requests; print('✅ requests: OK')" 2>/dev/null || echo "❌ requests: FAILED"

# Test xclip
which xclip >/dev/null 2>&1 && echo "✅ xclip: OK" || echo "❌ xclip: FAILED"

# Test xdotool
which xdotool >/dev/null 2>&1 && echo "✅ xdotool: OK" || echo "❌ xdotool: FAILED"

echo ""
echo "🎉 Dependency installation complete!"
echo "💡 You can now run the POS forwarding system without 'no module named serial' errors"
echo ""
echo "🚀 To test: python3 test_pos_forwarding_enhanced.py"
