def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them."""
    try:
        # Check if we're online
        if not api_client.is_online():
            return "Device is offline. Cannot process unsent messages."
            
        # Get unsent messages from local database
        local_db = LocalStorage()
        unsent_messages = local_db.get_unsent_messages()
        
        if not unsent_messages:
            return "No unsent messages found."
        
        # Load configuration
        config = load_config()
        iot_hub_owner_connection = config.get("iot_hub", {}).get("connection_string", None)
        
        if not iot_hub_owner_connection:
            return "No IoT Hub connection string configured. Cannot process unsent messages."
        
        # Process each unsent message
        success_count = 0
        failed_count = 0
        results = []
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["message"]
            timestamp = message["timestamp"]
            
            try:
                # Get device-specific connection string using dynamic registration service
                registration_service = get_dynamic_registration_service(iot_hub_owner_connection)
                device_connection_string = registration_service.register_device_with_azure(device_id)
                
                # Create a new HubClient with the device-specific connection string
                message_client = HubClient(device_connection_string)
                
                # Send the message to IoT Hub
                success = message_client.send_message(barcode, device_id)
                
                if success:
                    # Mark message as sent in the database
                    local_db.mark_message_sent(device_id, barcode, timestamp)
                    success_count += 1
                    results.append(f"Successfully sent message for device {device_id}, barcode {barcode}")
                else:
                    failed_count += 1
                    results.append(f"Failed to send message for device {device_id}, barcode {barcode}")
            except Exception as e:
                failed_count += 1
                results.append(f"Error processing message for device {device_id}: {str(e)}")
        
        # Return summary of results
        summary = f"Processed {len(unsent_messages)} unsent messages. {success_count} succeeded, {failed_count} failed."
        if auto_retry:
            return summary
        else:
            return summary + "\n\n" + "\n".join(results)
    
    except Exception as e:
        logger.error(f"Error processing unsent messages: {str(e)}")
        return f"Error processing unsent messages: {str(e)}"
