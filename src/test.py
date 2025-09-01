import logging
import json
from datetime import datetime, timezone
from utils.dynamic_device_id import generate_dynamic_device_id
from utils.dynamic_registration_service import get_dynamic_registration_service
from database.local_storage import LocalStorage
from utils.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)
local_db = LocalStorage()

def plug_and_play_registration(barcode: str):
    """Plug & Play device registration from barcode scan"""
    if not barcode or not barcode.strip():
        return "❌ No barcode provided"

    # Step 1: Generate unique device ID from barcode
    device_id = generate_dynamic_device_id(barcode)
    logger.info(f"📦 Generated Device ID from barcode {barcode}: {device_id}")

    # Step 2: Register device with IoT Hub
    try:
        registration_service = get_dynamic_registration_service()
        connection_string = registration_service.register_device_with_azure(device_id)

        if not connection_string:
            return f"❌ Failed to register {device_id} with IoT Hub"

        # Step 3: Save locally
        local_db.save_device_registration(device_id, {
            "barcode": barcode,
            "registration_date": datetime.now(timezone.utc).isoformat(),
            "connection_string": connection_string
        })

        # Step 4: Auto-connect device via ConnectionManager
        cm = ConnectionManager()
        cm.initialize_device(device_id, connection_string)

        return f"""🎉 **Plug-and-Play Registration Complete**

- Device ID: {device_id}
- Barcode: {barcode}
- Registered: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}
- Status: ✅ Connected to IoT Hub
"""
    except Exception as e:
        logger.error(f"Plug-and-play error: {e}")
        return f"❌ Error: {str(e)}"
