#!/bin/bash

# Master SD Card Image Creation Script
# Run this after setting up your first Raspberry Pi completely

echo "=========================================="
echo "  Master SD Card Image Creation Tool"
echo "=========================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script needs root privileges for SD card access"
   echo "   Run as: sudo ./create_master_image.sh"
   exit 1
fi

# Detect SD card
echo "🔍 Detecting SD card devices..."
lsblk -d -o NAME,SIZE,MODEL | grep -E "(mmcblk|sd[a-z])"

echo ""
read -p "📋 Enter SD card device (e.g., /dev/mmcblk0 or /dev/sdb): " SD_DEVICE

if [[ ! -b "$SD_DEVICE" ]]; then
    echo "❌ Device $SD_DEVICE not found or not a block device"
    exit 1
fi

# Safety check
echo "⚠️  WARNING: This will create an image of $SD_DEVICE"
echo "   Make sure this is your MASTER SD card with barcode scanner installed"
echo ""
read -p "🤔 Continue? (yes/no): " CONFIRM

if [[ "$CONFIRM" != "yes" ]]; then
    echo "❌ Aborted by user"
    exit 1
fi

# Create image
IMAGE_NAME="barcode-scanner-master-$(date +%Y%m%d).img"
echo ""
echo "📸 Creating master image: $IMAGE_NAME"
echo "   This may take 10-30 minutes depending on SD card size..."

dd if="$SD_DEVICE" of="$IMAGE_NAME" bs=4M status=progress

if [[ $? -eq 0 ]]; then
    echo ""
    echo "✅ Master image created successfully: $IMAGE_NAME"
    
    # Get image size
    IMAGE_SIZE=$(ls -lh "$IMAGE_NAME" | awk '{print $5}')
    echo "📊 Image size: $IMAGE_SIZE"
    
    # Compress image
    echo "🗜️  Compressing image for distribution..."
    gzip "$IMAGE_NAME"
    
    COMPRESSED_SIZE=$(ls -lh "${IMAGE_NAME}.gz" | awk '{print $5}')
    echo "✅ Compressed image: ${IMAGE_NAME}.gz"
    echo "📊 Compressed size: $COMPRESSED_SIZE"
    
    echo ""
    echo "🎯 NEXT STEPS:"
    echo "   1. Test image on 2-3 different Raspberry Pis"
    echo "   2. Verify each gets unique device ID"
    echo "   3. Confirm barcode scanning works"
    echo "   4. Use image for mass production"
    echo ""
    echo "📋 MASS FLASHING COMMAND:"
    echo "   sudo dd if=${IMAGE_NAME}.gz | gunzip | dd of=/dev/sdX bs=4M"
    
else
    echo "❌ Failed to create image"
    exit 1
fi
