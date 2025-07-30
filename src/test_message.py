from utils.config import load_config
from iot.hub_client import HubClient
import time
import traceback

def test_send_message():
    hub_client = None
    try:
        print("\n=== IoT Hub Connection Test ===")

        print("\nLoading configuration...")
        config = load_config()
        if not config:
            raise Exception("Failed to load configuration")
     
        print("\nCreating IoT Hub client...")
        hub_client = HubClient(config["iot_hub"]["connection_string"])
   
        print("\nInitial Status:")
        initial_status = hub_client.get_status()
        print(f"Connected: {initial_status['connected']}")
        print(f"deviceId: {initial_status['deviceId']}")
        print(f"Messages sent: {initial_status['messages_sent']}")
        
        print("\nTesting connection...")
        if not hub_client.test_connection():
            raise Exception("Connection test failed")
            
        # Test message
        device_id = config["iot_hub"]["deviceId"]
        test_barcode = "1234567890"  # 10-digit integer barcode
        
        print(f"\nPreparing test message...")
        print(f"deviceId: {device_id}")
        print(f"scannedBarcode: {test_barcode}")
        
        # Send message and wait a bit
        print("\nSending message...")
        # Pass barcode as first parameter, device_id as second parameter
        success = hub_client.send_message(test_barcode, device_id)
        time.sleep(2)  # Wait for message to be processed
        
        # Check final status
        print("\nFinal Status:")
        final_status = hub_client.get_status()
        print(f"Connected: {final_status['connected']}")
        print(f"deviceId: {final_status['deviceId']}")
        print(f"Messages sent: {final_status['messages_sent']}")
        print(f"Last message time: {final_status['last_message_time']}")
        
        if success:
            print("\n Test message sent successfully!")
        else:
            print("\n Failed to send test message")
            
    except Exception as e:
        print(f"\n Error: {str(e)}")
        print(f"Stack trace:\n{traceback.format_exc()}")
    finally:
        if hub_client:
            print("\nDisconnecting from IoT Hub...")
            hub_client.disconnect()

if __name__ == "__main__":
    test_send_message()
