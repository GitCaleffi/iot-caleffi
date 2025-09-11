"""
Device registration utilities for automatic device provisioning.
"""
import logging
import uuid
import socket
import subprocess
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def get_local_mac_address():
    """Get the MAC address of the local device using multiple methods."""
    methods = [
        _get_mac_via_ip_link,
        _get_mac_via_ifconfig,
        _get_mac_via_netifaces,
        _get_mac_via_sys
    ]
    
    for method in methods:
        try:
            mac = method()
            if mac and mac != "00:00:00:00:00:00":
                logger.info(f"Found MAC address using {method.__name__}: {mac}")
                return mac
        except Exception as e:
            logger.debug(f"Method {method.__name__} failed: {e}")
    
    logger.warning("Could not determine MAC address using any method")
    return None

def _get_mac_via_ip_link():
    """Get MAC address using ip link command"""
    result = subprocess.run(
        ["ip", "link", "show"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        mac_pattern = r'link/ether\s+([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
        matches = re.findall(mac_pattern, result.stdout.lower())
        for mac in matches:
            if mac != "00:00:00:00:00:00":
                return mac
    return None

def _get_mac_via_ifconfig():
    """Get MAC address using ifconfig command"""
    result = subprocess.run(
        ["ifconfig"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0:
        mac_pattern = r'ether\s+([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
        matches = re.findall(mac_pattern, result.stdout.lower())
        for mac in matches:
            if mac != "00:00:00:00:00:00":
                return mac
    return None

def _get_mac_via_netifaces():
    """Get MAC address using netifaces library"""
    import netifaces
    for interface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_LINK in addrs:
            for addr in addrs[netifaces.AF_LINK]:
                mac = addr.get('addr', '').lower()
                if mac and mac != '00:00:00:00:00:00':
                    return mac
    return None

def _get_mac_via_sys():
    """Get MAC address from /sys/class/net"""
    import glob
    for iface in glob.glob('/sys/class/net/*/address'):
        with open(iface, 'r') as f:
            mac = f.read().strip()
            if mac and mac != '00:00:00:00:00:00':
                return mac
    return None

# Alias for backward compatibility
get_local_device_mac = get_local_mac_address

def auto_register_device_to_server():
    """Automatically register the device with the server using MAC address."""
    try:
        from database.local_storage import LocalStorage
        from iot.hub_client import HubClient
        from utils.dynamic_device_manager import device_manager
        
        # Generate device ID from MAC address
        mac_address = get_local_mac_address()
        if not mac_address:
            logger.error("Could not determine MAC address for device registration")
            return False
            
        device_id = f"pi-{mac_address.replace(':', '')[-8:]}"
        logger.info(f"Auto-registering device with ID: {device_id}")
        
        # Save to local database
        local_db = LocalStorage()
        local_db.save_device_id(device_id)
        
        # Register with IoT Hub if available
        try:
            token = device_manager.generate_registration_token()
            device_info = {
                "registration_method": "auto_plug_and_play",
                "mac_address": mac_address,
                "auto_registered": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            success, message = device_manager.register_device(token, device_id, device_info)
            if success:
                logger.info(f"Successfully registered device {device_id} with IoT Hub")
                return True
            else:
                logger.error(f"Failed to register with IoT Hub: {message}")
                return False
                
        except Exception as e:
            logger.error(f"Error during IoT Hub registration: {e}")
            return False
            
    except Exception as e:
        logger.error(f"Auto-registration failed: {e}")
        return False
