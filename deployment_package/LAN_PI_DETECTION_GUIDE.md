# LAN-based Raspberry Pi Detection and IoT Hub Messaging Guide

## Overview

This system implements LAN-based Raspberry Pi detection that sends connection status to IoT Hub using Device Twin properties and enables barcode scanning when Pi devices are detected on the local network.

## Key Features

### 🔍 LAN Detection
- **Automatic Pi Discovery**: Uses network discovery to find Raspberry Pi devices on local network
- **MAC Address Recognition**: Identifies Pi devices by their known MAC address prefixes
- **Service Verification**: Checks for SSH (port 22) and web services (port 5000) availability
- **Real-time Monitoring**: Continuous background monitoring with 30-second intervals

### 📡 IoT Hub Integration
- **Device Twin Reporting**: Sends Pi connection status via Azure IoT Hub Device Twin properties
- **True/False Status**: Reports connected=true/false to IoT Hub using "twining technique"
- **Rich Metadata**: Includes IP address, MAC address, hostname, and available services
- **Automatic Updates**: Status changes trigger immediate IoT Hub updates

### 📱 Barcode Scanning
- **Conditional Scanning**: Only allows barcode scanning when Pi is detected on LAN
- **Automatic Retry**: Saves scans locally when Pi is offline, sends when reconnected
- **Status Feedback**: Clear user feedback about Pi connection status and scanning readiness

## Implementation Details

### Core Functions

#### `detect_lan_raspberry_pi() -> dict`
```python
# Detects Pi devices on LAN using network discovery
pi_status = detect_lan_raspberry_pi()
# Returns: {'connected': bool, 'ip': str, 'mac': str, 'hostname': str, 'services': list}
```

#### `send_pi_status_to_iot_hub(pi_status: dict, device_id: str) -> bool`
```python
# Sends Pi connection status to IoT Hub via Device Twin
success = send_pi_status_to_iot_hub(pi_status, device_id)
# Implements the "twining technique" for true/false status reporting
```

#### `is_pi_connected_for_scanning() -> tuple`
```python
# Checks if Pi is ready for barcode scanning
pi_connected, status_msg, pi_info = is_pi_connected_for_scanning()
# Returns: (bool, str, dict) - connection status, message, Pi info
```

#### `start_pi_status_monitoring()`
```python
# Starts background monitoring thread
start_pi_status_monitoring()
# Monitors Pi status every 30 seconds and reports changes to IoT Hub
```

### Device Twin Properties Structure

The system sends the following Device Twin properties to IoT Hub:

```json
{
  "pi_connection_status": {
    "connected": true,
    "ip_address": "192.168.1.18",
    "mac_address": "2c:cf:67:6c:45:f2",
    "hostname": "raspberry-pi",
    "services_available": ["ssh:22", "web:5000"],
    "device_count": 1,
    "last_check": "2025-01-04T05:37:43.123Z",
    "detection_method": "lan_discovery"
  }
}
```

### Barcode Scanning Workflow

1. **Pi Detection**: Check if Pi is connected on LAN
2. **Status Reporting**: Send Pi status to IoT Hub via Device Twin
3. **Conditional Processing**: 
   - If Pi connected: Process barcode and send to IoT Hub
   - If Pi offline: Save barcode locally for retry
4. **User Feedback**: Provide clear status messages with LED indicators

## Usage Examples

### Basic Usage

```python
from src.barcode_scanner_app import (
    detect_lan_raspberry_pi,
    send_pi_status_to_iot_hub,
    is_pi_connected_for_scanning
)

# Check Pi connection
pi_status = detect_lan_raspberry_pi()
if pi_status['connected']:
    print(f"✅ Pi found at {pi_status['ip']}")
else:
    print("❌ No Pi detected")

# Send status to IoT Hub
device_id = "my-device-001"
success = send_pi_status_to_iot_hub(pi_status, device_id)

# Check scanning readiness
ready, message, info = is_pi_connected_for_scanning()
print(f"Scanning ready: {ready} - {message}")
```

### Continuous Monitoring

```python
from src.barcode_scanner_app import start_pi_status_monitoring, stop_pi_status_monitoring

# Start background monitoring
start_pi_status_monitoring()

# Your application code here...

# Stop monitoring when done
stop_pi_status_monitoring()
```

### Barcode Scanning with Pi Detection

```python
from src.barcode_scanner_app import process_barcode_scan

# Process barcode (automatically checks Pi connection)
result = process_barcode_scan("1234567890123", "my-device-001")
print(result)
```

## Testing

### Run Comprehensive Test

```bash
cd /var/www/html/abhimanyu/barcode_scanner_clean/deployment_package
python test_lan_pi_detection.py
```

### Manual Testing

```python
from src.barcode_scanner_app import test_lan_detection_and_iot_hub_flow

# Run complete workflow test
results = test_lan_detection_and_iot_hub_flow()
print(f"LAN Detection: {results['lan_detection']}")
print(f"IoT Hub Reporting: {results['iot_hub_reporting']}")
print(f"Scanning Ready: {results['scanning_ready']}")
```

## Configuration

### Network Discovery Settings

The system uses the following Pi MAC address prefixes for detection:

```python
RASPBERRY_PI_MAC_PREFIXES = [
    "b8:27:eb",  # Raspberry Pi Foundation (older models)
    "dc:a6:32",  # Raspberry Pi Foundation (newer models)
    "e4:5f:01",  # Raspberry Pi Foundation (Pi 4 and newer)
    "28:cd:c1",  # Raspberry Pi Foundation (some Pi 4 models)
    "d8:3a:dd",  # Raspberry Pi Foundation (some newer models)
    "2c:cf:67",  # Raspberry Pi Foundation (additional newer models)
]
```

### Service Detection Ports

- **SSH**: Port 22
- **Web Service**: Port 5000
- **Ping**: ICMP (fallback)

## Integration with Main Application

The system is automatically integrated into the main barcode scanner application:

1. **Startup**: Pi status monitoring starts automatically
2. **Scanning**: All barcode scans check Pi connection first
3. **IoT Hub**: Device Twin updates sent on status changes
4. **Retry**: Offline scans saved and retried when Pi reconnects

## Troubleshooting

### Common Issues

1. **No Pi Detected**: Check network connectivity and Pi power
2. **IoT Hub Connection Failed**: Verify Azure IoT Hub connection string
3. **Services Not Available**: Ensure SSH or web service running on Pi
4. **MAC Address Not Recognized**: Add custom MAC prefix to configuration

### Debug Logging

Enable debug logging to see detailed Pi detection process:

```python
import logging
logging.getLogger('utils.network_discovery').setLevel(logging.DEBUG)
logging.getLogger('iot.hub_client').setLevel(logging.DEBUG)
```

## Benefits

1. **Plug-and-Play**: Automatic Pi detection without manual configuration
2. **Real-time Status**: Live monitoring of Pi connection status
3. **Reliable Messaging**: Offline message queuing with automatic retry
4. **IoT Hub Integration**: Seamless Device Twin status reporting
5. **User Feedback**: Clear status messages and LED indicators

This system provides a robust, automated solution for LAN-based Pi detection with IoT Hub integration, enabling reliable barcode scanning operations regardless of network conditions.
