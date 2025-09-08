#!/usr/bin/env python3
"""
Simple startup script for Auto Barcode Service
Zero-configuration plug-and-play barcode scanning
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Start the auto barcode service"""
    
    print("🚀 STARTING AUTO BARCODE SCANNER")
    print("=" * 40)
    print("📱 Plug-and-Play Barcode Scanning")
    print("🔄 Zero Configuration Required")
    print("📡 Automatic IoT Hub Integration")
    print("=" * 40)
    
    # Change to the deployment package directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Add src to Python path
    src_path = script_dir / "src"
    sys.path.insert(0, str(src_path))
    
    try:
        # Import and start the service
        from src.auto_barcode_service import AutoBarcodeService
        
        service = AutoBarcodeService()
        service.start()
        
    except ImportError as e:
        print(f"❌ IMPORT ERROR: {e}")
        print("💡 Make sure all dependencies are installed")
        sys.exit(1)
    except Exception as e:
        print(f"❌ SERVICE ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
