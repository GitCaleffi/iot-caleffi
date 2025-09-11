"""
Network discovery utilities for finding and managing devices on the local network
"""
import socket
import ipaddress
import subprocess
import re
import logging
from typing import List, Dict, Optional, Tuple
import platform
import time

logger = logging.getLogger(__name__)

class NetworkDiscovery:
    """Network discovery service for finding and managing devices"""
    
    def __init__(self, network: str = None, timeout: float = 2.0):
        """
        Initialize network discovery
        
        Args:
            network: Network in CIDR notation (e.g., '192.168.1.0/24')
            timeout: Socket timeout in seconds
        """
        self.network = network or self._detect_local_network()
        self.timeout = timeout
        self.available_ports = [80, 443, 8080, 5000]  # Common web/API ports
    
    def _detect_local_network(self) -> str:
        """Detect the local network CIDR"""
        try:
            # Get default gateway IP
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['ipconfig'], capture_output=True, text=True, check=True
                )
                # Parse Windows ipconfig output
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'IPv4 Address' in line and ':' in line:
                        ip = line.split(':')[-1].strip()
                        # Assume /24 network
                        return f"{'.'.join(ip.split('.')[:3])}.0/24"
            else:
                # Linux/MacOS
                result = subprocess.run(
                    ['ip', 'route'], capture_output=True, text=True, check=True
                )
                # Find the default route
                for line in result.stdout.split('\n'):
                    if 'default via' in line and 'dev' in line:
                        parts = line.split()
                        dev_index = parts.index('dev')
                        iface = parts[dev_index + 1]
                        # Get IP address of the interface
                        ip_result = subprocess.run(
                            ['ip', 'addr', 'show', iface],
                            capture_output=True,
                            text=True,
                            check=True
                        )
                        # Find the IP address
                        for ip_line in ip_result.stdout.split('\n'):
                            if 'inet ' in ip_line:
                                ip_part = ip_line.split()[1].split('/')[0]
                                # Assume /24 network
                                return f"{'.'.join(ip_part.split('.')[:3])}.0/24"
        except Exception as e:
            logger.warning(f"Failed to detect local network: {e}")
        
        # Default fallback
        return '192.168.1.0/24'
    
    def scan_network(self) -> List[Dict]:
        """
        Scan the network for available devices
        
        Returns:
            List of dictionaries containing device information
        """
        devices = []
        network = ipaddress.ip_network(self.network, strict=False)
        
        # Get local IP to exclude from scan
        local_ip = self._get_local_ip()
        
        # Scan each IP in the network
        for ip in network.hosts():
            ip_str = str(ip)
            
            # Skip localhost and broadcast
            if ip_str == local_ip or ip_str.endswith('.255'):
                continue
            
            # Check if host is up
            if self._is_host_up(ip_str):
                device = {
                    'ip': ip_str,
                    'hostname': self._get_hostname(ip_str) or 'Unknown',
                    'ports': self._scan_ports(ip_str),
                    'last_seen': time.time()
                }
                devices.append(device)
        
        return devices
    
    def _get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            # Create a socket connection to a public IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))  # Google DNS
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except Exception:
            return '127.0.0.1'
    
    def _is_host_up(self, ip: str) -> bool:
        """Check if a host is up using ICMP ping"""
        try:
            # Try ICMP ping if available
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '-W', '1', ip]
            return subprocess.call(command, 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL) == 0
        except Exception:
            # Fallback to TCP connect on common ports
            for port in self.available_ports:
                if self._is_port_open(ip, port):
                    return True
            return False
    
    def _is_port_open(self, ip: str, port: int) -> bool:
        """Check if a TCP port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _get_hostname(self, ip: str) -> Optional[str]:
        """Get the hostname for an IP address"""
        try:
            return socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror):
            return None
    
    def _scan_ports(self, ip: str) -> List[int]:
        """Scan for open ports on a host"""
        open_ports = []
        for port in self.available_ports:
            if self._is_port_open(ip, port):
                open_ports.append(port)
        return open_ports

def discover_raspberry_pi_devices() -> List[Dict]:
    """
    Convenience function to discover Raspberry Pi devices on the network
    
    Returns:
        List of discovered Raspberry Pi devices
    """
    try:
        discovery = NetworkDiscovery()
        devices = discovery.scan_network()
        
        # Filter for Raspberry Pi devices
        pi_devices = []
        for device in devices:
            # Check common Raspberry Pi hostname patterns
            if any(pi_id in device['hostname'].lower() 
                  for pi_id in ['raspberry', 'raspberrypi', 'rpi', 'retropie']):
                device['device_type'] = 'raspberry_pi'
                pi_devices.append(device)
            
            # Check for open ports common on Raspberry Pi
            elif any(port in device['ports'] for port in [22, 80, 443, 5000, 8000, 8080]):
                device['device_type'] = 'unknown_linux'
                pi_devices.append(device)
        
        return pi_devices
    except Exception as e:
        logger.error(f"Error discovering Raspberry Pi devices: {e}")
        return []

def get_primary_raspberry_pi_ip() -> Optional[str]:
    """
    Get the IP address of the primary Raspberry Pi on the network
    
    Returns:
        str: IP address of the primary Pi, or None if not found
    """
    try:
        # Try to get the local IP first (if this is a Pi)
        local_ip = socket.gethostbyname(socket.gethostname())
        if local_ip and local_ip != '127.0.0.1':
            return local_ip
            
        # Otherwise, discover Pis on the network
        pi_devices = discover_raspberry_pi_devices()
        if pi_devices:
            # Return the first Pi found
            return pi_devices[0]['ip']
            
    except Exception as e:
        logger.error(f"Error getting primary Raspberry Pi IP: {e}")
    
    return None
