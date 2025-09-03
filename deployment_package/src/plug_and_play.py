#!/usr/bin/env python3
"""
Simple Plug-and-Play Barcode Scanner
A streamlined barcode scanning application with web interface
"""

import gradio as gr
import json
import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
import uuid

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleBarcodeScanner:
    def __init__(self, db_path="barcode_scans.db"):
        self.db_path = db_path
        self.device_id = self.generate_device_id()
        self.init_database()
        logger.info(f"Scanner initialized with device ID: {self.device_id}")
    
    def generate_device_id(self):
        """Generate a unique device ID"""
        return f"scanner-{str(uuid.uuid4())[:8]}"
    
    def init_database(self):
        """Initialize SQLite database for storing scans"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS barcode_scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    barcode TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    quantity INTEGER DEFAULT 1,
                    notes TEXT
                )
            ''')
            conn.commit()
    
    def save_scan(self, barcode, quantity=1, notes=""):
        """Save a barcode scan to the database"""
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO barcode_scans (device_id, barcode, timestamp, quantity, notes)
                VALUES (?, ?, ?, ?, ?)
            ''', (self.device_id, barcode, timestamp, quantity, notes))
            conn.commit()
        
        logger.info(f"Saved scan: {barcode} (qty: {quantity})")
        return timestamp
    
    def get_recent_scans(self, limit=20):
        """Get recent barcode scans"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT barcode, timestamp, quantity, notes
                FROM barcode_scans
                WHERE device_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (self.device_id, limit))
            return cursor.fetchall()
    
    def get_scan_stats(self):
        """Get scanning statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_scans,
                    COUNT(DISTINCT barcode) as unique_barcodes,
                    MAX(timestamp) as last_scan
                FROM barcode_scans
                WHERE device_id = ?
            ''', (self.device_id,))
            return cursor.fetchone()
    
    def export_scans(self, format="json"):
        """Export scans to JSON or CSV"""
        scans = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT barcode, timestamp, quantity, notes
                FROM barcode_scans
                WHERE device_id = ?
                ORDER BY timestamp DESC
            ''', (self.device_id,))
            
            for row in cursor.fetchall():
                scans.append({
                    "barcode": row[0],
                    "timestamp": row[1],
                    "quantity": row[2],
                    "notes": row[3]
                })
        
        if format == "json":
            return json.dumps(scans, indent=2)
        elif format == "csv":
            csv_content = "Barcode,Timestamp,Quantity,Notes\n"
            for scan in scans:
                csv_content += f"{scan['barcode']},{scan['timestamp']},{scan['quantity']},\"{scan['notes']}\"\n"
            return csv_content
        
        return str(scans)

# Initialize the scanner
scanner = SimpleBarcodeScanner()

def process_barcode(barcode, quantity=1, notes=""):
    """Process a barcode scan"""
    if not barcode or not barcode.strip():
        return "❌ Please enter a barcode."
    
    barcode = barcode.strip()
    
    try:
        # Validate quantity
        if quantity is None or quantity < 1:
            quantity = 1
        
        # Save the scan
        timestamp = scanner.save_scan(barcode, int(quantity), notes)
        
        return f"""✅ Barcode Scanned Successfully!

**Barcode:** `{barcode}`
**Quantity:** {quantity}
**Timestamp:** {timestamp}
**Notes:** {notes if notes else 'None'}

Scan saved to local database."""
        
    except Exception as e:
        logger.error(f"Error processing barcode: {e}")
        return f"❌ Error processing barcode: {str(e)}"

def get_recent_scans_display():
    """Get formatted recent scans for display"""
    try:
        scans = scanner.get_recent_scans(10)
        
        if not scans:
            return "📋 **RECENT SCANS**\n\nNo scans found."
        
        display_text = "📋 **RECENT SCANS**\n\n"
        
        for i, (barcode, timestamp, quantity, notes) in enumerate(scans, 1):
            display_text += f"**{i}.** `{barcode}`\n"
            display_text += f"   • Time: {timestamp}\n"
            display_text += f"   • Qty: {quantity}\n"
            if notes:
                display_text += f"   • Notes: {notes}\n"
            display_text += "\n"
        
        return display_text
        
    except Exception as e:
        logger.error(f"Error getting recent scans: {e}")
        return f"❌ Error: {str(e)}"

def get_scanner_stats():
    """Get scanner statistics"""
    try:
        stats = scanner.get_scan_stats()
        
        if not stats:
            return "📊 **SCANNER STATISTICS**\n\nNo data available."
        
        total_scans, unique_barcodes, last_scan = stats
        
        return f"""📊 **SCANNER STATISTICS**

