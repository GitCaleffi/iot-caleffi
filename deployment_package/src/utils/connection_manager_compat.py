"""
Compatibility layer for FastConnectionManager to work with existing code
"""
import logging
from typing import Optional, Dict, Any
from .fast_connection_manager import get_fast_connection_manager

logger = logging.getLogger(__name__)

class ConnectionManagerCompat:
    """
    Compatibility wrapper that makes FastConnectionManager work with code
    expecting the old ConnectionManager interface.
    """
    
    def __init__(self):
        self.fast_cm = get_fast_connection_manager()
        self._last_iot_hub_check = 0
        self._last_pi_check = 0
        self._cached_pi_status = False
        
    def check_internet_connectivity(self) -> bool:
        """Check internet connectivity (compatibility method)"""
        return self.fast_cm.is_online()
    
    def is_online(self) -> bool:
        """Check if online (compatibility method)"""
        return self.fast_cm.is_online()
    
    def check_iot_hub_connectivity(self, *args, **kwargs) -> bool:
        """Check IoT Hub connectivity (compatibility method)"""
        # For now, just return online status
        # In a real implementation, this would check IoT Hub specifically
        return self.fast_cm.is_online()
    
    def check_raspberry_pi_availability(self, force_check: bool = False) -> bool:
        """Check Raspberry Pi availability (compatibility method)"""
        return self.fast_cm.check_raspberry_pi_availability()
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status (compatibility method)"""
        return self.fast_cm.get_connection_status()
    
    def send_message_with_retry(self, *args, **kwargs):
        """Send message with retry (compatibility method)"""
        # This would be implemented to work with the fast connection manager
        raise NotImplementedError("send_message_with_retry not yet implemented in compatibility layer")

# Global instance for compatibility
_connection_manager_compat = None

def get_connection_manager():
    """Get the global connection manager instance (compatibility function)"""
    global _connection_manager_compat
    if _connection_manager_compat is None:
        _connection_manager_compat = ConnectionManagerCompat()
    return _connection_manager_compat
