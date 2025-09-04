"""
Device Utilities - Handles device identification and internet connectivity checks
"""
import subprocess
import json
import os
import socket
import time
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Configuration - Using user's home directory for portability
CONFIG_DIR = os.path.expanduser("~/.iot-device")
CONFIG_FILE = os.path.join(CONFIG_DIR, "device_config.json")


def ensure_config_dir() -> None:
    """Ensure the config directory exists"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True, mode=0o755)
    except Exception as e:
        logger.error(f"Failed to create config directory: {e}")
        raise


def get_device_id() -> str:
    """
    Get or create a persistent device ID
    
    Returns:
        str: A unique device identifier
    """
    try:
        ensure_config_dir()
        
        # Try to load existing ID
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                if 'device_id' in config:
                    return config['device_id']
        
        # Generate new ID if none exists
        import uuid
        device_id = f"pi-{uuid.uuid4().hex[:8]}"
        
        # Save the new ID
        with open(CONFIG_FILE, 'w') as f:
            json.dump({'device_id': device_id}, f, indent=2)
        
        logger.info(f"Generated new device ID: {device_id}")
        return device_id
        
    except Exception as e:
        logger.error(f"Error in get_device_id: {e}")
        # Fallback to hostname if we can't use the filesystem
        return f"pi-{socket.gethostname()}-{int(time.time())}"


def check_internet_connectivity(timeout: int = 3) -> bool:
    """
    Check if the device has internet connectivity
    
    Args:
        timeout: Timeout in seconds
        
    Returns:
        bool: True if internet is reachable, False otherwise
    """
    test_servers = [
        '8.8.8.8',        # Google DNS
        '1.1.1.1',        # Cloudflare DNS
        'www.google.com',  # Google
        'www.azure.com'   # Microsoft Azure
    ]
    
    for server in test_servers:
        try:
            # Try DNS resolution first
            socket.gethostbyname(server)
            
            # Then try to ping
            cmd = ['ping', '-c', '1', '-W', str(timeout), server]
            result = subprocess.run(cmd, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 timeout=timeout + 1)
            
            if result.returncode == 0:
                logger.debug(f"Internet check passed via {server}")
                return True
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, socket.gaierror):
            continue
        except Exception as e:
            logger.debug(f"Internet check failed for {server}: {e}")
            continue
    
    logger.warning("No internet connectivity detected")
    return False


def get_network_interfaces() -> Dict[str, Dict[str, str]]:
    """
    Get status of network interfaces
    
    Returns:
        Dict with interface status information
    """
    interfaces = {}
    
    try:
        import netifaces
        
        for iface in netifaces.interfaces():
            if iface.startswith('lo'):
                continue
                
            addrs = netifaces.ifaddresses(iface)
            
            # Get IPv4 address if available
            ipv4 = addrs.get(netifaces.AF_INET, [{}])[0].get('addr', 'N/A')
            
            # Get MAC address
            mac = addrs.get(netifaces.AF_LINK, [{}])[0].get('addr', 'N/A')
            
            # Get interface status (up/down)
            operstate = 'down'
            try:
                with open(f'/sys/class/net/{iface}/operstate', 'r') as f:
                    operstate = f.read().strip()
            except:
                pass
                
            interfaces[iface] = {
                'ipv4': ipv4,
                'mac': mac,
                'status': operstate,
                'connected': operstate == 'up' and ipv4 != 'N/A'
            }
            
    except ImportError:
        logger.warning("netifaces module not available, using basic interface detection")
        
        # Fallback to basic interface detection
        for iface in ['eth0', 'wlan0']:
            try:
                # Check if interface exists
                with open(f'/sys/class/net/{iface}/operstate', 'r') as f:
                    operstate = f.read().strip()
                    
                # Get IP address
                ip_cmd = f"ip -4 addr show {iface} | grep -oP '(?<=inet\s)\d+(\.\d+){3}'"
                ip_result = subprocess.run(ip_cmd, shell=True, capture_output=True, text=True)
                ipv4 = ip_result.stdout.strip() if ip_result.returncode == 0 else 'N/A'
                
                # Get MAC address
                mac_cmd = f"cat /sys/class/net/{iface}/address"
                mac_result = subprocess.run(mac_cmd, shell=True, capture_output=True, text=True)
                mac = mac_result.stdout.strip() if mac_result.returncode == 0 else 'N/A'
                
                interfaces[iface] = {
                    'ipv4': ipv4,
                    'mac': mac,
                    'status': operstate,
                    'connected': operstate == 'up' and ipv4 != 'N/A'
                }
                
            except Exception as e:
                interfaces[iface] = {
                    'ipv4': 'N/A',
                    'mac': 'N/A',
                    'status': 'down',
                    'connected': False,
                    'error': str(e)
                }
    
    return interfaces
