===============================================================================
PLUG-AND-PLAY BARCODE SCANNER SYSTEM - RASPBERRY PI SETUP GUIDE
===============================================================================

===============================================================================
STEP 1: RASPBERRY PI OS INSTALLATION
===============================================================================

1. Download Raspberry Pi Imager:
   https://www.raspberrypi.org/software/

2. ping raspberrypi.local -4

3 ssh Geektech@192.168.1.14

4 Enable SSH (optional but recommended):
   - After flashing, create empty file named "ssh" in boot partition
   - Or use Raspberry Pi Imager advanced options to enable SSH

5 Insert SD card into Raspberry Pi and boot

===============================================================================
STEP 2: INITIAL RASPBERRY PI SETUP
===============================================================================

1. Connect to Raspberry Pi:
   # Via SSH (if enabled):
   ssh pi@<raspberry-pi-ip>
   
   # Or connect monitor/keyboard directly

2. Update system packages:
   sudo apt update
   sudo apt upgrade -y

3. Install required system packages:
   sudo apt install -y python3-pip python3-venv git curl wget

4. Install Python development tools:
   sudo apt install -y python3-dev python3-setuptools build-essential

5. Reboot system:
   sudo reboot

===============================================================================
STEP 3: DOWNLOAD BARCODE SCANNER APPLICATION
===============================================================================

1. Clone the repository:
   git clone https://github.com/GitCaleffi/iot-caleffi.git
   cd iot-caleffi

2. Switch to the correct branch:
   git checkout feature/plug-play_v2

3. Navigate to deployment directory:
   cd deployment_package

===============================================================================
STEP 4: INSTALL PYTHON DEPENDENCIES
===============================================================================

1. Create virtual environment (recommended):
   python3 -m venv barcode_env
   source barcode_env/bin/activate

2. Install required packages:
   pip install -r ../requirements-device.txt

3. Install additional Raspberry Pi specific packages:
   pip install RPi.GPIO gpiozero

4. Verify installation:
   python3 -c "import requests, sqlite3; print('✓ Dependencies installed successfully')"

===============================================================================
STEP 5: CONFIGURE THE APPLICATION
===============================================================================

1. The config.json file should already be configured
   
2. Verify configuration:
   cat config.json

3. If needed, update IoT Hub connection strings in config.json:
   nano config.json

===============================================================================
STEP 6: TEST THE INSTALLATION
===============================================================================

1. Run basic system test:
   cd src
   python3 -c "
   from barcode_validator import validate_ean
   print('✓ Barcode validator working')
   
   import sqlite3
   print('✓ Database support working')
   
   import requests
   print('✓ Network support working')
   "

2. Test device ID generation:
   python3 -c "
   from barcode_scanner_app import generate_device_id
   device_id = generate_device_id()
   print(f'✓ Device ID generated: {device_id}')
   "

===============================================================================
STEP 7: RUN THE PLUG-AND-PLAY BARCODE SCANNER
===============================================================================

1. Navigate to source directory:
   cd /home/pi/iot-caleffi/deployment_package/src

2. Start the automatic barcode scanner:
   python3 barcode_scanner_app.py

3. You should see output like:
   🚀 Starting AUTOMATIC Plug-and-Play Barcode Scanner Service...
   🔌 Connect ethernet cable and USB barcode scanner
   📊 Just scan any barcode to test connection and auto-register!
   ⚡ All operations are automatic - no buttons needed
   🆔 Auto-generated Device ID: auto-xxxxxxxx
   🎯 Ready for barcode scan (connect ethernet + scan barcode):

4. Connect USB barcode scanner and scan any barcode to test!

===============================================================================
STEP 9: USAGE INSTRUCTIONS
===============================================================================

PLUG-AND-PLAY OPERATION:
1. Connect ethernet cable to Raspberry Pi
2. Plug in USB barcode scanner
3. Scan any barcode - that's it!

AUTOMATIC FEATURES:
✓ Auto-detects ethernet connection
✓ Auto-generates unique device ID
✓ Auto-registers device on first barcode scan
✓ Auto-processes all barcode scans
✓ Auto-saves to local database
✓ Auto-sends to cloud inventory system
✓ Auto-recovers unsent data when connection restored

