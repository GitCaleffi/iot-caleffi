#!/usr/bin/env python3
"""
Plug-and-Play Barcode Scanner Launcher
One-click startup with automatic configuration and minimal logging
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path

def setup_graceful_shutdown():
    """Setup graceful shutdown handling"""
    def signal_handler(signum, frame):
        print("\n🛑 Shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

def check_prerequisites():
    """Check if all prerequisites are met"""
    print("🔍 Checking system prerequisites...")
    
    # Check config file
    config_path = Path("config.json")
    if not config_path.exists():
        print("❌ Config file not found. Please run setup first.")
        return False
    
    # Check virtual environment
    venv_path = Path("venv")
    if not venv_path.exists():
        print("❌ Virtual environment not found. Please run setup first.")
        return False
    
    print("✅ Prerequisites check passed")
    return True

def start_barcode_scanner():
    """Start the barcode scanner with optimized settings"""
    print("🚀 Starting Plug-and-Play Barcode Scanner...")
    print("🌐 Web interface will be available at: http://localhost:7860")
    print("📱 System will auto-detect Raspberry Pi devices")
    print("🔄 Press Ctrl+C to stop")
    print("-" * 50)
    
    # Set environment variables to reduce logging
    env = os.environ.copy()
    env['PYTHONPATH'] = str(Path.cwd() / 'src')
    env['GRADIO_ANALYTICS_ENABLED'] = 'False'
    env['GRADIO_SERVER_NAME'] = '0.0.0.0'
    env['GRADIO_SERVER_PORT'] = '7860'
    
    # Start the barcode scanner app
    try:
        process = subprocess.Popen([
            sys.executable, 
            'src/barcode_scanner_app.py'
        ], env=env, cwd=Path.cwd())
        
        # Wait for process to complete
        process.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping barcode scanner...")
        if process:
            process.terminate()
            process.wait()
    except Exception as e:
        print(f"❌ Error starting barcode scanner: {e}")

def main():
    """Main plug-and-play launcher"""
    print("🎯 PLUG-AND-PLAY BARCODE SCANNER")
    print("=" * 40)
    print("✅ Zero configuration required")
    print("✅ Auto-detects Raspberry Pi devices") 
    print("✅ Auto-sends to Azure IoT Hub")
    print("✅ Web interface included")
    print("=" * 40)
    
    # Setup graceful shutdown
    setup_graceful_shutdown()
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n💡 To setup the system, run:")
        print("   python3 setup_new_device.py")
        sys.exit(1)
    
    # Start the barcode scanner
    start_barcode_scanner()
    
    print("\n✅ Barcode scanner stopped")

if __name__ == "__main__":
    main()
