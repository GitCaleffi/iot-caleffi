def process_barcode_scan(barcode, device_id=None):
    """Process barcode scan: register device OR scan EAN barcode for quantity update"""
    
    # Input validation
    if not barcode or not barcode.strip():
        led_controller.blink_led("red")
        return "❌ Please enter a barcode."
    
    barcode = barcode.strip()
    
    # If device_id is provided, this is EAN barcode scanning for quantity update
    if device_id and device_id.strip():
        device_id = device_id.strip()
        return process_ean_barcode_scan(barcode, device_id)
    
    # If no device_id provided, this is device registration
    return process_device_registration(barcode)

def process_device_registration(registration_barcode):
    """Register a new device using registration barcode"""
    
    # Generate device ID from registration barcode
    device_id = f"device-{registration_barcode[-8:]}"
    
    try:
        # Check if device already registered
        registered_devices = local_db.get_registered_devices() or []
        device_already_registered = any(dev.get('device_id') == device_id for dev in registered_devices)
        
        if device_already_registered:
            led_controller.blink_led("yellow")
            return f"""⚠️ **Device Already Registered**

**Device ID:** {device_id}
**Registration Barcode:** {registration_barcode}
**Status:** Ready for EAN barcode scanning

**Next Step:** Use this device ID to scan product EAN barcodes for quantity updates."""
        
        # Register new device
        timestamp = datetime.now(timezone.utc)
        
        # Save device registration locally
        device_data = {
            'device_id': device_id,
            'registration_barcode': registration_barcode,
            'quantity': 0,  # No quantity for registration
            'registered_at': timestamp.isoformat()
        }
        local_db.save_registered_device(device_data)
        
        # Register with IoT Hub
        try:
            from utils.config import load_config
            config = load_config()
            iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string") if config else None
            
            if iot_hub_connection_string:
                reg_service = get_dynamic_registration_service(iot_hub_connection_string)
                if reg_service:
                    conn_str = reg_service.register_device_with_azure(device_id)
                    if conn_str:
                        logger.info(f"✅ Device {device_id} registered in IoT Hub")
        except Exception as e:
            logger.warning(f"IoT Hub registration failed: {e}")
        
        # Send registration to frontend API
        try:
            api_result = api_client.confirm_registration(device_id)
            if api_result.get('success', False):
                logger.info(f"✅ Device registration sent to frontend API: {device_id}")
        except Exception as e:
            logger.warning(f"Frontend API registration failed: {e}")
        
        led_controller.blink_led("green", 0.5, 3)
        
        return f"""🎉 **Device Registered Successfully**

**Device ID:** {device_id}
**Registration Barcode:** {registration_barcode}
**Registered At:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

**Status:** Device is now ready for EAN barcode scanning

**Next Step:** Use device ID "{device_id}" to scan product EAN barcodes for inventory updates."""
        
    except Exception as e:
        logger.error(f"Device registration error: {e}")
        led_controller.blink_led("red")
        return f"❌ **Device Registration Failed**: {str(e)}"

def process_ean_barcode_scan(ean_barcode, device_id):
    """Process EAN barcode scan for quantity update on registered device"""
    
    try:
        # Check if device is registered
        registered_devices = local_db.get_registered_devices() or []
        device_exists = any(dev.get('device_id') == device_id for dev in registered_devices)
        
        if not device_exists:
            led_controller.blink_led("red")
            return f"""❌ **Device Not Registered**

**Device ID:** {device_id}
**EAN Barcode:** {ean_barcode}

**Error:** Device must be registered first before scanning EAN barcodes.

**Solution:** Register the device first using a registration barcode."""
        
        # Get current quantity for this EAN barcode on this device
        existing_device = next((dev for dev in registered_devices if dev.get('device_id') == device_id), None)
        current_quantity = existing_device.get('quantity', 0) if existing_device else 0
        new_quantity = current_quantity + 1
        
        # Update quantity in local database
        local_db.update_device_quantity(device_id, new_quantity)
        
        timestamp = datetime.now(timezone.utc)
        actions_completed = []
        
        # Send to IoT Hub
        try:
            from utils.config import load_config
            config = load_config()
            iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string") if config else None
            
            reg_service = get_dynamic_registration_service(iot_hub_connection_string) if iot_hub_connection_string else None
            conn_str = reg_service.get_device_connection_string(device_id) if reg_service else None
            
            if conn_str:
                from iot.hub_client import HubClient
                hub_client = HubClient(conn_str)
                
                message_data = {
                    "messageType": "ean_scan",
                    "deviceId": device_id,
                    "eanBarcode": ean_barcode,
                    "previousQuantity": current_quantity,
                    "newQuantity": new_quantity,
                    "timestamp": timestamp.isoformat(),
                    "action": "scan_ean"
                }
                
                success = hub_client.send_message(json.dumps(message_data), device_id)
                if success:
                    actions_completed.append("✅ EAN scan sent to IoT Hub")
                    logger.info(f"✅ EAN scan sent to IoT Hub: {ean_barcode}")
                else:
                    actions_completed.append("⚠️ IoT Hub failed - saved for retry")
                    local_db.save_unsent_message(device_id, json.dumps(message_data), timestamp)
            else:
                actions_completed.append("⚠️ No IoT Hub connection - saved for retry")
                
        except Exception as e:
            logger.error(f"IoT Hub error: {e}")
            actions_completed.append(f"⚠️ IoT Hub error: {str(e)[:50]}...")
        
        # Send to Frontend API
        try:
            api_result = api_client.send_barcode_scan(device_id, ean_barcode, new_quantity)
            if api_result.get('success', False):
                actions_completed.append("✅ EAN scan sent to frontend API")
                logger.info(f"✅ EAN scan sent to frontend API: {ean_barcode}")
            else:
                actions_completed.append(f"⚠️ Frontend API failed: {api_result.get('message', 'Unknown error')}")
                
        except Exception as e:
            actions_completed.append(f"⚠️ Frontend API error: {str(e)[:50]}...")
            logger.error(f"Frontend API error: {e}")
        
        # Save scan to local database
        local_db.save_barcode_scan(device_id, ean_barcode, timestamp)
        actions_completed.append("✅ EAN scan saved locally")
        
        led_controller.blink_led("blue", 0.3, 3)
        
        return f"""📊 **EAN Barcode Scanned Successfully**

**Actions Completed:**
{chr(10).join(actions_completed)}

**Details:**
• Device ID: {device_id}
• EAN Barcode: {ean_barcode}
• Previous Quantity: {current_quantity}
• New Quantity: {new_quantity}
• Timestamp: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}

🔵 Blue LED indicates EAN scan processed"""
        
    except Exception as e:
        logger.error(f"EAN barcode scan error: {e}")
        led_controller.blink_led("red")
        return f"""❌ **EAN Scan Failed**

**Device ID:** {device_id}
**EAN Barcode:** {ean_barcode}
**Error:** {str(e)[:100]}

🔴 Red LED indicates error"""