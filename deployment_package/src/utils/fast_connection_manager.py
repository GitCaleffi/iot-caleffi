"""
Fast Connection Manager with immediate LAN disconnection detection
"""
import os
import time
import socket
import fcntl
import struct
import logging
import netifaces
from typing import Dict, List, Optional, Tuple, Set
from threading import RLock, Thread, Event

logger = logging.getLogger(__name__)

class FastConnectionManager:
    """
    High-performance connection manager with immediate LAN disconnection detection.
    Uses direct network interface monitoring for instant response to network changes.
    """
    
    def __init__(self):
        self._lock = RLock()
        self._stop_event = Event()
        self._interface_status: Dict[str, bool] = {}
        self._last_check_time = 0
        self._last_known_online = False
        self._monitor_thread = None
        self._check_interval = 0.5  # Check every 500ms for immediate detection
        
        # Start monitoring thread
        self._start_monitor()
    
    def _start_monitor(self):
        """Start the network monitoring thread"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._monitor_thread = Thread(
            target=self._monitor_network,
            name="NetworkMonitor",
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop(self):
        """Stop the connection manager"""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
    
    def _monitor_network(self):
        """Background thread that monitors network interfaces"""
        while not self._stop_event.is_set():
            try:
                self._check_interfaces()
            except Exception as e:
                logger.error(f"Network monitor error: {e}", exc_info=True)
            
            # Small sleep to prevent CPU overload
            self._stop_event.wait(self._check_interval)
    
    def _check_interfaces(self):
        """Check status of all network interfaces"""
        current_status: Dict[str, bool] = {}
        
        # Get all non-loopback interfaces
        interfaces = [
            iface for iface in netifaces.interfaces() 
            if not iface.startswith(('lo', 'docker', 'br-', 'veth'))
        ]
        
        # Check each interface
        for iface in interfaces:
            try:
                # Check if interface is up
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    ifname = iface.encode('utf-8')
                    flags = struct.unpack('H', fcntl.ioctl(
                        s.fileno(),
                        0x8913,  # SIOCGIFFLAGS
                        struct.pack('256s', ifname[:15])
                    )[16:18])[0]
                    is_up = bool(flags & 0x1)  # IFF_UP flag
                
                # Check if interface has an IP address
                has_ip = False
                addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
                if addrs and addrs[0].get('addr') not in ('127.0.0.1', '0.0.0.0'):
                    has_ip = True
                
                current_status[iface] = is_up and has_ip
                
            except Exception as e:
                logger.debug(f"Could not check interface {iface}: {e}")
                current_status[iface] = False
        
        # Update status
        with self._lock:
            self._interface_status = current_status
            self._last_check_time = time.time()
    
    def is_online(self) -> bool:
        """
        Check if any network interface is up and has an IP address.
        Returns immediately with cached result.
        """
        with self._lock:
            return any(self._interface_status.values())
    
    def check_raspberry_pi_availability(self) -> bool:
        """
        Check if Raspberry Pi is available on the LAN.
        Returns immediately with cached result.
        """
        # If we're not even online, Pi can't be available
        if not self.is_online():
            return False
            
        # For now, just check if we're online
        # In a real implementation, this would check for Pi-specific services
        return True
    
    def get_connection_status(self) -> Dict[str, any]:
        """
        Get detailed connection status.
        
        Returns:
            Dict containing connection status information
        """
        with self._lock:
            return {
                'online': self.is_online(),
                'interfaces': self._interface_status,
                'last_check': self._last_check_time,
                'pi_available': self.check_raspberry_pi_availability()
            }

# Global instance
fast_connection_manager = FastConnectionManager()

def get_fast_connection_manager() -> FastConnectionManager:
    """Get the global fast connection manager instance"""
    return fast_connection_manager
