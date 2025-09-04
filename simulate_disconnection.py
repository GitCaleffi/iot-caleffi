#!/usr/bin/env python3
"""
Simulate internet disconnection by temporarily blocking network access
"""

import subprocess
import time
import sys

def block_internet():
    """Block internet access using iptables"""
    try:
        # Block outgoing connections to simulate internet disconnection
        subprocess.run(['sudo', 'iptables', '-A', 'OUTPUT', '-p', 'tcp', '--dport', '80', '-j', 'DROP'], check=True)
        subprocess.run(['sudo', 'iptables', '-A', 'OUTPUT', '-p', 'tcp', '--dport', '443', '-j', 'DROP'], check=True)
        subprocess.run(['sudo', 'iptables', '-A', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'DROP'], check=True)
        print("🔴 Internet access blocked (simulated disconnection)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to block internet: {e}")
        return False

def unblock_internet():
    """Restore internet access"""
    try:
        # Remove the blocking rules
        subprocess.run(['sudo', 'iptables', '-D', 'OUTPUT', '-p', 'tcp', '--dport', '80', '-j', 'DROP'], check=True)
        subprocess.run(['sudo', 'iptables', '-D', 'OUTPUT', '-p', 'tcp', '--dport', '443', '-j', 'DROP'], check=True)
        subprocess.run(['sudo', 'iptables', '-D', 'OUTPUT', '-p', 'udp', '--dport', '53', '-j', 'DROP'], check=True)
        print("🟢 Internet access restored")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to restore internet: {e}")
        return False

def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ['block', 'unblock', 'test']:
        print("Usage: python3 simulate_disconnection.py [block|unblock|test]")
        print("  block   - Block internet access")
        print("  unblock - Restore internet access")
        print("  test    - Block for 15 seconds then restore")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == 'block':
        block_internet()
    elif action == 'unblock':
        unblock_internet()
    elif action == 'test':
        print("🧪 Starting internet disconnection simulation test...")
        if block_internet():
            print("⏱️ Internet blocked for 15 seconds...")
            print("💡 Check the barcode scanner logs to see LED change to red/error")
            time.sleep(15)
            unblock_internet()
            print("✅ Test completed - internet restored")

if __name__ == "__main__":
    main()
