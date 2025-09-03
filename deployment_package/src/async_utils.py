"""Utility functions for async operations in the barcode scanner application."""
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

async def simulate_online_mode_async() -> AsyncGenerator[str, None]:
    """Restore normal online mode with streaming progress while processing unsent messages"""
    from barcode_scanner_app import process_unsent_messages_ui, simulated_offline_mode

    # Step 1: show starting message
    yield "⏳ Restoring online mode... establishing IoT connection. Please wait."

    try:
        # Step 2: flip offline flag off
        simulated_offline_mode = False
        logger.info("✅ Simulated OFFLINE mode deactivated - normal operation restored")

        # Step 3: inform and stream unsent processing
        yield "✅ Online connection restored. Now processing any unsent messages..."
        for msg in process_unsent_messages_ui():
            yield msg

        # Step 4: final
        yield "🎉 Completed restore and unsent message processing."
    except Exception as e:
        error_msg = f"❌ Error restoring online mode: {str(e)}"
        logger.error(error_msg)
        yield error_msg
