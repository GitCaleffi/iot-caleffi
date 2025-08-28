"""
Auto Retry Manager - Handles automatic message retry and connection recovery
Monitors device connection state and automatically sends queued messages
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from threading import Lock, Event

from database.local_storage import LocalStorage
from utils.connection_manager import ConnectionManager
from utils.fast_config_manager import get_config, get_device_status

logger = logging.getLogger(__name__)

class AutoRetryManager:
    """Manages automatic retry of failed messages when devices reconnect"""
    
    def __init__(self):
        self.local_db = LocalStorage()
        self.connection_manager = get_connection_manager()
        
        # Threading components
        self.retry_thread = None
        self.stop_event = Event()
        self.retry_lock = Lock()
        
        # State tracking
        self.last_device_state = {}
        self.retry_interval = 10  # seconds
        self.max_retry_attempts = 5
        self.batch_size = 20
        
        # Connection state callbacks
        self.connection_callbacks = []
        
        # Start monitoring
        self.start_monitoring()
    
    def start_monitoring(self):
        """Start background monitoring for device reconnections"""
        if self.retry_thread is None or not self.retry_thread.is_alive():
            self.stop_event.clear()
            self.retry_thread = threading.Thread(
                target=self._monitor_and_retry,
                daemon=True,
                name="AutoRetryManager"
            )
            self.retry_thread.start()
            logger.info("🔄 Auto retry manager started")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self.stop_event.set()
        if self.retry_thread and self.retry_thread.is_alive():
            self.retry_thread.join(timeout=5)
        logger.info("⏹️ Auto retry manager stopped")
    
    def add_connection_callback(self, callback: Callable[[bool], None]):
        """Add callback to be called when connection state changes"""
        self.connection_callbacks.append(callback)
    
    def _monitor_and_retry(self):
        """Main monitoring loop"""
        logger.info("🔍 Starting connection monitoring and auto-retry")
        
        while not self.stop_event.wait(self.retry_interval):
            try:
                self._check_connection_changes()
                self._process_unsent_messages()
            except Exception as e:
                logger.error(f"❌ Auto retry error: {e}")
    
    def _check_connection_changes(self):
        """Check for device connection state changes"""
        try:
            current_device_state = get_device_status()
            
            # Check if state changed
            if self.last_device_state.get('connected') != current_device_state:
                logger.info(f"📡 Device connection state changed: {current_device_state}")
                
                # Update state
                self.last_device_state = {
                    'connected': current_device_state,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Notify callbacks
                for callback in self.connection_callbacks:
                    try:
                        callback(current_device_state)
                    except Exception as e:
                        logger.error(f"❌ Connection callback error: {e}")
                
                # If device reconnected, trigger immediate retry
                if current_device_state:
                    logger.info("🔄 Device reconnected - triggering immediate message retry")
                    self._process_unsent_messages(immediate=True)
                    
        except Exception as e:
            logger.error(f"❌ Connection state check error: {e}")
    
    def _process_unsent_messages(self, immediate=False):
        """Process unsent messages if device is connected"""
        try:
            # Check if device is connected
            if not get_device_status():
                return
            
            # Get unsent messages
            unsent_messages = self.local_db.get_unsent_messages(limit=self.batch_size)
            
            if not unsent_messages:
                return
            
            logger.info(f"🔄 Processing {len(unsent_messages)} unsent messages")
            
            processed_count = 0
            failed_count = 0
            
            for message in unsent_messages:
                try:
                    message_id = message.get('id')
                    device_id = message.get('device_id')
                    message_json = message.get('message_json')
                    
                    if not all([message_id, device_id, message_json]):
                        logger.warning(f"⚠️ Invalid message format: {message}")
                        continue
                    
                    # Parse message data
                    try:
                        message_data = json.loads(message_json)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Invalid JSON in message {message_id}: {e}")
                        # Remove invalid message
                        self.local_db.remove_unsent_message(message_id)
                        continue
                    
                    # Attempt to send message
                    success = self._send_message_retry(device_id, message_data)
                    
                    if success:
                        # Remove from unsent messages
                        self.local_db.remove_unsent_message(message_id)
                        processed_count += 1
                        logger.info(f"✅ Sent unsent message {message_id}")
                    else:
                        failed_count += 1
                        
                        # Update retry count
                        retry_count = message.get('retry_count', 0) + 1
                        if retry_count >= self.max_retry_attempts:
                            logger.warning(f"⚠️ Max retries reached for message {message_id}, removing")
                            self.local_db.remove_unsent_message(message_id)
                        else:
                            # Update retry count in database
                            self.local_db.update_unsent_message_retry_count(message_id, retry_count)
                    
                    # Small delay between messages to avoid overwhelming
                    if not immediate:
                        time.sleep(0.1)
                        
                except Exception as e:
                    logger.error(f"❌ Error processing message {message.get('id', 'unknown')}: {e}")
                    failed_count += 1
            
            if processed_count > 0 or failed_count > 0:
                logger.info(f"📊 Message retry summary: {processed_count} sent, {failed_count} failed")
                
        except Exception as e:
            logger.error(f"❌ Unsent message processing error: {e}")
    
    def _send_message_retry(self, device_id: str, message_data: Dict) -> bool:
        """Attempt to send a single message"""
        try:
            # Extract message components
            barcode = message_data.get('barcode')
            quantity = message_data.get('quantity', 1)
            message_type = message_data.get('messageType', 'barcode_scan')
            
            if not barcode:
                logger.error(f"❌ No barcode in message data: {message_data}")
                return False
            
            # Use connection manager to send
            success, status_message = self.connection_manager.send_message_with_retry(
                device_id=device_id,
                barcode=barcode,
                quantity=quantity,
                message_type=message_type
            )
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Message send retry error: {e}")
            return False
    
    def force_retry_all(self) -> Dict[str, int]:
        """Force retry of all unsent messages"""
        logger.info("🔄 Force retrying all unsent messages")
        
        try:
            # Get all unsent messages
            unsent_messages = self.local_db.get_unsent_messages(limit=1000)
            
            if not unsent_messages:
                return {"total": 0, "sent": 0, "failed": 0}
            
            sent_count = 0
            failed_count = 0
            
            for message in unsent_messages:
                try:
                    message_id = message.get('id')
                    device_id = message.get('device_id')
                    message_json = message.get('message_json')
                    
                    if not all([message_id, device_id, message_json]):
                        continue
                    
                    message_data = json.loads(message_json)
                    success = self._send_message_retry(device_id, message_data)
                    
                    if success:
                        self.local_db.remove_unsent_message(message_id)
                        sent_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"❌ Force retry error for message {message.get('id')}: {e}")
                    failed_count += 1
            
            result = {
                "total": len(unsent_messages),
                "sent": sent_count,
                "failed": failed_count
            }
            
            logger.info(f"📊 Force retry completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Force retry all error: {e}")
            return {"total": 0, "sent": 0, "failed": 0, "error": str(e)}
    
    def get_status(self) -> Dict:
        """Get current retry manager status"""
        try:
            unsent_count = len(self.local_db.get_unsent_messages(limit=1000))
            
            return {
                "monitoring_active": self.retry_thread and self.retry_thread.is_alive(),
                "device_connected": get_device_status(),
                "unsent_messages_count": unsent_count,
                "last_device_state": self.last_device_state,
                "retry_interval": self.retry_interval,
                "max_retry_attempts": self.max_retry_attempts
            }
            
        except Exception as e:
            return {"error": str(e)}

# Global instance
_auto_retry_manager = None
_manager_lock = Lock()

def get_auto_retry_manager() -> AutoRetryManager:
    """Get global auto retry manager instance"""
    global _auto_retry_manager
    
    if _auto_retry_manager is None:
        with _manager_lock:
            if _auto_retry_manager is None:
                _auto_retry_manager = AutoRetryManager()
    
    return _auto_retry_manager

def start_auto_retry():
    """Start auto retry monitoring"""
    manager = get_auto_retry_manager()
    manager.start_monitoring()

def stop_auto_retry():
    """Stop auto retry monitoring"""
    global _auto_retry_manager
    if _auto_retry_manager:
        _auto_retry_manager.stop_monitoring()
