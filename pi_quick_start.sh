#!/bin/bash
# Quick Start Script for Raspberry Pi Barcode Scanner
# For users who want immediate setup

echo "🚀 Quick Start - Raspberry Pi Barcode Scanner"
echo "============================================="

# Make deployment script executable
chmod +x pi_deploy.sh

# Run deployment
echo "📦 Running automatic deployment..."
./pi_deploy.sh

# Start the service immediately
echo "🔄 Starting barcode scanner service..."
sudo systemctl start barcode-scanner

# Show status
echo "📊 Service Status:"
sudo systemctl status barcode-scanner --no-pager

echo ""
echo "🎉 Quick Start Complete!"
echo "========================"
echo "✅ Service is running"
echo "🔌 Connect your USB barcode scanner"
echo "📱 Start scanning barcodes immediately"
echo ""
echo "📋 Useful Commands:"
echo "• View logs: sudo journalctl -u barcode-scanner -f"
echo "• Restart: sudo systemctl restart barcode-scanner"
echo "• Stop: sudo systemctl stop barcode-scanner"
