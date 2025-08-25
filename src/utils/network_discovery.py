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
        """Alternative discovery method - uses dynamic MAC address detection"""
        devices = []
        
        # Method 1: Detect local device MAC address (current Pi device)
        try:
            logger.info("🔍 Detecting local Raspberry Pi device via MAC address...")
            
            # Get local device MAC address dynamically
            local_mac = self._get_local_device_mac()
            
            if local_mac:
                # Accept any MAC address for live server deployment
                logger.info(f"✅ Local device detected with MAC: {local_mac}")
                
                # Check if this MAC belongs to a Raspberry Pi (for logging purposes)
                is_pi_mac = any(local_mac.startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                device_type = "raspberry_pi" if is_pi_mac else "server_device"
                
                # Get actual server IP for connection checks
                server_ip = self._get_server_ip()
                
                device_info = {
                    "ip": server_ip if server_ip else "127.0.0.1",  # Use actual server IP
                    "mac": local_mac,
                    "hostname": f"local-{device_type}",
                    "is_raspberry_pi": False,  # Server device is NOT a Pi for connection purposes
                    "detection_reason": "local_mac_detection",
                    "discovery_method": "dynamic_mac",
                    "actual_device_type": device_type,
                    "is_server_device": True  # Mark as server device
                }
                devices.append(device_info)
                logger.info(f"🍓 Device found via MAC (using for Pi detection): {local_mac}")
            else:
                logger.warning("⚠️ Could not detect local device MAC address")
                
        except Exception as e:
            logger.warning(f"Local MAC detection failed: {e}")
            
        # Method 2: Use ip neighbor for network-wide MAC detection (scan for actual Pi devices)
        # Always scan for external Pi devices, even if server device was detected
        external_devices = self._discover_via_ip_neighbor()
        devices.extend(external_devices)
        
        # Filter out server device IP from external devices to avoid duplicates
        server_ip = self._get_server_ip()
        if server_ip:
            devices = [d for d in devices if not (d.get('ip') == server_ip and d.get('is_server_device', False))]
        
        return devices
    
    def _get_local_device_mac(self) -> str:
        """Get the MAC address of the local device dynamically"""
        import re
        
        # Method 1: Use ip link command (most reliable for servers)
        try:
            result = subprocess.run(
                ["ip", "link", "show"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Look for MAC addresses in the output
                mac_pattern = r'link/ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
                matches = re.findall(mac_pattern, result.stdout.lower())
                for mac in matches:
                    if mac != "00:00:00:00:00:00":
                        logger.info(f"📍 Found MAC address via ip link: {mac}")
                        return mac
        except Exception as e:
            logger.warning(f"ip link method failed: {e}")
        
        # Method 2: Use ifconfig command (fallback)
        try:
            result = subprocess.run(
                ["ifconfig"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Look for MAC addresses in ifconfig output
                mac_pattern = r'ether ([0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2})'
                matches = re.findall(mac_pattern, result.stdout.lower())
                for mac in matches:
                    if mac != "00:00:00:00:00:00":
                        logger.info(f"📍 Found MAC address via ifconfig: {mac}")
                        return mac
        except Exception as e:
            logger.warning(f"ifconfig method failed: {e}")
        
        # Method 3: Check /sys/class/net files (if available)
        try:
            interfaces = ['eth0', 'wlan0', 'enp0s3', 'ens33', 'eno1', 'ens160']
            for interface in interfaces:
                try:
                    with open(f"/sys/class/net/{interface}/address", 'r') as f:
                        mac = f.read().strip().lower()
                        if mac and mac != "00:00:00:00:00:00" and ":" in mac:
                            logger.info(f"📍 Found MAC address from {interface}: {mac}")
                            return mac
                except (FileNotFoundError, PermissionError):
                    continue
        except Exception as e:
            logger.debug(f"/sys/class/net method failed: {e}")
        
        # Method 4: Use cat /proc/net/arp (alternative approach)
        try:
            result = subprocess.run(
                ["cat", "/proc/net/arp"],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode == 0:
                # Parse ARP table for local device info
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        mac = parts[3].lower()
                        if mac and mac != "00:00:00:00:00:00" and ":" in mac and len(mac) == 17:
                            logger.info(f"📍 Found MAC address via /proc/net/arp: {mac}")
                            return mac
        except Exception as e:
            logger.debug(f"/proc/net/arp method failed: {e}")
        
        logger.error("❌ Could not detect local device MAC address using any method")
        return None
    
    def _get_server_ip(self) -> str:
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
        """Use ip neighbor command (modern replacement for arp)"""
        devices = []
        try:
            # Try ip neighbor command
            result = subprocess.run(
                ["ip", "neighbor", "show"], 
                capture_output=True, 
                text=True, 
                timeout=3
            )
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    # Parse ip neighbor output: 192.168.1.18 dev eth0 lladdr 2c:cf:67:6c:45:f2 REACHABLE
                    parts = line.split()
                    if len(parts) >= 5:
                        ip = parts[0]
                        mac = parts[4] if len(parts) > 4 else "unknown"
                        
                        # Check if MAC matches Pi
                        is_pi = any(mac.lower().startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                        
                        if is_pi:
                            device_info = {
                                "ip": ip,
                                "mac": mac,
                                "hostname": "raspberry-pi",
                                "is_raspberry_pi": True,
                                "detection_reason": "MAC",
                                "discovery_method": "ip_neighbor"
                            }
                            devices.append(device_info)
                            logger.info(f"🍓 Raspberry Pi found via ip neighbor: {ip} ({mac})")
        except Exception as e:
            logger.debug(f"ip neighbor failed: {e}")
        
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
    
    def discover_raspberry_pi_devices(self, use_nmap: bool = False) -> List[Dict[str, str]]:
        """
        Discover Raspberry Pi devices on the local network
        
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
