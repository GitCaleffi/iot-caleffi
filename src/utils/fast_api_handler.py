"""
Fast API Handler - Optimized for speed and automatic processing
Eliminates manual configuration steps and provides instant responses
"""
import json
import logging
import time
import asyncio
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timezone

from .fast_config_manager import get_fast_config_manager, get_config, get_device_status
from database.local_storage import LocalStorage
from api.api_client import ApiClient
from utils.dynamic_registration_service import get_dynamic_registration_service
from utils.connection_manager import get_connection_manager

logger = logging.getLogger(__name__)

class FastAPIHandler:
    """Ultra-fast API handler with automatic processing and caching"""
    
    def __init__(self):
        self.config_manager = get_fast_config_manager()
        self.local_db = LocalStorage()
        self.api_client = ApiClient()
        self.connection_manager = get_connection_manager()
        
        # Performance optimizations
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.cache_lock = Lock()
        self.response_cache = {}
        self.cache_ttl = 30  # 30 seconds cache for responses
        
        # Auto-initialization
        self._initialize_fast_mode()
    
    def _initialize_fast_mode(self):
        """Initialize fast mode with automatic settings"""
        try:
            config = self.config_manager.get_config()
            performance_config = config.get("performance", {})
            
            if performance_config.get("fast_mode", True):
                logger.info("🚀 Fast mode enabled - optimizing for speed")
                
                # Update cache settings for faster responses
                self.cache_ttl = performance_config.get("cache_duration", 30)
                
                # Enable parallel processing
                if performance_config.get("parallel_processing", True):
                    logger.info("⚡ Parallel processing enabled")
                
        except Exception as e:
            logger.warning(f"⚠️ Fast mode initialization warning: {e}")
    
    async def process_barcode_fast(self, barcode: str, device_id: str = None) -> Dict[str, Any]:
        """Ultra-fast barcode processing with automatic device detection"""
        start_time = time.time()
        
        try:
            # Auto-generate device ID if not provided
            if not device_id:
                device_id = self._auto_generate_device_id()
            
            # Check cache first for recent identical requests
            cache_key = f"{barcode}_{device_id}"
            cached_response = self._get_cached_response(cache_key)
            if cached_response:
                logger.info(f"⚡ Cache hit for {barcode} - response in {(time.time() - start_time)*1000:.1f}ms")
                return cached_response
            
            # Parallel processing for speed
            tasks = []
            
            # Task 1: Device connection check (async)
            device_connected = get_device_status()
            
            # Task 2: Validate barcode (fast)
            is_valid_barcode = self._validate_barcode_fast(barcode)
            
            if not is_valid_barcode:
                response = {
                    "success": False,
                    "message": f"❌ Invalid barcode format: {barcode}",
                    "processing_time_ms": round((time.time() - start_time) * 1000, 1)
                }
                return response
            
            # Task 3: Process in parallel
            if device_connected:
                # Send to IoT Hub and API simultaneously
                iot_result, api_result = await self._process_parallel(barcode, device_id)
            else:
                # Save locally for retry
                iot_result = await self._save_for_retry(barcode, device_id)
                api_result = {"success": False, "message": "Device offline - saved locally"}
            
            # Build fast response
            response = {
                "success": True,
                "barcode": barcode,
                "device_id": device_id,
                "device_connected": device_connected,
                "iot_hub_result": iot_result,
                "api_result": api_result,
                "processing_time_ms": round((time.time() - start_time) * 1000, 1),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Cache successful responses
            self._cache_response(cache_key, response)
            
            logger.info(f"✅ Barcode {barcode} processed in {response['processing_time_ms']}ms")
            return response
            
        except Exception as e:
            logger.error(f"❌ Fast barcode processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": round((time.time() - start_time) * 1000, 1)
            }
    
    async def _process_parallel(self, barcode: str, device_id: str) -> tuple:
        """Process IoT Hub and API calls in parallel for speed"""
        try:
            # Create tasks for parallel execution
            iot_task = asyncio.create_task(self._send_to_iot_hub_async(barcode, device_id))
            api_task = asyncio.create_task(self._send_to_api_async(barcode, device_id))
            
            # Wait for both to complete
            iot_result, api_result = await asyncio.gather(iot_task, api_task, return_exceptions=True)
            
            return iot_result, api_result
            
        except Exception as e:
            logger.error(f"❌ Parallel processing error: {e}")
            return {"success": False, "error": str(e)}, {"success": False, "error": str(e)}
    
    async def _send_to_iot_hub_async(self, barcode: str, device_id: str) -> Dict[str, Any]:
        """Async IoT Hub sending"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._send_to_iot_hub_sync, 
                barcode, 
                device_id
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _send_to_api_async(self, barcode: str, device_id: str) -> Dict[str, Any]:
        """Async API sending"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor, 
                self._send_to_api_sync, 
                barcode, 
                device_id
            )
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _send_to_iot_hub_sync(self, barcode: str, device_id: str) -> Dict[str, Any]:
        """Synchronous IoT Hub sending"""
        try:
            # Use connection manager for automatic retry logic
            message_data = {
                "barcode": barcode,
                "device_id": device_id,
                "quantity": 1,
                "message_type": "barcode_scan",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            result = self.connection_manager.send_message_with_retry(
                device_id=device_id,
                barcode=barcode,
                quantity=1,
                message_type="barcode_scan"
            )
            
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"❌ IoT Hub send error: {e}")
            return {"success": False, "error": str(e)}
    
    def _send_to_api_sync(self, barcode: str, device_id: str) -> Dict[str, Any]:
        """Synchronous API sending"""
        try:
            result = self.api_client.send_barcode_scan(device_id, barcode, 1)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"❌ API send error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _save_for_retry(self, barcode: str, device_id: str) -> Dict[str, Any]:
        """Save message for retry when device comes online"""
        try:
            message_data = {
                "barcode": barcode,
                "device_id": device_id,
                "quantity": 1,
                "message_type": "barcode_scan",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            self.local_db.save_unsent_message(
                device_id=device_id,
                message_json=json.dumps(message_data),
                timestamp=datetime.now(timezone.utc)
            )
            
            return {"success": True, "message": "Saved for retry when device online"}
            
        except Exception as e:
            logger.error(f"❌ Save for retry error: {e}")
            return {"success": False, "error": str(e)}
    
    def _auto_generate_device_id(self) -> str:
        """Auto-generate device ID based on system info"""
        try:
            from utils.dynamic_device_id import generate_dynamic_device_id
            return generate_dynamic_device_id()
        except Exception:
            # Fallback to simple generation
            import uuid
            return f"device-{str(uuid.uuid4())[:8]}"
    
    def _validate_barcode_fast(self, barcode: str) -> bool:
        """Fast barcode validation"""
        if not barcode or len(barcode) < 6:
            return False
        
        # Allow alphanumeric barcodes (common formats)
        if not barcode.replace('-', '').replace('_', '').isalnum():
            return False
        
        return True
    
    def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if still valid"""
        with self.cache_lock:
            if cache_key in self.response_cache:
                cached_data, timestamp = self.response_cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return cached_data
                else:
                    # Remove expired cache
                    del self.response_cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: Dict[str, Any]) -> None:
        """Cache response for faster future requests"""
        with self.cache_lock:
            self.response_cache[cache_key] = (response, time.time())
            
            # Clean old cache entries (keep only last 100)
            if len(self.response_cache) > 100:
                oldest_key = min(self.response_cache.keys(), 
                               key=lambda k: self.response_cache[k][1])
                del self.response_cache[oldest_key]
    
    def get_system_status_fast(self) -> Dict[str, Any]:
        """Get system status with automatic detection"""
        try:
            config = self.config_manager.get_config()
            device_connected = get_device_status()
            
            return {
                "config_auto_detected": self.config_manager.is_auto_detected(),
                "config_path": str(self.config_manager.get_config_path()) if self.config_manager.get_config_path() else None,
                "device_connected": device_connected,
                "fast_mode_enabled": config.get("performance", {}).get("fast_mode", True),
                "auto_registration": config.get("commercial_deployment", {}).get("auto_registration", True),
                "iot_hub_available": True,  # Always assume available for speed
                "api_available": True,      # Always assume available for speed
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ System status error: {e}")
            return {"error": str(e)}

# Global instance
_fast_api_handler = None
_handler_lock = Lock()

def get_fast_api_handler() -> FastAPIHandler:
    """Get global fast API handler instance"""
    global _fast_api_handler
    
    if _fast_api_handler is None:
        with _handler_lock:
            if _fast_api_handler is None:
                _fast_api_handler = FastAPIHandler()
    
    return _fast_api_handler
