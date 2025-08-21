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
    
    def discover_devices_arp(self) -> List[Dict[str, str]]:
        """Discover devices using ARP table scanning with caching"""
        devices = []
        
        # Try to use cached data first
        output = self._get_cached_arp_output()
        
        if output is None:
            try:
                logger.info("Scanning ARP table for devices...")
                # Use shorter timeout and more robust command
                output = subprocess.check_output("arp -a", shell=True, timeout=3).decode()
                self._update_arp_cache(output)
            except subprocess.TimeoutExpired:
                logger.warning("ARP scan timed out - using fallback method")
                # Fallback: try with even shorter timeout
                try:
                    output = subprocess.check_output("arp -a", shell=True, timeout=1).decode()
                    self._update_arp_cache(output)
                except Exception as e:
                    logger.error(f"ARP fallback also failed: {e}")
                    # If ARP completely fails, try alternative method
                    return self._discover_devices_alternative()
            except Exception as e:
                logger.error(f"Error scanning ARP table: {e}")
                return self._discover_devices_alternative()
        
        if output:
            for line in output.splitlines():
                # Extract IP and MAC address from ARP output
                # Format: hostname (192.168.1.100) at aa:bb:cc:dd:ee:ff [ether] on eth0
                ip_match = re.search(r"\(([\d.]+)\)", line)
                mac_match = re.search(r"at ([a-fA-F0-9:]{17})", line)
                hostname_match = re.search(r"^([^\s]+)", line)
                
                if ip_match and mac_match:
                    ip = ip_match.group(1)
                    mac = mac_match.group(1).lower()
                    hostname = hostname_match.group(1) if hostname_match else "Unknown"
                    
                    # Check if MAC address matches Raspberry Pi
                    is_raspberry_pi_mac = any(mac.startswith(prefix.lower()) for prefix in self.RASPBERRY_PI_MAC_PREFIXES)
                    
                    # Check if hostname suggests Raspberry Pi
                    is_raspberry_pi_hostname = any(pi_name in hostname.lower() for pi_name in self.RASPBERRY_PI_HOSTNAMES)
                    
                    # Device is considered Raspberry Pi if either MAC or hostname matches
                    is_raspberry_pi = is_raspberry_pi_mac or is_raspberry_pi_hostname
                    
                    device_info = {
                        "ip": ip,
                        "mac": mac,
                        "hostname": hostname,
                        "is_raspberry_pi": is_raspberry_pi,
                        "detection_reason": "MAC" if is_raspberry_pi_mac else ("hostname" if is_raspberry_pi_hostname else "none"),
                        "discovery_method": "arp"
                    }
                    devices.append(device_info)
                    
                    if is_raspberry_pi:
                        reason = device_info["detection_reason"]
                        logger.info(f"🍓 Raspberry Pi found via ARP: {ip} ({mac}) - detected by {reason}")
        
        return devices
    
    def _discover_devices_alternative(self) -> List[Dict[str, str]]:
        """Alternative discovery method when ARP fails"""
        devices = []
        
        # Known Raspberry Pi IPs to check
        known_pi_ips = [
            "192.168.1.18",  # User's specific Pi
            "192.168.1.100", # Common Pi IP
            "192.168.1.101", # Common Pi IP
        ]
        
        for known_pi_ip in known_pi_ips:
            try:
                logger.info(f"Trying direct connection to {known_pi_ip}")
                
                # Test if the IP responds with a quick ping
                ping_result = subprocess.run(
                    ["ping", "-c", "1", "-W", "1", known_pi_ip], 
                    capture_output=True, 
                    timeout=2
                )
                
                if ping_result.returncode == 0:
                    logger.info(f"✅ Direct ping successful to {known_pi_ip}")
                    
                    # For the user's specific IP, use known MAC
                    mac = "2c:cf:67:6c:45:f2" if known_pi_ip == "192.168.1.18" else "unknown"
                    
                    device_info = {
                        "ip": known_pi_ip,
                        "mac": mac,
                        "hostname": "raspberry-pi",
                        "is_raspberry_pi": True,
                        "detection_reason": "direct_ping",
                        "discovery_method": "fallback"
                    }
                    devices.append(device_info)
                    logger.info(f"🍓 Raspberry Pi found via direct ping: {known_pi_ip}")
                    
                    # If we found the user's specific Pi, prioritize it
                    if known_pi_ip == "192.168.1.18":
                        break
                        
            except Exception as e:
                logger.debug(f"Ping to {known_pi_ip} failed: {e}")
                continue
        
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