**Total Scans:** {total_scans or 0}
**Unique Barcodes:** {unique_barcodes or 0}
**Last Scan:** {last_scan or 'Never'}
**Device ID:** {scanner.device_id}
**Database:** {scanner.db_path}"""
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return f"❌ Error: {str(e)}"

def export_data(format_choice):
    """Export scan data"""
    try:
        data = scanner.export_scans(format_choice.lower())
        
        # Save to file
        filename = f"barcode_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_choice.lower()}"
        filepath = Path(filename)
        
        with open(filepath, 'w') as f:
            f.write(data)
        
        return f"""✅ **Export Complete**

**Format:** {format_choice}
**File:** {filename}
**Size:** {len(data)} characters

Data has been saved to: `{filepath.absolute()}`"""
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return f"❌ Export failed: {str(e)}"

def clear_all_data():
    """Clear all scan data (with confirmation)"""
    try:
        with sqlite3.connect(scanner.db_path) as conn:
            cursor = conn.execute('DELETE FROM barcode_scans WHERE device_id = ?', (scanner.device_id,))
            deleted_count = cursor.rowcount
            conn.commit()
        
        return f"""🗑️ **Data Cleared**

**Deleted:** {deleted_count} scan records
**Device:** {scanner.device_id}

All scan data has been permanently removed."""
        
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return f"❌ Error clearing data: {str(e)}"

# Create Gradio interface
with gr.Blocks(title="Simple Barcode Scanner", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 📱 Simple Barcode Scanner")
    gr.Markdown("*Plug-and-play barcode scanning with local storage*")
    
    with gr.Row():
        # Left column - Scanning
        with gr.Column():
            gr.Markdown("## 🔍 Scan Barcode")
            
            with gr.Row():
                barcode_input = gr.Textbox(
                    label="Barcode", 
                    placeholder="Scan or enter barcode here",
                    scale=3
                )
                quantity_input = gr.Number(
                    label="Quantity", 
                    value=1, 
                    minimum=1,
                    scale=1
                )
            
            notes_input = gr.Textbox(
                label="Notes (optional)", 
                placeholder="Add any notes about this scan",
                max_lines=2
            )
            
            with gr.Row():
                scan_button = gr.Button("🔍 Scan Barcode", variant="primary", scale=2)
                clear_button = gr.Button("🗑️ Clear", scale=1)
            
            scan_output = gr.Markdown("Ready to scan barcodes...")
            
        # Right column - History and Stats
        with gr.Column():
            gr.Markdown("## 📊 Scanner Dashboard")
            
            with gr.Row():
                refresh_button = gr.Button("🔄 Refresh", scale=1)
                stats_button = gr.Button("📊 Stats", scale=1)
                export_button = gr.Button("💾 Export", scale=1)
            
            # Export options (initially hidden)
            with gr.Row():
                export_format = gr.Radio(
                    choices=["JSON", "CSV"], 
                    value="JSON", 
                    label="Export Format",
                    scale=2
                )
                export_confirm = gr.Button("📁 Download", scale=1)
            
            dashboard_output = gr.Markdown("Click 'Refresh' to see recent scans...")
            
            # Data management
            with gr.Accordion("⚙️ Data Management", open=False):
                with gr.Row():
                    clear_all_button = gr.Button("🗑️ Clear All Data", variant="stop")
                
                data_management_output = gr.Markdown("")
    
    # Event handlers
    scan_button.click(
        fn=process_barcode,
        inputs=[barcode_input, quantity_input, notes_input],
        outputs=[scan_output]
    ).then(
        fn=get_recent_scans_display,
        inputs=[],
        outputs=[dashboard_output]
    )
    
    clear_button.click(
        fn=lambda: ("", 1, ""),
        outputs=[barcode_input, quantity_input, notes_input]
    )
    
    refresh_button.click(
        fn=get_recent_scans_display,
        outputs=[dashboard_output]
    )
    
    stats_button.click(
        fn=get_scanner_stats,
        outputs=[dashboard_output]
    )
    
    export_confirm.click(
        fn=export_data,
        inputs=[export_format],
        outputs=[data_management_output]
    )
    
    clear_all_button.click(
        fn=clear_all_data,
        outputs=[data_management_output]
    )
    
    # Auto-focus on barcode input
    barcode_input.focus()

if __name__ == "__main__":
    print(f"🚀 Starting Simple Barcode Scanner...")
    print(f"📱 Device ID: {scanner.device_id}")
    print(f"💾 Database: {scanner.db_path}")
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 7860))
    
    try:
        app.launch(
            server_name="0.0.0.0",
            server_port=port,
            share=False,
            show_tips=True
        )
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("🔄 Trying alternative port...")
        app.launch(server_port=port+1)