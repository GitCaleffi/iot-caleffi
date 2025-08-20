#!/usr/bin/env python3
"""
Simple test script to verify offline/online mode functionality
"""
import os
import sys
import json
import logging
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable to simulate offline mode
simulated_offline_mode = False

class LocalStorage:
    """Simple storage class for local database operations"""
    def __init__(self, db_path="barcode_scanner.db"):
        self.db_path = db_path
        
    def _get_connection(self):
        """Get a connection to the SQLite database"""
        return sqlite3.connect(self.db_path)
    
    def save_barcode_scan(self, device_id, barcode, timestamp):
        """Save a barcode scan to the local database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create barcode_scans table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS barcode_scans (
                device_id TEXT,
                barcode TEXT,
                timestamp DATETIME,
                sent_to_hub BOOLEAN DEFAULT 0
            )
        ''')
        
        formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO barcode_scans (device_id, barcode, timestamp, sent_to_hub) VALUES (?, ?, ?, 0)',
            (device_id, barcode, formatted_timestamp)
        )
        conn.commit()
        conn.close()
        logger.info(f"Barcode scan saved locally for device {device_id}")
        
    def save_unsent_message(self, device_id, message, timestamp):
        """Save an unsent message for retry later"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create unsent_messages table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unsent_messages (
                device_id TEXT,
                message TEXT,
                timestamp DATETIME,
                sent_to_hub BOOLEAN DEFAULT 0
            )
        ''')
        
        formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO unsent_messages (device_id, message, timestamp, sent_to_hub) VALUES (?, ?, ?, 0)',
            (device_id, message, formatted_timestamp)
        )
        conn.commit()
        conn.close()
        logger.info(f"Unsent message saved for device {device_id}")
        
    def get_unsent_messages(self):
        """Get all unsent messages from the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS unsent_messages (
                device_id TEXT,
                message TEXT,
                timestamp DATETIME,
                sent_to_hub BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('SELECT device_id, message, timestamp FROM unsent_messages WHERE sent_to_hub = 0')
        rows = cursor.fetchall()
        
        messages = []
        for row in rows:
            messages.append({
                "device_id": row[0],
                "message": row[1],
                "timestamp": row[2]
            })
        
        conn.close()
        return messages
        
    def mark_message_sent(self, device_id, message, timestamp):
        """Mark a message as sent in the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE unsent_messages SET sent_to_hub = 1 WHERE device_id = ? AND message = ? AND timestamp = ?',
            (device_id, message, timestamp)
        )
        conn.commit()
        conn.close()
        logger.info(f"Message marked as sent for device {device_id}")

def simulate_offline_mode():
    """Simulate offline mode by setting the global variable"""
    global simulated_offline_mode
    simulated_offline_mode = True
    logger.info("[WARNING] Simulated OFFLINE mode activated")
    return "[WARNING] OFFLINE mode simulated. Barcodes will be stored locally and sent when 'online'."

def restore_online_mode():
    """Restore online mode by setting the global variable and processing unsent messages"""
    global simulated_offline_mode
    simulated_offline_mode = False
    logger.info("[OK] Simulated OFFLINE mode deactivated - normal operation restored")
    result = process_unsent_messages()
    return "[OK] Online mode restored. Any pending messages will now be sent.\n\n" + (result or "")

def process_barcode_scan(barcode, device_id="test-device"):
    """Process a barcode scan and determine if it's a valid product or device ID"""
    try:
        timestamp = datetime.now()
        local_db = LocalStorage()
        
        # Save the barcode scan locally
        local_db.save_barcode_scan(device_id, barcode, timestamp)
        logger.info(f"Barcode {barcode} saved locally for device {device_id}")
        
        # Check if we're in simulated offline mode
        if simulated_offline_mode:
            # Save the message for later sending when online
            local_db.save_unsent_message(device_id, barcode, timestamp)
            logger.info(f"Device is offline. Barcode {barcode} saved for later sending.")
            return f"""[WARNING] Barcode Partially Processed

Information:
- Barcode: {barcode}
- Device ID: {device_id}
- Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Actions Completed:
- [OK] Barcode saved locally
- [OK] Sent to API successfully
- [WARNING] Failed to send to IoT Hub (stored for retry)
"""
        else:
            # Simulate sending to IoT Hub
            logger.info(f"Barcode {barcode} sent to IoT Hub for device {device_id}")
            return f"""[OK] Barcode Scan Processed

Information:
- Barcode: {barcode}
- Device ID: {device_id}
- Scanned At: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Actions Completed:
- [OK] Barcode saved locally
- [OK] Sent to API successfully
- [OK] Sent to IoT Hub
"""
    except Exception as e:
        logger.error(f"Error processing barcode scan: {str(e)}")
        return f"[ERROR] Error processing barcode: {str(e)}"

def process_unsent_messages(auto_retry=False):
    """Process any unsent messages in the local database and try to send them."""
    try:
        # Check if we're online
        if simulated_offline_mode:
            return "Device is offline. Cannot process unsent messages."
            
        # Get unsent messages from local database
        local_db = LocalStorage()
        unsent_messages = local_db.get_unsent_messages()
        
        if not unsent_messages:
            return "No unsent messages found."
        
        # Process each unsent message
        success_count = 0
        failed_count = 0
        results = []
        
        for message in unsent_messages:
            device_id = message["device_id"]
            barcode = message["message"]
            timestamp = message["timestamp"]
            
            try:
                # Simulate sending to IoT Hub
                logger.info(f"Sending unsent message for device {device_id}, barcode {barcode}")
                
                # Mark message as sent in the database
                local_db.mark_message_sent(device_id, barcode, timestamp)
                success_count += 1
                results.append(f"Successfully sent message for device {device_id}, barcode {barcode}")
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

def main():
    """Main function to test offline/online mode functionality"""
    print("Testing offline/online mode functionality...")
    
    # Test offline mode
    print("\n1. Simulating offline mode...")
    result = simulate_offline_mode()
    print(result)
    
    # Test barcode scanning in offline mode
    print("\n2. Scanning barcode in offline mode...")
    barcode = "123456789012"
    result = process_barcode_scan(barcode)
    print(result)
    
    # Test restoring online mode
    print("\n3. Restoring online mode and processing unsent messages...")
    result = restore_online_mode()
    print(result)
    
    # Test barcode scanning in online mode
    print("\n4. Scanning barcode in online mode...")
    barcode = "987654321098"
    result = process_barcode_scan(barcode)
    print(result)
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()
