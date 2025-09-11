"""
API endpoints for Raspberry Pi device notifications and status updates.
This module provides FastAPI endpoints for device communication.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, status
from pydantic import BaseModel
from typing import Dict, Optional, List
import logging
from datetime import datetime, timezone
import json

# Set up logging
logger = logging.getLogger(__name__)

# Router for device notifications
router = APIRouter(
    prefix="/api/pi-device",
    tags=["pi-device"],
    responses={404: {"description": "Not found"}},
)

# In-memory storage for device status (in a real app, use a database)
device_status_store: Dict[str, dict] = {}

class DeviceHeartbeat(BaseModel):
    """Model for device heartbeat data"""
    device_id: str
    status: str = "online"
    timestamp: Optional[datetime] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None

class DeviceNotification(BaseModel):
    """Model for device notifications"""
    device_id: str
    message: str
    message_type: str
    timestamp: Optional[datetime] = None
    data: Optional[dict] = None

@router.post("/heartbeat", status_code=status.HTTP_200_OK)
async def receive_heartbeat(heartbeat: DeviceHeartbeat):
    """
    Receive and process device heartbeat
    
    Args:
        heartbeat: Device heartbeat data
        
    Returns:
        dict: Status message
    """
    try:
        # Update timestamp if not provided
        if not heartbeat.timestamp:
            heartbeat.timestamp = datetime.now(timezone.utc)
            
        # Store the heartbeat
        device_id = heartbeat.device_id
        device_status_store[device_id] = {
            "last_seen": heartbeat.timestamp.isoformat(),
            "status": heartbeat.status,
            "ip_address": heartbeat.ip_address,
            "mac_address": heartbeat.mac_address
        }
        
        logger.info(f"💓 Heartbeat received from {device_id} - Status: {heartbeat.status}")
        
        return {
            "status": "success",
            "message": f"Heartbeat received from {device_id}",
            "timestamp": heartbeat.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing heartbeat: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing heartbeat: {str(e)}"
        )

@router.post("/notification", status_code=status.HTTP_200_OK)
async def receive_notification(notification: DeviceNotification):
    """
    Receive and process device notifications
    
    Args:
        notification: Device notification data
        
    Returns:
        dict: Status message
    """
    try:
        # Update timestamp if not provided
        if not notification.timestamp:
            notification.timestamp = datetime.now(timezone.utc)
            
        logger.info(
            f"📢 Notification from {notification.device_id} "
            f"({notification.message_type}): {notification.message}"
        )
        
        # Here you would typically process the notification,
        # e.g., store it in a database, forward it, etc.
        
        return {
            "status": "success",
            "message": "Notification received",
            "notification_id": f"notif_{int(notification.timestamp.timestamp())}",
            "timestamp": notification.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing notification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing notification: {str(e)}"
        )

@router.get("/status/{device_id}", response_model=dict)
async def get_device_status(device_id: str):
    """
    Get the current status of a device
    
    Args:
        device_id: ID of the device to check
        
    Returns:
        dict: Device status information
    """
    if device_id not in device_status_store:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No status found for device {device_id}"
        )
        
    return {
        "device_id": device_id,
        **device_status_store[device_id]
    }

def create_pi_notification_endpoint():
    """
    Create and return the FastAPI router for device notifications
    
    Returns:
        APIRouter: Configured FastAPI router
    """
    return router

# Example usage in a FastAPI app:
# from fastapi import FastAPI
# from .api.pi_device_notification import create_pi_notification_endpoint
# 
# app = FastAPI()
# app.include_router(create_pi_notification_endpoint())
