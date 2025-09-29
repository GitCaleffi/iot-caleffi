# Client Configuration Fix Guide

## Problem Description

The Raspberry Pi client is loading configuration from the wrong path:
```
Looking for config file at: /home/pi/azure-iot-hub-python/deployment_package/config.json
```

Instead of the correct updated configuration. This causes:
- Old/outdated configuration being used
- IoT Hub connection issues
- Missing device connection strings
- API endpoint mismatches

## Root Cause

The client-side deployment is using an old project structure from `/home/pi/azure-iot-hub-python/` instead of the updated barcode scanner system.

## Solution Options

### Option 1: Automatic Fix (Recommended)

Run the automatic configuration fix script on the Raspberry Pi:

```bash
# Copy the fix script to the Raspberry Pi
scp fix_client_config.sh pi@[PI_IP_ADDRESS]:~/

# SSH to the Raspberry Pi
ssh pi@[PI_IP_ADDRESS]

# Run the fix script
chmod +x fix_client_config.sh
./fix_client_config.sh
```

This script will:
- Find all config.json files on the system
- Analyze them to find the best barcode scanner configuration
- Update all client deployment directories
- Create backups of existing configs
- Provide next steps for service restart

### Option 2: Manual Fix

1. **Copy the correct config.json to the client:**
   ```bash
   # From server, copy to Raspberry Pi
   scp /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/config.json pi@[PI_IP_ADDRESS]:~/azure-iot-hub-python/deployment_package/
   ```

2. **Restart the barcode scanner service:**
   ```bash
   sudo systemctl restart caleffi-barcode-scanner.service
   ```

### Option 3: Update Client Code Path

Update the client deployment to use the correct project structure:

1. **Copy the entire updated deployment package:**
   ```bash
   # Create new directory structure
   ssh pi@[PI_IP_ADDRESS] "mkdir -p ~/barcode_scanner_clean"
   
   # Copy the entire deployment package
   scp -r /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package pi@[PI_IP_ADDRESS]:~/barcode_scanner_clean/
   
   # Update service to use new location
   ssh pi@[PI_IP_ADDRESS] "sudo systemctl stop caleffi-barcode-scanner.service"
   # Update service file to point to new location
   # Restart service
   ```

## Verification Steps

After applying the fix:

1. **Check configuration status:**
   ```bash
   cd ~/barcode_scanner_clean/deployment_package  # or current deployment directory
   python3 check_config_status.py
   ```

2. **Verify service logs:**
   ```bash
   journalctl -u caleffi-barcode-scanner.service -f
   ```

3. **Look for correct config path in logs:**
   Should show something like:
   ```
   Looking for config file at: /home/pi/barcode_scanner_clean/deployment_package/config.json
   ✅ Configuration loaded successfully
   ```

4. **Test barcode scanning:**
   - Scan a test barcode
   - Verify IoT Hub messages are sent
   - Check API connectivity

## Expected Results

After the fix:
- ✅ Correct configuration path used
- ✅ IoT Hub owner connection string loaded
- ✅ Commercial deployment mode active
- ✅ Device IDs auto-generated from barcodes
- ✅ API endpoints correctly configured
- ✅ Barcode scanning sends to both IoT Hub and API

## Configuration Details

The correct configuration should show:
```
🔑 Connection Type: IoT Hub Owner (Commercial)
📱 Device ID Mode: Auto-generated from barcodes
🌐 IoT Hub Hostname: CaleffiIoT.azure-devices.net
🔗 API Base URL: https://api2.caleffionline.it/api/v1
🚀 Deployment Mode: commercial
```

## Troubleshooting

### If config still not found:
1. Check file permissions: `ls -la config.json`
2. Verify file exists: `find ~ -name "config.json" -type f`
3. Check service working directory in systemd service file

### If IoT Hub connection fails:
1. Verify connection string format in config.json
2. Check network connectivity to CaleffiIoT.azure-devices.net
3. Ensure device registration is working

### If API calls fail:
1. Verify API base URL: https://api2.caleffionline.it/api/v1
2. Check network connectivity to API endpoint
3. Verify payload format matches API requirements

## Files Provided

- `fix_client_config.sh` - Automatic configuration fix script
- `check_config_status.py` - Configuration status checker
- `update_client_config.py` - Advanced configuration update tool

## Support

If issues persist after applying these fixes:
1. Run `check_config_status.py` and share the output
2. Check service logs: `journalctl -u caleffi-barcode-scanner.service --since "1 hour ago"`
3. Verify network connectivity and DNS resolution
