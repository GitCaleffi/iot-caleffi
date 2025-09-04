# Device Management System

This system provides automatic device identification, internet connectivity monitoring, and IoT Hub registration for Raspberry Pi devices.

## Features

- **Automatic Device Identification**
  - Generates persistent device ID based on hardware
  - Stores ID in `/var/iot/device_config.json`
  - Falls back to hostname + timestamp if needed

- **Internet Connectivity Monitoring**
  - Multiple test servers (Google, Cloudflare, Azure)
  - Automatic reconnection handling
  - Detailed network interface status

- **IoT Hub Integration**
  - Automatic device registration
  - Heartbeat mechanism
  - Status reporting

- **LED Status Indicators**
  - Green: Online and registered
  - Yellow: Connecting/Registering
  - Red: Error/Offline
  - Blinking: Connection in progress

## Components

### 1. Device Utils (`device_utils.py`)
- Device ID generation and persistence
- Internet connectivity checking
- Network interface monitoring

### 2. LED Status Manager (`led_status_manager.py`)
- Controls RGB LED indicators
- Visual feedback for device status
- Thread-safe operation

### 3. Device Registry (`device_registry.py`)
- Handles device registration with IoT Hub
- Manages heartbeats
- Status tracking

### 4. Device Manager (`device_manager.py`)
- Main service that ties everything together
- Automatic initialization and monitoring
- Status reporting

## Usage

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements-device.txt
   ```

2. Configure `config.json`:
   ```json
   {
     "iot_hub": {
       "connection_string": "YOUR_IOT_HUB_CONNECTION_STRING",
       "device_registry_url": "https://your-iot-hub.azure-devices.net",
       "api_key": "YOUR_API_KEY"
     }
   }
   ```

### Running Tests

```bash
python test_device_manager.py
```

### Integration

```python
from src.services.device_manager import DeviceManager

# Initialize with config
device_manager = DeviceManager(config)

# Get current status
status = device_manager.get_status()
print(f"Device Status: {status}")

# Clean up on exit
device_manager.shutdown()
```

## Status Indicators

| LED Color | Status | Description |
|-----------|--------|-------------|
| Green (Solid) | Online | Device is registered and connected |
| Yellow (Blinking) | Connecting | Establishing connection/registration |
| Red (Solid) | Error | Registration failed or critical error |
| Red (Blinking) | Offline | No internet connection |

## Logging

Logs are written to `device_manager.log` with the following format:
```
2023-04-01 12:00:00,000 - device_manager - INFO - Device registered successfully
```

## Troubleshooting

1. **LEDs not working**
   - Check if running on Raspberry Pi
   - Verify GPIO permissions (add user to `gpio` group)
   - Check wiring (GPIO pins 18, 23, 24)

2. **Registration fails**
   - Verify IoT Hub connection string
   - Check network connectivity
   - Review logs for specific error messages

3. **Device ID changes**
   - Ensure `/var/iot` directory is writable
   - Check for disk space issues

## License

This project is licensed under the MIT License - see the LICENSE file for details.
