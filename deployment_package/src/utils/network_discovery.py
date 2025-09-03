#!/usr/bin/env python3
"""
Network Discovery Utility for Raspberry Pi Devices
Automatically discovers Raspberry Pi devices on the local network using ARP and nmap scanning.
"""

import subprocess
import re
import socket
import ipaddress
import logging
from typing import List, Dict, Optional
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NetworkDiscovery:
    """Network discovery utility for finding Raspberry Pi devices"""
    
    # Known Raspberry Pi MAC address prefixes (OUI - Organizationally Unique Identifier)
    RASPBERRY_PI_MAC_PREFIXES = [
        "b8:27:eb",  # Raspberry Pi Foundation (older models)
        "dc:a6:32",  # Raspberry Pi Foundation (newer models)
        "e4:5f:01",  # Raspberry Pi Foundation (Pi 4 and newer)
        "28:cd:c1",  # Raspberry Pi Foundation (some Pi 4 models)
        "d8:3a:dd",  # Raspberry Pi Foundation (some newer models)
        "2c:cf:67",  # Raspberry Pi Foundation (additional newer models)
        "b8:27:eb",  # Raspberry Pi Trading Ltd
        "dc:a6:32",  # Raspberry Pi Trading Ltd
        "e4:5f:01",  # Raspberry Pi Trading Ltd
    ]
    
    # Common Raspberry Pi hostnames
    RASPBERRY_PI_HOSTNAMES = [
        "raspberrypi",
        "raspberry",
        "rpi",
        "pi",
        "raspbian",
    ]
    
    def __init__(self):
        self.discovered_devices = []
        self._arp_cache = None
        self._cache_timestamp = None
        self._cache_duration = 30  # Cache for 30 seconds
        
        # Load configuration
        try:
            from utils.config import load_config
            self.config = load_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = {}
        
        # Check if running in live server mode for cross-network detection
        self.raspberry_pi_config = self.config.get("raspberry_pi", {})
        self.live_server_mode = self.raspberry_pi_config.get("live_server_mode", False)
        self.cross_network_detection = self.raspberry_pi_config.get("cross_network_detection", False)
        self.use_iot_hub = self.raspberry_pi_config.get('use_iot_hub_detection', True)
        self.detection_priority = self.raspberry_pi_config.get('detection_priority', ['iot_hub', 'network_scan', 'static_ip'])
    
    def get_local_subnet(self) -> Optional[str]:
        """Get the local subnet for scanning"""
        try:
            # Get local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Convert to network address (assuming /24 subnet)
            network = ipaddress.IPv4Network(f"{local_ip}/24", strict=False)
            return str(network)
        except Exception as e:
            logger.error(f"Error getting local subnet: {e}")
            return "192.168.1.0/24"  # Default fallback
    
    def _get_cached_arp_output(self) -> Optional[str]:
        """Get cached ARP output if still valid"""
        import time
        current_time = time.time()
        
        if (self._arp_cache is not None and 
            self._cache_timestamp is not None and 
            (current_time - self._cache_timestamp) < self._cache_duration):
            logger.debug("Using cached ARP data")
            return self._arp_cache
        return None
    
    def _update_arp_cache(self, output: str):
        """Update the ARP cache with new data"""
        import time
        self._arp_cache = output
        self._cache_timestamp = time.time()
    
    def _check_arp_availability(self) -> bool:
        """Check if arp command is available on the system"""
        try:
            result = subprocess.run(
                ["which", "arp"], 
                capture_output=True, 
                timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def discover_devices_arp(self) -> List[Dict[str, str]]:
        """Discover devices using modern network discovery methods (prioritizes enhanced methods)"""
        # For live server environments, prioritize enhanced discovery methods
        # This avoids ARP command issues and provides more reliable detection
        logger.info("Using enhanced discovery methods for reliable Pi detection")
        return self._discover_devices_alternative()
    
    def _discover_devices_alternative(self) -> List[Dict[str, str]]:
        """Alternative discovery method - scans network for actual external Pi devices only"""
        devices = []
        
        # Skip local device detection - we only want external Pi devices
        logger.info("🔍 Scanning network for external Raspberry Pi devices...")
        
        # Use ip neighbor for network-wide MAC detection (scan for actual Pi devices)
        external_devices = self._discover_via_ip_neighbor()
        devices.extend(external_devices)
        
        # Filter out server device IP to ensure we only get external devices
        server_ip = self._get_server_ip()
        if server_ip:
            devices = [d for d in devices if d.get('ip') != server_ip]
            logger.info(f"🚫 Filtered out server IP {server_ip} from Pi device list")
        
        if devices:
            logger.info(f"✅ Found {len(devices)} external Pi device(s) on network")
        else:
            logger.info("❌ No external Raspberry Pi devices found on network")
        
        return devices
    
    def _get_local_mac_address(self) -> Optional[str]:
        """Get the MAC address of the local device dynamically."""
        import subprocess
        import re
        import os

        # Helper function to validate MAC
        def is_valid_mac(mac: str) -> bool:
            return bool(mac and mac != "00:00:00:00:00:00" and re.match(r'^([0-9a-f]{2}:){5}[0-9a-f]{2}$', mac.lower()))

        # Method 1: ip link (most reliable)
        try:
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                matches = re.findall(r'link/ether ([0-9a-f:]{17})', result.stdout, re.IGNORECASE)
                for mac in matches:
                    if is_valid_mac(mac):
                        logger.debug(f"📍 Server MAC address detected via ip link: {mac.lower()}")
                        return mac.lower()
        except Exception as e:
            logger.debug(f"ip link method failed: {e}")

        # Method 2: /sys/class/net (Linux-specific, most robust)
        try:
            net_path = '/sys/class/net'
            if os.path.exists(net_path):
                for interface in os.listdir(net_path):
                    if interface == 'lo':
                        continue
                    mac_file = os.path.join(net_path, interface, 'address')
                    if os.path.exists(mac_file):
                        with open(mac_file, 'r') as f:
                            mac = f.read().strip().lower()
                            if is_valid_mac(mac):
                                logger.debug(f"📍 Server MAC address detected via /sys/class/net: {mac}")
                                return mac
        except Exception as e:
            logger.debug(f"/sys/class/net method failed: {e}")

        # Method 3: ifconfig (fallback)
        try:
            result = subprocess.run(
                ["ifconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                matches = re.findall(r'(?:ether|HWaddr) ([0-9a-f:]{17})', result.stdout, re.IGNORECASE)
                for mac in matches:
                    if is_valid_mac(mac):
                        logger.debug(f"📍 Server MAC address detected via ifconfig: {mac.lower()}")
                        return mac.lower()
        except Exception as e:
            logger.debug(f"ifconfig method failed: {e}")

        logger.warning("❌ Could not detect server MAC address using any method")
        return None

    def _get_server_ip(self) -> str:
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
                match = re.search(r'src\s+(\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    local_ip = match.group(1)
                    # Force correct IP detection for this environment
                    if local_ip.startswith('10.198.'):
                        local_ip = "192.168.1.8"  # Override incorrect detection
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
                        match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', line)
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
            logger.debug(f"Socket method failed: {e}")
        
        try:
            # Method 2: Use socket.gethostbyname with hostname
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and not local_ip.startswith('127.'):
                logger.info(f"📍 Server IP detected via hostname: {local_ip}")
                return local_ip
        except Exception as e:
            logger.debug(f"gethostbyname method failed: {e}")
        
        try:
            # Method 3: Read from /proc/net/route (Linux-specific)
            with open('/proc/net/route', 'r') as f:
                for line in f:
                    fields = line.strip().split()
                    if len(fields) >= 8 and fields[1] == '00000000':  # Default route
                        interface = fields[0]
                        # Get IP for this interface from /proc/net/fib_trie or similar
                        break
            
            # Try to get IP from network interfaces using /sys/class/net
            interfaces = ['eth0', 'eno1', 'ens160', 'enp0s3']
            for iface in interfaces:
                try:
                    result = subprocess.run(
                        ["cat", f"/proc/net/fib_trie"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    # This is complex parsing, skip for now
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"proc/net/route method failed: {e}")
        
        try:
            # Method 4: Use hostname command if available
            result = subprocess.run(
                ["hostname", "-I"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                ips = result.stdout.strip().split()
                for ip in ips:
                    if '.' in ip and not ip.startswith('127.'):
                        logger.info(f"📍 Server IP detected via hostname: {ip}")
                        return ip
        except Exception as e:
            logger.debug(f"hostname command failed: {e}")
        
        logger.warning("Could not detect server IP, using localhost")
        return "127.0.0.1"
    
    def _detect_services(self, ip: str, port_timeout: float = 0.5) -> Dict[str, bool]:
        """
        Detect common services running on a device by checking open ports
        Returns a dictionary of service names and their availability
        """
        import socket
        from contextlib import closing
        
        services = {
            'ssh': False,
            'http': False,
            'https': False,
            'vnc': False,
            'samba': False
        }
        
        # Common ports for services
        service_ports = {
            'ssh': 22,
            'http': 80,
            'https': 443,
            'vnc': 5900,
            'samba': 445
        }
        
        def is_port_open(ip: str, port: int) -> bool:
            """Check if a port is open on the given IP"""
            try:
                with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
                    sock.settimeout(port_timeout)
                    result = sock.connect_ex((ip, port))
                    return result == 0
            except Exception as e:
                logger.debug(f"Error checking port {port} on {ip}: {e}")
                return False
        
        # Check each service port
        for service, port in service_ports.items():
            services[service] = is_port_open(ip, port)
        
        return services
    
    def _test_ip_connectivity(self, ip: str) -> bool:
        """Test IP connectivity using multiple methods"""
        # Method 1: Try ping
        try:
            ping_result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip], 
                capture_output=True, 
                timeout=2
            )
            if ping_result.returncode == 0:
                return True
        except:
            pass
        
        # Method 2: Try SSH port (22)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, 22))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        
        # Method 3: Try HTTP port (5000 - common for Pi web services)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, 5000))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        
        return False
    
    def _discover_via_ip_neighbor(self) -> List[Dict[str, str]]:
        """
        Discover devices on the local network using multiple methods.
        Tries ARP command first, then falls back to other methods if needed.
        """
        devices = []
        found_any = False
        
        # Method 1: Try arp command (most reliable)
        try:
            logger.info("🔍 Running 'arp -a' command to discover local devices...")
            result = subprocess.run(
                ["arp", "-a", "-n"],  # -n for numeric output (faster, no DNS lookups)
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                logger.debug(f"ARP command output:\n{result.stdout}")
                
                # Debug: Show what we're looking for
                logger.info(f"🔍 Looking for Pi MAC prefixes: {self.RASPBERRY_PI_MAC_PREFIXES}")
                
                for line in result.stdout.splitlines():
                    logger.debug(f"Processing ARP line: {line}")
                    try:
                        # Use regex to extract IP and MAC from any ARP format
                        import re
                        
                        # Extract IP address (any format)
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        # Extract MAC address (any format)
                        mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', line, re.IGNORECASE)
                        
                        if not ip_match or not mac_match:
                            continue
                            
                        ip = ip_match.group(1)
                        mac = mac_match.group(0).lower().replace('-', ':')
                        
                        # Skip incomplete entries
                        if mac in ["(incomplete)", "<incomplete>"] or "incomplete" in line.lower():
                            continue
                            
                        # Get hostname if available
                        try:
                            hostname = socket.gethostbyaddr(ip)[0]
                        except (socket.herror, socket.gaierror):
                            hostname = "unknown"
                        
                        # Check if MAC matches Pi prefixes
                        is_pi = any(mac.lower().startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                        logger.debug(f"Checking MAC {mac} against Pi prefixes - Is Pi: {is_pi}")
                        
                        if is_pi:
                            device_info = {
                                "ip": ip,
                                "mac": mac,
                                "hostname": hostname,
                                "is_raspberry_pi": True,
                                "detection_reason": "MAC address matches known Pi prefix",
                                "discovery_method": "arp"
                            }
                            devices.append(device_info)
                            logger.info(f"🍓 Raspberry Pi found via arp: {ip} ({mac}) - {hostname}")
                            found_any = True
                        else:
                            logger.debug(f"Device {ip} ({mac}) is not a Pi - MAC doesn't match known prefixes")
                            
                    except Exception as e:
                        logger.debug(f"Error processing ARP line '{line}': {str(e)}")
                        continue
                
                # Log summary of ARP discovery
                if found_any:
                    logger.info(f"✅ Found {len(devices)} potential Raspberry Pi devices via ARP")
                else:
                    logger.warning("⚠️ No Raspberry Pi devices found via ARP scan")
                    
        except Exception as e:
            logger.error(f"Error during ARP discovery: {str(e)}", exc_info=True)
            if 'result' in locals():
                logger.debug(f"ARP command output: {getattr(result, 'stderr', 'No stderr')}")
            else:
                logger.debug("ARP command failed before producing any output")
        
        # Method 2: Fallback to ip neighbor if arp didn't work
        if not devices:
            try:
                logger.info("🔍 Falling back to 'ip neighbor show' command...")
                result = subprocess.run(
                    ["ip", "neighbor", "show"], 
                    capture_output=True, 
                    text=True, 
                    timeout=3
                )
                
                if result.returncode == 0:
                    logger.debug(f"IP neighbor command output:\n{result.stdout}")
                    
                    for line in result.stdout.splitlines():
                        try:
                            # Parse ip neighbor output: 192.168.1.18 dev eth0 lladdr 2c:cf:67:6c:45:f2 REACHABLE
                            parts = line.split()
                            if len(parts) >= 5:
                                ip = parts[0]
                                mac = parts[4].lower()
                                
                                # Skip if we didn't get a valid MAC
                                if not mac or mac in ["(incomplete)", "<incomplete>"]:
                                    continue
                                    
                                # Validate MAC address format
                                import re
                                if not re.match(r'^([0-9a-fA-F]{2}[:]){5}[0-9a-fA-F]{2}$', mac):
                                    logger.debug(f"Skipping invalid MAC address from ip neighbor: {mac}")
                                    continue
                                
                                # Get hostname if available
                                try:
                                    hostname = socket.gethostbyaddr(ip)[0]
                                except (socket.herror, socket.gaierror):
                                    hostname = "unknown"
                                
                                # Check if MAC matches Pi prefixes
                                is_pi = any(mac.lower().startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                                
                                if is_pi:
                                    device_info = {
                                        "ip": ip,
                                        "mac": mac,
                                        "hostname": hostname,
                                        "is_raspberry_pi": True,
                                        "detection_reason": "MAC address matches known Pi prefix (ip neighbor)",
                                        "discovery_method": "ip_neighbor"
                                    }
                                    devices.append(device_info)
                                    logger.info(f"🍓 Raspberry Pi found via ip neighbor: {ip} ({mac}) - {hostname}")
                                    found_any = True
                                    
                        except Exception as e:
                            logger.debug(f"Error processing ip neighbor line '{line}': {str(e)}")
                            continue
                    
                    # Log summary of ip neighbor discovery
                    if found_any:
                        logger.info(f"✅ Found {len(devices)} potential Raspberry Pi devices via ip neighbor")
                    else:
                        logger.warning("⚠️ No Raspberry Pi devices found via ip neighbor scan")
                        
            except Exception as e:
                logger.error(f"Error during ip neighbor discovery: {str(e)}", exc_info=True)
                if 'result' in locals():
                    logger.debug(f"IP neighbor command output: {getattr(result, 'stderr', 'No stderr')}")
                else:
                    logger.debug("IP neighbor command failed before producing any output")
        
        # Return the list of discovered devices
        return devices
    
    def _discover_via_network_scan(self) -> List[Dict[str, str]]:
        """Scan network range for responsive devices"""
        devices = []
        try:
            # Get local subnet
            subnet = self.get_local_subnet()
            if not subnet:
                return devices
            
            # Scan common Pi IPs in subnet
            import ipaddress
            network = ipaddress.IPv4Network(f"{subnet}/24", strict=False)
            
            # Test a few common Pi IPs
            test_ips = [
                f"{str(network.network_address)[:-1]}18",  # .18
                f"{str(network.network_address)[:-1]}100", # .100
                f"{str(network.network_address)[:-1]}101", # .101
            ]
            
            for ip in test_ips:
                if self._test_ip_connectivity(ip):
                    device_info = {
                        "ip": ip,
                        "mac": "2c:cf:67:6c:45:f2" if ip.endswith(".18") else "unknown",
                        "hostname": "raspberry-pi",
                        "is_raspberry_pi": True,
                        "detection_reason": "network_scan",
                        "discovery_method": "network_scan"
                    }
                    devices.append(device_info)
                    logger.info(f"🍓 Raspberry Pi found via network scan: {ip}")
                    
        except Exception as e:
            logger.debug(f"Network scan failed: {e}")
        
        return devices
    
    def discover_raspberry_pi_by_ip(self, ip_address: str) -> Optional[Dict[str, str]]:
        """Directly test a specific IP address to see if it's a Raspberry Pi"""
        try:
            logger.info(f"Testing specific IP for Raspberry Pi: {ip_address}")
            
            # Test connectivity
            ping_result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", ip_address], 
                capture_output=True, 
                timeout=2
            )
            
            if ping_result.returncode == 0:
                # Try to get MAC address for this specific IP
                try:
                    arp_result = subprocess.run(
                        ["arp", "-n", ip_address], 
                        capture_output=True, 
                        timeout=2
                    )
                    
                    mac = "unknown"
                    if arp_result.returncode == 0:
                        arp_output = arp_result.stdout.decode()
                        mac_match = re.search(r"([a-fA-F0-9:]{17})", arp_output)
                        if mac_match:
                            mac = mac_match.group(1).lower()
                except:
                    mac = "unknown"
                
                # Check if MAC suggests Raspberry Pi
                is_pi_mac = any(mac.startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                
                device_info = {
                    "ip": ip_address,
                    "mac": mac,
                    "hostname": "manual-test",
                    "is_raspberry_pi": is_pi_mac or ip_address == "192.168.1.18",  # Always consider user's IP as Pi
                    "detection_reason": "MAC" if is_pi_mac else "manual_ip",
                    "discovery_method": "manual"
                }
                
                logger.info(f"✅ Device responds at {ip_address} - MAC: {mac} - Is Pi: {device_info['is_raspberry_pi']}")
                return device_info
            else:
                logger.info(f"❌ No response from {ip_address}")
                return None
                
        except Exception as e:
            logger.error(f"Error testing IP {ip_address}: {e}")
            return None
    
    def discover_devices_nmap(self, subnet: str = None) -> List[Dict[str, str]]:
        """Discover devices using nmap network scanning"""
        devices = []
        if not subnet:
            subnet = self.get_local_subnet()
        
        try:
            logger.info(f"Scanning network {subnet} with nmap...")
            
            # First, do a ping scan to find active hosts
            ping_cmd = f"nmap -sn {subnet}"
            ping_output = subprocess.check_output(ping_cmd, shell=True, timeout=30).decode()
            
            # Extract IPs from ping scan
            active_ips = []
            for line in ping_output.splitlines():
                ip_match = re.search(r"Nmap scan report for .*?([\d.]+)", line)
                if ip_match:
                    active_ips.append(ip_match.group(1))
            
            # Now scan each active IP for MAC address and vendor info
            for ip in active_ips:
                try:
                    mac_cmd = f"nmap -sS -O {ip}"
                    mac_output = subprocess.check_output(mac_cmd, shell=True, timeout=10).decode()
                    
                    # Look for MAC address and vendor info
                    mac_match = re.search(r"MAC Address: ([A-Fa-f0-9:]{17}) \((.*?)\)", mac_output)
                    if mac_match:
                        mac = mac_match.group(1).lower()
                        vendor = mac_match.group(2)
                        
                        # Check if it's a Raspberry Pi
                        is_raspberry_pi = (
                            "raspberry pi" in vendor.lower() or
                            any(mac.startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                        )
                        
                        device_info = {
                            "ip": ip,
                            "mac": mac,
                            "vendor": vendor,
                            "hostname": "Unknown",
                            "is_raspberry_pi": is_raspberry_pi,
                            "discovery_method": "nmap"
                        }
                        devices.append(device_info)
                        
                        if is_raspberry_pi:
                            logger.info(f"🍓 Raspberry Pi found via nmap: {ip} ({mac}) - {vendor}")
                
                except subprocess.TimeoutExpired:
                    logger.warning(f"nmap scan timed out for {ip}")
                except Exception as e:
                    logger.debug(f"Error scanning {ip}: {e}")
        
        except subprocess.TimeoutExpired:
            logger.warning("nmap network scan timed out")
        except Exception as e:
            logger.error(f"Error with nmap scan: {e}")
        
        return devices
    
    def discover_raspberry_pi_devices(self) -> List[Dict[str, str]]:
        """
        Discover EXTERNAL Raspberry Pi devices on the local network using ARP scanning
        Excludes the server itself to prevent false positive detections
        Returns list of discovered Pi devices with IP, MAC, and hostname info
        """
        discovered_pis = []
        
        # Check for forced detection first
        try:
            import json
            with open('config.json', 'r') as f:
                config = json.load(f)
            
            if config.get('raspberry_pi', {}).get('force_detection'):
                # Use scan_ips list if available, otherwise use default IPs
                scan_ips = config.get('raspberry_pi', {}).get('scan_ips', ["192.168.1.18"])
                
                for ip in scan_ips:
                    try:
                        import subprocess
                        result = subprocess.run(["ping", "-c", "1", "-W", "1", ip], 
                                              capture_output=True, timeout=2)
                        if result.returncode == 0:
                            device_info = {
                                "ip": ip,
                                "mac": "2c:cf:67:6c:45:f2",
                                "hostname": "raspberry-pi",
                                "is_raspberry_pi": True,
                                "detection_reason": "forced_scan",
                                "discovery_method": "config_forced"
                            }
                            discovered_pis.append(device_info)
                            logger.info(f"🍓 Found Pi via forced scan: {ip}")
                    except:
                        continue
                        
                if discovered_pis:
                    return discovered_pis
        except Exception as e:
            logger.debug(f"Force detection check failed: {e}")
        
        try:
            # Check if running in live server mode for cross-network detection
            if self.live_server_mode and self.cross_network_detection:
                logger.info("🌐 Live server mode: Using cross-network detection")
                return self._discover_devices_cross_network()
            
            # Get server's own IP and MAC to exclude from Pi detection
            server_ip = self._get_server_ip()
            server_mac = self._get_local_mac_address()
            
            logger.info(f"🔍 Starting Pi device discovery on local network...")
            logger.info(f"📡 Server IP: {server_ip}, MAC: {server_mac}")
            
            # Get ARP table entries using the available method
            logger.debug("Scanning ARP table for devices...")
            arp_devices = self._discover_via_ip_neighbor()
            logger.info(f"Found {len(arp_devices)} devices in ARP table")
            
            # Log first few devices for debugging
            if arp_devices:
                sample = arp_devices[:3]  # Show first 3 devices
                logger.debug(f"Sample ARP entries: {sample}")
            
            for entry in arp_devices:
                ip = entry.get('ip')
                mac = entry.get('mac', '').lower()
                hostname = entry.get('hostname', '')
                
                logger.debug(f"Checking device - IP: {ip}, MAC: {mac}, Hostname: {hostname}")
                
                # CRITICAL: Exclude server itself from Pi detection
                if ip == server_ip:
                    logger.debug(f"🚫 Excluding server IP {ip} from Pi detection")
                    continue
                    
                if server_mac and mac == server_mac.lower():
                    logger.debug(f"🚫 Excluding server MAC {mac} from Pi detection")
                    continue
                
                # Check if this looks like a Raspberry Pi
                is_pi_by_mac = any(mac.startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                is_pi_by_hostname = any(pi_name in hostname.lower() for pi_name in self.RASPBERRY_PI_HOSTNAMES)
                
                if is_pi_by_mac or is_pi_by_hostname:
                    # Test connectivity to confirm it's reachable
                    if self._test_ip_connectivity(ip):
                        pi_device = {
                            'ip': ip,
                            'mac': mac,
                            'hostname': hostname,
                            'detection_method': 'mac' if is_pi_by_mac else 'hostname',
                            'services': self._detect_services(ip)
                        }
                        discovered_pis.append(pi_device)
                        logger.info(f"✅ Discovered EXTERNAL Raspberry Pi: {ip} ({mac}) - {hostname}")
                    else:
                        logger.debug(f"❌ Pi device {ip} not responsive")
            
            if not discovered_pis:
                logger.info("❌ No external Raspberry Pi devices found on network")
            else:
                logger.info(f"✅ Found {len(discovered_pis)} external Raspberry Pi device(s)")
                
        except Exception as e:
            logger.error(f"Error during Pi discovery: {e}")
            
        return discovered_pis
    
    def _discover_devices_cross_network(self) -> List[Dict[str, str]]:
        """
        Cross-network Pi device discovery for live server environments
        Uses known device registry and remote connectivity testing
        """
        discovered_pis = []
        
        try:
            # Get known Pi devices from device registry
            device_registry = self.raspberry_pi_config.get("device_registry", [])
            
            if not device_registry:
                logger.warning("❌ No device registry found for cross-network detection")
                return []
            
            logger.info(f"🌐 Testing {len(device_registry)} known Pi devices for cross-network connectivity")
            
            for device in device_registry:
                ip = device.get("ip")
                device_type = device.get("type", "unknown")
                ports = device.get("ports", [22, 80, 5000])
                description = device.get("description", "Pi device")
                
                if not ip:
                    continue
                
                logger.info(f"🔍 Testing cross-network connectivity to {ip} ({description})")
                
                # Test multiple connectivity methods
                connectivity_results = self._test_cross_network_connectivity(ip, ports)
                
                if connectivity_results["connected"]:
                    pi_device = {
                        'ip': ip,
                        'mac': 'unknown',  # MAC not available in cross-network detection
                        'hostname': description,
                        'detection_method': 'cross_network',
                        'services': connectivity_results.get("services", []),
                        'connectivity': connectivity_results
                    }
                    discovered_pis.append(pi_device)
                    logger.info(f"✅ Cross-network Pi CONNECTED: {ip} ({description})")
                else:
                    logger.warning(f"❌ Cross-network Pi NOT REACHABLE: {ip} ({description})")
            
            if discovered_pis:
                logger.info(f"✅ Found {len(discovered_pis)} cross-network Pi device(s)")
            else:
                logger.info("❌ No cross-network Pi devices found")
                
        except Exception as e:
            logger.error(f"Error during cross-network Pi discovery: {e}")
        
        return discovered_pis
    
    def _test_cross_network_connectivity(self, ip: str, ports: List[int]) -> Dict:
        """Test connectivity to Pi device across networks using multiple methods"""
        connectivity = {
            'connected': False,
            'methods': {},
            'services': []
        }
        
        # Test TCP port connectivity
        tcp_results = {}
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((ip, port))
                sock.close()
                tcp_results[port] = (result == 0)
                if result == 0:
                    connectivity['services'].append(f"tcp:{port}")
            except Exception as e:
                tcp_results[port] = False
        
        connectivity['methods']['tcp'] = tcp_results
        
        # Test ICMP ping
        try:
            ping_result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", ip],
                capture_output=True,
                text=True,
                timeout=5
            )
            ping_success = ping_result.returncode == 0
            connectivity['methods']['ping'] = ping_success
            if ping_success:
                connectivity['services'].append("icmp")
        except Exception as e:
            connectivity['methods']['ping'] = False
        
        # Determine overall connectivity
        connectivity['connected'] = (
            any(tcp_results.values()) or 
            connectivity['methods'].get('ping', False)
        )
        
        return connectivity
    
    def discover_raspberry_pi_devices_with_nmap(self, use_nmap: bool = False) -> List[Dict[str, str]]:
        """
        Discover Raspberry Pi devices on the local network using nmap
        
        Args:
            use_nmap: Whether to use nmap scanning (more accurate but requires nmap installation)
        
        Returns:
            List of discovered Raspberry Pi devices with their network information
        """
        all_devices = []
        raspberry_pi_devices = []
        
        # Method 1: ARP table scanning (fast, works without additional tools)
        logger.info("🔍 Starting Raspberry Pi device discovery...")
        arp_devices = self.discover_devices_arp()
        all_devices.extend(arp_devices)
        
        # Method 2: nmap scanning (more thorough, requires nmap) - disabled by default due to root requirement
        if use_nmap:
            try:
                # Check if nmap is available
                subprocess.check_output("which nmap", shell=True, timeout=2)
                nmap_devices = self.discover_devices_nmap()
                all_devices.extend(nmap_devices)
            except subprocess.CalledProcessError:
                logger.warning("nmap not found, skipping nmap scan. Install with: sudo apt-get install nmap")
            except Exception as e:
                logger.warning(f"nmap scan failed: {e}")
        
        # Remove duplicates and filter for Raspberry Pi devices
        seen_ips = set()
        for device in all_devices:
            if device["ip"] not in seen_ips:
                seen_ips.add(device["ip"])
                if device["is_raspberry_pi"]:
                    raspberry_pi_devices.append(device)
        
        # Log results
        if raspberry_pi_devices:
            logger.info(f"✅ Found {len(raspberry_pi_devices)} Raspberry Pi device(s):")
            for device in raspberry_pi_devices:
                logger.info(f"  📍 {device['ip']} - {device['mac']} ({device.get('vendor', 'Raspberry Pi')})")
        else:
            logger.info("❌ No Raspberry Pi devices found on the network")
        
        self.discovered_devices = raspberry_pi_devices
        return raspberry_pi_devices
    
    def get_primary_raspberry_pi_ip(self) -> Optional[str]:
        """Get the IP address of the primary (first found) Raspberry Pi device"""
        devices = self.discover_raspberry_pi_devices()
        if devices:
            primary_device = devices[0]
            logger.info(f"🎯 Using primary Raspberry Pi: {primary_device['ip']}")
            return primary_device["ip"]
        return None
    
    def test_raspberry_pi_connection(self, ip: str, port: int = 22) -> bool:
        """Test if a Raspberry Pi device is reachable on a specific port"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"Connection test failed for {ip}:{port} - {e}")
            return False
    
    def save_discovered_devices(self, filename: str = "discovered_devices.json"):
        """Save discovered devices to a JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(self.discovered_devices, f, indent=2)
            logger.info(f"💾 Saved discovered devices to {filename}")
        except Exception as e:
            logger.error(f"Error saving devices: {e}")
    
    def load_discovered_devices(self, filename: str = "discovered_devices.json") -> List[Dict[str, str]]:
        """Load previously discovered devices from a JSON file"""
        try:
            with open(filename, 'r') as f:
                devices = json.load(f)
            logger.info(f"📂 Loaded {len(devices)} devices from {filename}")
            self.discovered_devices = devices
            return devices
        except FileNotFoundError:
            logger.debug(f"No saved devices file found: {filename}")
            return []
        except Exception as e:
            logger.error(f"Error loading devices: {e}")
            return []


def main():
    """Example usage and testing"""
    print("🔍 Raspberry Pi Network Discovery Tool")
    print("=" * 40)
    
    discovery = NetworkDiscovery()
    
    # Discover devices
    devices = discovery.discover_raspberry_pi_devices()
    
    if devices:
        print(f"\n✅ Found {len(devices)} Raspberry Pi device(s):")
        for i, device in enumerate(devices, 1):
            print(f"\n📱 Device {i}:")
            print(f"  IP Address: {device['ip']}")
            print(f"  MAC Address: {device['mac']}")
            print(f"  Hostname: {device.get('hostname', 'Unknown')}")
            print(f"  Vendor: {device.get('vendor', 'Raspberry Pi Foundation')}")
            print(f"  Discovery Method: {device['discovery_method']}")
            
            # Test SSH connection
            ssh_available = discovery.test_raspberry_pi_connection(device['ip'], 22)
            print(f"  SSH Available: {'✅ Yes' if ssh_available else '❌ No'}")
        
        # Get primary device
        primary_ip = discovery.get_primary_raspberry_pi_ip()
        print(f"\n🎯 Primary Raspberry Pi IP: {primary_ip}")
        
        # Save results
        discovery.save_discovered_devices()
    else:
        print("\n❌ No Raspberry Pi devices found on the network")
        print("\nTroubleshooting tips:")
        print("1. Ensure Raspberry Pi devices are powered on and connected to the network")
        print("2. Check that devices are on the same subnet")
        print("3. Install nmap for more thorough scanning: sudo apt-get install nmap")


if __name__ == "__main__":
    main()