NO CONFIGURATION NEEDED - EVERYTHING IS AUTOMATIC!

===============================================================================
TROUBLESHOOTING
===============================================================================

PROBLEM: "No module named 'requests'"
SOLUTION: Install dependencies: pip install -r ../requirements-device.txt

PROBLEM: "Permission denied" when accessing USB scanner
SOLUTION: Add user to dialout group: sudo usermod -a -G dialout pi

PROBLEM: "Database locked" error
SOLUTION: Stop any running instances: sudo pkill -f barcode_scanner_app.py

PROBLEM: Ethernet not detected
SOLUTION: Check cable connection and run: ip addr show

PROBLEM: Barcode scanner not recognized
SOLUTION: Check USB connection and run: lsusb

PROBLEM: IoT Hub connection failed
SOLUTION: Verify config.json has correct connection strings

PROBLEM: Service won't start automatically
SOLUTION: Check service status: sudo systemctl status barcode-scanner.service

===============================================================================
TESTING COMMANDS
===============================================================================

# Test network connectivity
ping -c 3 8.8.8.8

# Check USB devices (barcode scanner should appear)
lsusb

# Check network interfaces
ip addr show

# Test database
python3 -c "import sqlite3; print('Database OK')"

# Check service logs
sudo journalctl -u barcode-scanner.service -n 50

# Manual test run
cd /home/pi/iot-caleffi/deployment_package/src
python3 barcode_scanner_app.py

===============================================================================
SUPPORT AND MAINTENANCE
===============================================================================

LOG FILES:
- Application logs: Check console output or systemd journal
- System logs: /var/log/syslog

UPDATE APPLICATION:
cd /home/pi/iot-caleffi
git pull origin feature/plug-play_v2
pip install -r requirements-device.txt --upgrade

BACKUP DATABASE:
cp deployment_package/src/barcode_scans.db ~/barcode_scans_backup.db

RESET CONFIGURATION:
# Stop service first
sudo systemctl stop barcode-scanner.service
# Remove database to reset
rm deployment_package/src/barcode_scans.db
# Restart service
sudo systemctl start barcode-scanner.service

===============================================================================
TECHNICAL SPECIFICATIONS
===============================================================================

SUPPORTED BARCODE FORMATS:
- EAN-13, EAN-8
- UPC-A, UPC-E  
- Code 128, Code 39
- Any format supported by HID barcode scanners

NETWORK REQUIREMENTS:
- Ethernet connection with internet access
- DHCP or static IP configuration
- Outbound HTTPS access (ports 443, 8883)

STORAGE REQUIREMENTS:
- ~100MB for application
- ~10MB for database (grows with usage)
- Automatic database cleanup after successful cloud sync

PERFORMANCE:
- Processes barcodes in <1 second
- Supports continuous scanning
- Handles network interruptions gracefully
- Auto-recovery of unsent data

===============================================================================
QUICK START SUMMARY
===============================================================================

For experienced users, here's the quick setup:

1. Flash Raspberry Pi OS to SD card
2. Boot Pi and connect to internet
3. Run: sudo apt update && sudo apt upgrade -y
4. Run: sudo apt install -y python3-pip git
5. Run: git clone https://github.com/GitCaleffi/iot-caleffi.git
6. Run: cd iot-caleffi && git checkout feature/plug-play_v2
7. Run: cd deployment_package && pip install -r ../requirements-device.txt
8. Run: cd src && python3 barcode_scanner_app.py
9. Connect USB scanner and scan barcode!

===============================================================================
CONTACT INFORMATION
===============================================================================

For technical support or questions:
- GitHub Issues: https://github.com/GitCaleffi/iot-caleffi/issues
- Project Repository: https://github.com/GitCaleffi/iot-caleffi

===============================================================================
VERSION INFORMATION
===============================================================================

Application Version: Plug-and-Play v2.0
Compatible with: Raspberry Pi OS Bullseye/Bookworm
Python Version: 3.8+
Last Updated: September 2025

===============================================================================
