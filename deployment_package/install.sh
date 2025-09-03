#!/bin/bash

# Barcode Scanner System - Automated Installation Script
# For Raspberry Pi and Linux systems

set -e  # Exit on any error

echo "=========================================="
echo "  Barcode Scanner System Installation"
echo "=========================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should NOT be run as root"
   echo "   Run as regular user: ./install.sh"
   exit 1
fi

# Update system packages
echo "📦 Updating system packages..."
sudo apt update -y

# Install Python 3 and pip if not already installed
echo "🐍 Installing Python dependencies..."
sudo apt install -y python3 python3-pip python3-venv git

# Install system dependencies for GPIO and hardware access
echo "🔧 Installing system dependencies..."
sudo apt install -y python3-rpi.gpio python3-dev build-essential

# Create virtual environment
echo "🌐 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt

# Set up GPIO permissions (for LED control)
echo "💡 Setting up GPIO permissions..."
sudo usermod -a -G gpio $USER

# Create systemd service for auto-start
echo "⚙️ Creating systemd service..."
