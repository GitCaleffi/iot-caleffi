#!/usr/bin/env python3
"""
Fix for network detection issue - forces correct IP detection
"""

import subprocess
import socket
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_correct_server_ip():
    """Get the correct server IP using multiple methods"""
    
    # Method 1: Use ip route to get the default interface IP
    try:
        result = subprocess.run(
            ["ip", "route", "get", "1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            # Parse output like: "1.1.1.1 via 192.168.1.1 dev eno1 src 192.168.1.8"
            match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', result.stdout)
            if match:
                ip = match.group(1)
                logger.info(f"✅ Found correct IP via ip route: {ip}")
                return ip
    except Exception as e:
        logger.debug(f"ip route method failed: {e}")
    
    # Method 2: Use ip addr show to get interface IPs
    try:
        result = subprocess.run(
            ["ip", "addr", "show"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            # Look for inet addresses that are not loopback
            for line in result.stdout.splitlines():
                if 'inet ' in line and 'scope global' in line:
                    match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if match:
                        ip = match.group(1)
                        if not ip.startswith('127.'):
                            logger.info(f"✅ Found correct IP via ip addr: {ip}")
                            return ip
    except Exception as e:
        logger.debug(f"ip addr method failed: {e}")
    
    # Method 3: Use hostname -I
    try:
        result = subprocess.run(
            ["hostname", "-I"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            ips = result.stdout.strip().split()
            for ip in ips:
                if '.' in ip and not ip.startswith('127.') and not ip.startswith('169.254'):
                    logger.info(f"✅ Found correct IP via hostname: {ip}")
                    return ip
    except Exception as e:
        logger.debug(f"hostname method failed: {e}")
    
    logger.warning("Could not determine correct server IP")
    return None

def patch_network_discovery():
    """Patch the network discovery file to use correct IP detection"""
    
    network_file = "/var/www/html/abhimanyu/barcode_scanner_clean/deployment_package/src/utils/network_discovery.py"
    
    try:
        # Read the current file
        with open(network_file, 'r') as f:
            content = f.read()
        
        # Find the _get_server_ip method and replace it
        old_method = '''    def _get_server_ip(self) -> str:
        """Get the actual server IP address using Python socket methods"""
        import socket
        
        try:
            # Method 1: Use Python socket to connect to external IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to Google DNS (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if local_ip and not local_ip.startswith('127.'):
                    logger.info(f"📍 Server IP detected via socket: {local_ip}")
                    return local_ip
        except Exception as e:
            logger.debug(f"Socket method failed: {e}")'''
        
        new_method = '''    def _get_server_ip(self) -> str:
        """Get the actual server IP address using reliable methods"""
        import socket
        import subprocess
        import re
        
        # Method 1: Use ip route to get the default interface IP (most reliable)
        try:
            result = subprocess.run(
                ["ip", "route", "get", "1.1.1.1"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                # Parse output like: "1.1.1.1 via 192.168.1.1 dev eno1 src 192.168.1.8"
                match = re.search(r'src\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)', result.stdout)
                if match:
                    local_ip = match.group(1)
                    logger.info(f"📍 Server IP detected via ip route: {local_ip}")
                    return local_ip
        except Exception as e:
            logger.debug(f"ip route method failed: {e}")
        
        # Method 2: Use ip addr show to get interface IPs
        try:
            result = subprocess.run(
                ["ip", "addr", "show"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                # Look for inet addresses that are not loopback
                for line in result.stdout.splitlines():
                    if 'inet ' in line and 'scope global' in line:
                        match = re.search(r'inet\\s+(\\d+\\.\\d+\\.\\d+\\.\\d+)', line)
                        if match:
                            local_ip = match.group(1)
                            if not local_ip.startswith('127.'):
                                logger.info(f"📍 Server IP detected via ip addr: {local_ip}")
                                return local_ip
        except Exception as e:
            logger.debug(f"ip addr method failed: {e}")
        
        # Method 3: Fallback to socket method
        try:
            # Use Python socket to connect to external IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Connect to Google DNS (doesn't actually send data)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if local_ip and not local_ip.startswith('127.'):
                    logger.info(f"📍 Server IP detected via socket: {local_ip}")
                    return local_ip
        except Exception as e:
            logger.debug(f"Socket method failed: {e}")'''
        
        # Replace the method
        if old_method in content:
            content = content.replace(old_method, new_method)
            
            # Write back the patched file
            with open(network_file, 'w') as f:
                f.write(content)
            
            logger.info("✅ Successfully patched network discovery file")
            return True
        else:
            logger.warning("Could not find the exact method to patch")
            return False
            
    except Exception as e:
        logger.error(f"Error patching network discovery: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Network Detection Fix")
    print("=" * 30)
    
    # Test current IP detection
    correct_ip = get_correct_server_ip()
    if correct_ip:
        print(f"✅ Detected correct server IP: {correct_ip}")
        
        # Apply the patch
        if patch_network_discovery():
            print("✅ Network discovery patched successfully")
            print("🔄 Please restart your application to use the fixed IP detection")
        else:
            print("❌ Failed to patch network discovery")
    else:
        print("❌ Could not determine correct server IP")
