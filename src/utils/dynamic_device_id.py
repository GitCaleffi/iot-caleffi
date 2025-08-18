import subprocess
import uuid
import logging

logger = logging.getLogger(__name__)

def generate_dynamic_device_id():
    """Generate a unique device ID based on system hardware"""
    try:
        # Try to get system serial number
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    if serial and serial != '0000000000000000':
                        return f"scanner-{serial[-8:]}"
        
        # Fallback to MAC address
        result = subprocess.run(['cat', '/sys/class/net/eth0/address'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            mac = result.stdout.strip().replace(':', '')
            return f"scanner-{mac[-8:]}"
        
    except Exception as e:
        logger.warning(f"Could not get system ID: {e}")
    
    # Final fallback to random ID
    random_id = str(uuid.uuid4())[:8]
    return f"scanner-{random_id}"
