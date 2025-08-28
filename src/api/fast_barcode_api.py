"""
Optimized Barcode Scanner API with async support and caching
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Dict, List, Any, Optional, Callable
import aiohttp
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Import local modules
from database.local_storage import LocalStorage
from utils.connection_manager import ConnectionManager
from utils.dynamic_registration_service import get_dynamic_registration_service

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Barcode Scanner API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
local_db = LocalStorage()
connection_manager = get_connection_manager()
registration_service = get_dynamic_registration_service()

# Cache for API responses
response_cache = {}
CACHE_TTL = 5  # seconds

class BarcodeScanRequest(BaseModel):
    barcode: str
    device_id: str
    quantity: int = 1

class RegistrationRequest(BaseModel):
    device_id: str
    pi_ip: str

# Response models
class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None
    cached: bool = False
    timestamp: str = datetime.utcnow().isoformat()

# Decorator for caching responses
def cache_response(ttl: int = CACHE_TTL):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{str(kwargs)}"
            current_time = time.time()
            
            # Check cache
            if cache_key in response_cache:
                cached_time, cached_response = response_cache[cache_key]
                if current_time - cached_time < ttl:
                    response = cached_response.copy()
                    response["cached"] = True
                    return response
            
            # Call function and cache result
            result = await func(*args, **kwargs)
            response_cache[cache_key] = (current_time, result)
            return result
        return wrapper
    return decorator

# Middleware for request timing and error handling
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # Log slow requests
        if process_time > 1.0:  # Log requests slower than 1 second
            logger.warning(f"Slow request: {request.method} {request.url} took {process_time:.3f}s")
            
        return response
    except Exception as e:
        logger.error(f"API error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Internal server error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# Barcode scan endpoint
@app.post("/api/v1/scan", response_model=ApiResponse)
@cache_response(ttl=1)  # Short cache for scans
async def scan_barcode(request: BarcodeScanRequest):
    """Process a barcode scan with optimized performance"""
    start_time = time.time()
    
    try:
        # Check if device is online
        is_online = await connection_manager.is_online()
        
        # Prepare message
        message = {
            "device_id": request.device_id,
            "barcode": request.barcode,
            "quantity": request.quantity,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        
        if is_online:
            # Try to send to IoT Hub first
            try:
                hub_client = registration_service.get_hub_client()
                if hub_client:
                    await hub_client.send_message_async(json.dumps(message))
                    message["status"] = "sent"
                    return {
                        "success": True,
                        "message": "Barcode processed successfully",
                        "data": {"status": "sent_to_hub"}
                    }
            except Exception as e:
                logger.warning(f"Failed to send to IoT Hub: {e}")
                is_online = False
        
        # If offline or IoT Hub send failed, save locally
        if not is_online:
            local_db.save_unsent_message("barcode_scan", message)
            return {
                "success": True,
                "message": "Device offline - barcode saved locally",
                "data": {"status": "saved_locally"}
            }
            
    except Exception as e:
        logger.error(f"Barcode scan error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error processing barcode: {str(e)}"
        }
    finally:
        logger.info(f"Barcode scan processed in {(time.time() - start_time)*1000:.2f}ms")

# Device registration endpoint
@app.post("/api/v1/register", response_model=ApiResponse)
@cache_response(ttl=60)  # Cache registration responses longer
async def register_device(request: RegistrationRequest):
    """Register a new device with optimized performance"""
    try:
        # Check if device is already registered
        if registration_service.is_device_registered(request.device_id):
            return {
                "success": True,
                "message": "Device already registered",
                "data": {"registered": True, "device_id": request.device_id}
            }
        
        # Register device
        result = await registration_service.register_device_async(
            device_id=request.device_id,
            pi_ip=request.pi_ip
        )
        
        return {
            "success": True,
            "message": "Device registered successfully",
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Device registration error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error registering device: {str(e)}"
        }

# Get device status endpoint
@app.get("/api/v1/status/{device_id}", response_model=ApiResponse)
@cache_response(ttl=5)  # Short cache for status checks
async def get_device_status(device_id: str):
    """Get device status with optimized performance"""
    try:
        is_online = await connection_manager.is_online()
        is_pi_available = await connection_manager.check_raspberry_pi_availability()
        
        return {
            "success": True,
            "data": {
                "device_id": device_id,
                "online": is_online,
                "pi_available": is_pi_available,
                "last_seen": datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Status check error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Error checking status: {str(e)}"
        }

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "fast_barcode_api:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="info"
    )
