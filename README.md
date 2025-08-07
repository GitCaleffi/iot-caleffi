## raspberrypi activate command (First-step)
1. ping raspberrypi.local -4

2. ssh Geektech@192.168.1.14

 # bash: sqlite3 barcode_device_mapping.db "SELECT barcode, device_id FROM barcode_device_mapping;"


# pi-barcode-scanner README.md

# Pi Barcode Scanner

This project is a barcode scanning application designed to run on a Raspberry Pi. It reads barcodes, stores device IDs, and communicates with an IoT Hub.

## Project Structure

```
pi-barcode-scanner
├── src
│   ├── main.py                # Entry point of the application
│   ├── scanner
│   │   ├── __init__.py
│   │   └── barcode_reader.py   # Barcode reading functionality
│   ├── database
│   │   ├── __init__.py
│   │   └── local_storage.py     # Local storage for device IDs
│   ├── iot
│   │   ├── __init__.py
│   │   └── hub_client.py        # IoT Hub communication
│   └── utils
│       ├── __init__.py
│       └── config.py            # Configuration loading
├── requirements.txt             # Project dependencies
├── config.json                  # Configuration settings
└── README.md                    # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd pi-barcode-scanner
   ```

2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```

3. **Register and configure devices:**
   To register multiple Raspberry Pi devices with your Azure IoT Hub, use the device registration script:
   ```
   python src/register_device.py
   ```
   This will register all device IDs listed in the script and update `config.json` with their connection details.

   - To add more devices, edit the `DEVICE_IDS` list in `src/register_device.py` and rerun the script.
   - The device IDs (e.g., `694833b1b872`) are unique identifiers for each Raspberry Pi device.

4. **Configure the project:**
   Edit the `config.json` file to set your IoT Hub connection details and local database settings. The device connection strings will be updated automatically by the registration script.

5. **Run the main application:**
   ```
   python src/main.py
   ```
   This will start the barcode scanner on your Raspberry Pi. The application will use the device ID stored locally or prompt you to scan/set one on first run.

6. **Test device messaging (optional):**
   To test sending a message from a specific device to the IoT Hub, use:
   ```
   python src/test_device_message.py --device <device_id> --barcode <barcode>
   ```
   - If you omit `--device`, you will be prompted to select a device from those registered in `config.json`.
   - The test script helps verify connectivity and payload format for any registered device.

## Usage Guidelines

- The application will prompt you to scan a barcode.
- The first scanned barcode will be stored as the device ID (unique per Raspberry Pi device).
- Subsequent scans will send messages to the IoT Hub using the stored device ID.
- If the device cannot send a message due to connectivity issues, it will store the message locally and retry later.

### Managing Multiple Devices (Not Just Multiple Raspberry Pis)
- You can register and manage multiple *logical* devices (not just physical Raspberry Pis) using this codebase.
- To do so, add all your desired device IDs to the `DEVICE_IDS` list in `src/register_device.py` and run the script. This will register each device with the IoT Hub and store their connection strings in `config.json`.
- After registration, your `config.json` will contain a list of devices and their credentials under `iot_hub > devices`.
- You can send messages as any registered device using `src/test_device_message.py` by specifying the device ID:
  ```
  python src/test_device_message.py --device <device_id> --barcode <barcode>
  ```
- You may also automate messaging for multiple devices in your own Python script by looping over the devices in `config.json`.
- This approach works for simulating or managing many devices from a single Python environment—no need for one Raspberry Pi per device.

## License

This project is licensed under the MIT License. See the LICENSE file for details.


