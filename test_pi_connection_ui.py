#!/usr/bin/env python3
"""
Test and demonstration of Raspberry Pi connection status system for Gradio UI
"""

import sys
import os
from pathlib import Path
import gradio as gr
import logging
from datetime import datetime

# Add src directory to path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the connection functions
from src.barcode_scanner_app import (
    check_raspberry_pi_connection, 
    get_pi_connection_status_display,
    _pi_connection_status,
    require_pi_connection,
    blink_led
)

def refresh_pi_connection():
    """Refresh Raspberry Pi connection status and return updated display."""
    logger.info("🔄 Refreshing Raspberry Pi connection...")
    
    # Check connection
    connected = check_raspberry_pi_connection()
    
    # Get updated status display
    status_display = get_pi_connection_status_display()
    
    if connected:
        blink_led("green")
        logger.info("✅ Connection refresh successful")
    else:
        blink_led("red")
        logger.warning("❌ Connection refresh failed")
    
    return status_display

@require_pi_connection
def test_barcode_scan_with_connection_check(barcode, device_id):
    """Test barcode scan that requires Pi connection."""
    if not barcode:
        return "❌ Please enter a barcode"
    
    blink_led("green")
    return f"""✅ **Barcode Scan Successful**

📊 **Barcode:** {barcode}
🆔 **Device ID:** {device_id or 'auto-generated'}
🕒 **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🍓 **Pi IP:** {_pi_connection_status.get('ip', 'Unknown')}

✅ **Status:** Processed successfully with Pi connection verified"""

@require_pi_connection
def test_registration_with_connection_check(token, device_id):
    """Test registration that requires Pi connection."""
    if not token or not device_id:
        return "❌ Please provide both registration token and device ID"
    
    blink_led("green")
    return f"""✅ **Registration Successful**

🎫 **Token:** {token}
🆔 **Device ID:** {device_id}
🕒 **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🍓 **Pi IP:** {_pi_connection_status.get('ip', 'Unknown')}

✅ **Status:** Device registered successfully with Pi connection verified"""

@require_pi_connection
def test_process_unsent_messages():
    """Test processing unsent messages that requires Pi connection."""
    blink_led("yellow")
    return f"""✅ **Unsent Messages Processed**

📨 **Messages:** 0 unsent messages found
🕒 **Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🍓 **Pi IP:** {_pi_connection_status.get('ip', 'Unknown')}

✅ **Status:** All messages processed successfully"""

def create_demo_interface():
    """Create the demonstration Gradio interface."""
    
    with gr.Blocks(title="Pi Connection Status Demo") as demo:
        gr.Markdown("# 🍓 Raspberry Pi Connection Status Demo")
        gr.Markdown("This demonstrates the Pi connection requirement system for barcode scanner operations.")
        
        with gr.Row():
            # Left column for operations
            with gr.Column():
                gr.Markdown("## 📱 Scanner Operations")
                gr.Markdown("*These operations require Pi connection*")
                
                # Barcode scanning
                gr.Markdown("### Barcode Scanning")
                barcode_input = gr.Textbox(label="Barcode", placeholder="Enter barcode to scan")
                device_id_input = gr.Textbox(label="Device ID", placeholder="Enter device ID (optional)")
                scan_button = gr.Button("🔍 Scan Barcode", variant="primary")
                scan_output = gr.Markdown("")
                
                gr.Markdown("---")
                
                # Registration
                gr.Markdown("### Device Registration")
                token_input = gr.Textbox(label="Registration Token", placeholder="Enter registration token")
                reg_device_input = gr.Textbox(label="Device ID", placeholder="Enter device ID")
                register_button = gr.Button("📝 Register Device", variant="primary")
                register_output = gr.Markdown("")
                
                gr.Markdown("---")
                
                # Unsent messages
                gr.Markdown("### Process Messages")
                process_button = gr.Button("📨 Process Unsent Messages", variant="primary")
                process_output = gr.Markdown("")
            
            # Right column for Pi status
            with gr.Column():
                gr.Markdown("## 🍓 Raspberry Pi Status")
                
                # Connection status display
                pi_status_display = gr.Markdown("🔍 **Checking Raspberry Pi connection...**")
                
                with gr.Row():
                    refresh_button = gr.Button("🔄 Refresh Connection", variant="secondary")
                
                gr.Markdown("---")
                
                gr.Markdown("## ℹ️ How It Works")
                gr.Markdown("""
**Connection Requirements:**
- All scanner operations require Pi connection
- Operations are blocked if Pi is disconnected
- Visual feedback shows connection status
- LED indicators provide hardware feedback

**Status Indicators:**
- ✅ **Connected**: Operations allowed
- ❌ **Disconnected**: Operations blocked
- 🔄 **Checking**: Status being verified

**Your Pi IP:** `192.168.1.18`
                """)
        
        # Event handlers
        refresh_button.click(
            fn=refresh_pi_connection,
            inputs=[],
            outputs=[pi_status_display]
        )
        
        scan_button.click(
            fn=test_barcode_scan_with_connection_check,
            inputs=[barcode_input, device_id_input],
            outputs=[scan_output]
        )
        
        register_button.click(
            fn=test_registration_with_connection_check,
            inputs=[token_input, reg_device_input],
            outputs=[register_output]
        )
        
        process_button.click(
            fn=test_process_unsent_messages,
            inputs=[],
            outputs=[process_output]
        )
        
        # Auto-refresh connection status on load
        demo.load(
            fn=refresh_pi_connection,
            inputs=[],
            outputs=[pi_status_display]
        )
    
    return demo

def main():
    """Main function to run the demo."""
    print("🍓 Starting Raspberry Pi Connection Status Demo")
    print("=" * 50)
    
    # Initial connection check
    print("🔍 Performing initial Pi connection check...")
    connected = check_raspberry_pi_connection()
    
    if connected:
        print(f"✅ Pi connected at {_pi_connection_status['ip']}")
    else:
        print("❌ Pi not connected - demo will show blocked operations")
    
    # Create and launch demo
    demo = create_demo_interface()
    
    print("\n🚀 Launching demo interface...")
    print("📱 Open the interface to test Pi connection requirements")
    print("🔄 Use 'Refresh Connection' to update status")
    print("🧪 Try operations with Pi connected/disconnected to see blocking behavior")
    
    demo.launch(
        server_name="0.0.0.0",
        server_port=7862,
        share=False
    )

if __name__ == "__main__":
    main()
