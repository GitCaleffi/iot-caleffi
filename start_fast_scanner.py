#!/usr/bin/env python3
"""
Fast Barcode Scanner Startup Script
Automatically detects configuration and starts the optimized scanner
"""
import os
import sys
import logging
from pathlib import Path

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.insert(0, str(src_dir))

def setup_logging():
    """Setup optimized logging for fast mode"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/fast_scanner.log', mode='a')
        ]
    )

def main():
    """Main startup function with automatic configuration"""
    print("🚀 Starting Fast Barcode Scanner...")
    
    # Setup logging
    os.makedirs('logs', exist_ok=True)
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Import and start fast scanner
        from fast_barcode_scanner import FastBarcodeScanner
        
        logger.info("🔧 Initializing Fast Barcode Scanner with automatic configuration")
        scanner = FastBarcodeScanner()
        
        # Launch with optimized settings
        logger.info("🌐 Launching web interface...")
        scanner.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=False,
            show_error=True,
            inbrowser=True
        )
        
    except KeyboardInterrupt:
        logger.info("👋 Fast Barcode Scanner stopped by user")
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        print("❌ Failed to import required modules. Please check dependencies.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Failed to start Fast Barcode Scanner: {e}")
        print(f"❌ Startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
