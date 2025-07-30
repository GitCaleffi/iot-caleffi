#!/usr/bin/env python3
"""
Notification Service for Device Registration
Handles sending notifications about device registration status
"""

import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
import sys

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from api.api_client import ApiClient

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.api_client = ApiClient()
        
    def send_device_registration_notification(self, device_id, test_barcode, success=True):
        """
        Send device registration notification
        Since the direct notifications endpoint is not available via POST,
        we'll use the existing API structure to send notifications
        """
        try:
            # Format the message as requested
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            if success:
                message = "Registration successful! You're all set to get started."
                status = "success"
            else:
                message = "Registration failed. Please try again."
                status = "failed"
            
            # Try to send via the existing deviceRegistered endpoint with notification flag
            endpoint = f"{self.api_client.api_base_url}/raspberry/saveDeviceId"
            headers = {
                "Content-Type": "application/json",
                "Authorization": self.api_client.auth_token
            }
            
            # Create a notification payload that includes the registration message
            notification_payload = {
                "scannedBarcode": device_id,
                "notificationType": "device_registration",
                "notificationMessage": message,
                "notificationDate": current_date,
                "testBarcode": test_barcode,
                "registrationStatus": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"Sending registration notification for device {device_id}")
            response = requests.post(endpoint, headers=headers, json=notification_payload, timeout=15)
            
            try:
                data = response.json()
                
                # Log the notification details
                self._log_notification(device_id, message, current_date, status, data)
                
                return {
                    'success': True,
                    'message': f'Registration notification processed: {message}',
                    'date': current_date,
                    'api_response': data,
                    'notification_details': {
                        'device_id': device_id,
                        'message': message,
                        'date': current_date,
                        'status': status,
                        'test_barcode': test_barcode
                    }
                }
                
            except json.JSONDecodeError:
                # Even if JSON parsing fails, we can still log the notification
                self._log_notification(device_id, message, current_date, status, {"raw_response": response.text})
                
                return {
                    'success': True,
                    'message': f'Registration notification sent: {message}',
                    'date': current_date,
                    'notification_details': {
                        'device_id': device_id,
                        'message': message,
                        'date': current_date,
                        'status': status,
                        'test_barcode': test_barcode
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to send registration notification: {str(e)}")
            
            # Still log the notification locally even if sending fails
            self._log_notification(device_id, message, current_date, status, {"error": str(e)})
            
            return {
                'success': False,
                'message': f'Notification failed but logged locally: {str(e)}',
                'notification_details': {
                    'device_id': device_id,
                    'message': message,
                    'date': current_date,
                    'status': status,
                    'test_barcode': test_barcode
                }
            }
    
    def _log_notification(self, device_id, message, date, status, api_response):
        """Log notification details to local database"""
        try:
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            # Create notifications table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT,
                    message TEXT,
                    date TEXT,
                    status TEXT,
                    timestamp DATETIME,
                    api_response TEXT
                )
            ''')
            
            # Insert notification record
            cursor.execute('''
                INSERT INTO notifications (device_id, message, date, status, timestamp, api_response)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (device_id, message, date, status, 
                  datetime.now(timezone.utc).isoformat(), 
                  json.dumps(api_response)))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Notification logged for device {device_id}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to log notification: {str(e)}")
    
    def get_notifications(self, device_id=None, limit=10):
        """Get notification history"""
        try:
            import sqlite3
            conn = sqlite3.connect(project_root / 'barcode_scans.db')
            cursor = conn.cursor()
            
            if device_id:
                cursor.execute('''
                    SELECT device_id, message, date, status, timestamp
                    FROM notifications 
                    WHERE device_id = ?
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (device_id, limit))
            else:
                cursor.execute('''
                    SELECT device_id, message, date, status, timestamp
                    FROM notifications 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            notifications = []
            for row in cursor.fetchall():
                notifications.append({
                    'device_id': row[0],
                    'message': row[1],
                    'date': row[2],
                    'status': row[3],
                    'timestamp': row[4]
                })
            
            conn.close()
            return notifications
            
        except Exception as e:
            logger.error(f"Failed to get notifications: {str(e)}")
            return []
    
    def create_registration_success_message(self, device_id, test_barcode):
        """Create a formatted registration success message"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        return {
            'message': 'Registration successful! You\'re all set to get started.',
            'date': current_date,
            'device_id': device_id,
            'test_barcode': test_barcode,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'formatted_display': f"""
**Registration successful! You're all set to get started.**

**{current_date}**

Device ID: {device_id}
Test Barcode: {test_barcode}
Status: Successfully registered and ready for use
"""
        }

def main():
    """Test the notification service"""
    service = NotificationService()
    
    # Test notification
    device_id = "test_device_notification_002"
    test_barcode = f"TEST_{device_id}_{datetime.now().strftime('%Y%m%d')}"
    
    print("Testing notification service...")
    
    # Send success notification
    result = service.send_device_registration_notification(device_id, test_barcode, success=True)
    print(f"Notification result: {json.dumps(result, indent=2)}")
    
    # Create formatted message
    formatted_message = service.create_registration_success_message(device_id, test_barcode)
    print(f"\nFormatted message:")
    print(formatted_message['formatted_display'])
    
    # Get notification history
    notifications = service.get_notifications(limit=5)
    print(f"\nRecent notifications:")
    for notification in notifications:
        print(f"- {notification['date']}: {notification['message']} (Device: {notification['device_id']})")

if __name__ == "__main__":
    main()