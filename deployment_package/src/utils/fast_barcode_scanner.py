"""
Optimized Barcode Scanner with async support and offline handling
"""
import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, Optional, Any, List
import aiohttp

from database.local_storage import LocalStorage
from utils.connection_manager import ConnectionManager
from utils.dynamic_registration_service import get_dynamic_registration_service

logger = logging.getLogger(__name__)

class FastBarcodeScanner:
    """High-performance barcode scanner with offline support"""
    
    def __init__(self):
        self.local_db = LocalStorage()
        self.connection_manager = get_connection_manager()
        self.registration_service = get_dynamic_registration_service()
        self.session = None
        self.api_url = "http://localhost:8000"  # Default, can be configured
        
        # Performance tracking
        self.scan_count = 0
        self.avg_processing_time = 0
        self.last_scan_time = 0
        
    async def initialize(self):
        """Initialize async resources"""
        self.session = aiohttp.ClientSession()
        
    async def close(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
    
    async def process_barcode(self, barcode: str, device_id: str, quantity: int = 1) -> Dict[str, Any]:
        """
        Process a barcode scan with optimized performance and offline support
        
        Args:
            barcode: The scanned barcode
            device_id: Unique device identifier
            quantity: Quantity of items (default: 1)
            
        Returns:
            Dict containing scan result and status
        """
        start_time = time.time()
        self.scan_count += 1
        
        try:
            # Validate barcode
            if not self._validate_barcode(barcode):
                return self._create_error_response("Invalid barcode format")
                
            # Check if device is registered
            if not await self._ensure_device_registered(device_id):
                return self._create_error_response("Device not registered")
            
            # Prepare scan data
            scan_data = {
                "barcode": barcode,
                "device_id": device_id,
                "quantity": quantity,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Try to send to API first
            try:
                if await self.connection_manager.is_online():
                    async with self.session.post(
                        f"{self.api_url}/api/v1/scan",
                        json=scan_data,
                        timeout=2.0  # Short timeout for responsiveness
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            return self._process_scan_result(result, scan_data, start_time)
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"API request failed: {e}")
            
            # If we get here, save locally for later sync
            await self._save_scan_locally(scan_data)
            return self._create_success_response(
                "Scan saved locally (offline mode)",
                {"status": "saved_locally", "barcode": barcode}
            )
            
        except Exception as e:
            logger.error(f"Error processing barcode: {e}", exc_info=True)
            return self._create_error_response(f"Processing error: {str(e)}")
    
    async def _ensure_device_registered(self, device_id: str) -> bool:
        """Ensure device is registered, register if needed"""
        if self.registration_service.is_device_registered(device_id):
            return True
            
        try:
            # Try to register the device
            result = await self.registration_service.register_device_async(device_id)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Device registration failed: {e}")
            return False
    
    def _validate_barcode(self, barcode: str) -> bool:
        """Validate barcode format"""
        if not barcode or not isinstance(barcode, str):
            return False
        return 6 <= len(barcode) <= 20  # Basic length check
    
    async def _save_scan_locally(self, scan_data: Dict[str, Any]) -> None:
        """Save scan data to local storage for later sync"""
        try:
            self.local_db.save_unsent_message("barcode_scan", scan_data)
            logger.info(f"Saved scan locally: {scan_data['barcode']}")
        except Exception as e:
            logger.error(f"Failed to save scan locally: {e}")
    
    def _process_scan_result(self, result: Dict, scan_data: Dict, start_time: float) -> Dict[str, Any]:
        """Process API scan result and update metrics"""
        processing_time = (time.time() - start_time) * 1000  # ms
        
        # Update average processing time (exponential moving average)
        self.avg_processing_time = (
            0.8 * self.avg_processing_time + 
            0.2 * processing_time
        )
        
        self.last_scan_time = time.time()
        
        logger.info(
            f"Processed barcode {scan_data['barcode']} in {processing_time:.1f}ms "
            f"(avg: {self.avg_processing_time:.1f}ms)"
        )
        
        return {
            "success": True,
            "message": result.get("message", "Scan processed"),
            "data": {
                **result.get("data", {}),
                "processing_time_ms": processing_time,
                "scan_count": self.scan_count
            }
        }
    
    @staticmethod
    def _create_success_response(message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Create a standardized success response"""
        return {
            "success": True,
            "message": message,
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def _create_error_response(message: str, error_code: str = "processing_error") -> Dict[str, Any]:
        """Create a standardized error response"""
        return {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def sync_pending_scans(self) -> Dict[str, Any]:
        """Sync any pending scans with the server"""
        try:
            pending_scans = self.local_db.get_unsent_messages("barcode_scan")
            if not pending_scans:
                return {"success": True, "message": "No pending scans to sync"}
            
            success_count = 0
            for scan in pending_scans:
                try:
                    async with self.session.post(
                        f"{self.api_url}/api/v1/scan",
                        json=scan,
                        timeout=5.0
                    ) as response:
                        if response.status == 200:
                            self.local_db.delete_unsent_message(scan["id"])
                            success_count += 1
                except Exception as e:
                    logger.warning(f"Failed to sync scan {scan.get('id')}: {e}")
            
            return {
                "success": True,
                "message": f"Synced {success_count}/{len(pending_scans)} scans",
                "data": {
                    "synced": success_count,
                    "pending": len(pending_scans) - success_count
                }
            }
            
        except Exception as e:
            logger.error(f"Error syncing pending scans: {e}")
            return {
                "success": False,
                "message": f"Sync failed: {str(e)}"
            }

# Singleton instance
fast_scanner = FastBarcodeScanner()

# Initialize on import
async def init_fast_scanner():
    """Initialize the fast scanner instance"""
    await fast_scanner.initialize()

# Start the initialization
asyncio.create_task(init_fast_scanner())
