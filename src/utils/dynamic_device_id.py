"""
Dynamic device ID generation utilities
Generates unique and consistent device identifiers
"""
import hashlib
import uuid
import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def generate_device_id_from_mac(mac_address: str = None) -> str:
    """
    Generate a device ID from MAC address
    
    Args:
        mac_address: Optional MAC address. If not provided, will try to detect.
        
    Returns:
        str: Generated device ID
    """
    if not mac_address:
        mac_address = _get_mac_address()
    
    if not mac_address:
        logger.warning("No MAC address available, falling back to random UUID")
        return f"dev-{str(uuid.uuid4())[:8]}"
    
    # Normalize MAC address (remove any non-hex chars and lowercase)
    clean_mac = ''.join(c.lower() for c in mac_address if c.isalnum())
    
    # Generate a consistent hash of the MAC address
    h = hashlib.sha256(clean_mac.encode()).hexdigest()
    
    # Use first 12 characters of the hash
    return f"dev-{h[:12]}"

def generate_dynamic_device_id() -> str:
    """
    Generate a dynamic device ID using available system information
    
    Returns:
        str: Generated device ID
    """
    # Try to get MAC address first
    mac_address = _get_mac_address()
    if mac_address:
        return generate_device_id_from_mac(mac_address)
    
    # Fallback to hostname-based ID
    try:
        hostname = socket.gethostname()
        if hostname and hostname != 'localhost':
            h = hashlib.sha256(hostname.encode()).hexdigest()
            return f"host-{h[:10]}"
    except Exception as e:
        logger.warning(f"Failed to get hostname: {e}")
    
    # Final fallback: random UUID
    return f"dev-{str(uuid.uuid4())[:8]}"

def _get_mac_address() -> Optional[str]:
    """Get the MAC address of the primary network interface"""
    try:
        # Try to get MAC address using ip command (Linux)
        import subprocess
        result = subprocess.run(
            ["ip", "link", "show"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            import re
            # Look for the first non-loopback interface with a MAC address
            for line in result.stdout.split('\n'):
                if 'link/ether' in line:
                    mac_match = re.search(r'link/ether\s+([0-9a-fA-F:]+)', line)
                    if mac_match and not line.strip().startswith('lo:'):
                        return mac_match.group(1).lower()
        
        # Fallback to UUID based on MAC (works on most systems)
        mac = uuid.getnode()
        if (mac != uuid.getnode()):  # Check if we got a real MAC
            return ':'.join([f"{mac >> elements & 0xff:02x}" for elements in range(0,8*6,8)][::-1])
            
    except Exception as e:
        logger.debug(f"Failed to get MAC address: {e}")
    
    return None
