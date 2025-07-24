#!/usr/bin/env python3
from azure.iot.hub import IoTHubRegistryManager
import inspect

# IoT Hub owner connection string
IOTHUB_CONNECTION_STRING = "HostName=CaleffiIoT.azure-devices.net;SharedAccessKeyName=iothubowner;SharedAccessKey=5wAebNkJEH3qI3WQ8MIXMp3Yj70z68l9vAIoTMDkEyQ="

def main():
    try:
        # Create IoTHubRegistryManager
        registry_manager = IoTHubRegistryManager.from_connection_string(IOTHUB_CONNECTION_STRING)
        
        # Get all methods
        methods = [method for method in dir(registry_manager) if not method.startswith('_')]
        
        print("Available methods in IoTHubRegistryManager:")
        for method in sorted(methods):
            print(f"- {method}")
            
        # Get version info
        try:
            import azure.iot.hub
            print(f"\nAzure IoT Hub SDK version: {azure.iot.hub.__version__}")
        except:
            print("\nCouldn't determine SDK version")
            
    except Exception as ex:
        print(f"Error: {ex}")

if __name__ == "__main__":
    main()
