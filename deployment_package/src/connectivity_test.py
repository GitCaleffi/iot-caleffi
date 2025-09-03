#!/usr/bin/env python3
"""
Enhanced connectivity test script for Raspberry Pi
"""
import subprocess
import time
import socket
from datetime import datetime

def ping_test(host="8.8.8.8", timeout=5):
    """Test connectivity using ping"""
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), host], 
            capture_output=True, 
            text=True,
            timeout=timeout + 2
        )
        if result.returncode == 0:
            # Extract response time from ping output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'time=' in line:
                    time_part = line.split('time=')[1].split(' ')[0]
                    return True, f"Ping successful ({time_part}ms)"
            return True, "Ping successful"
        else:
            return False, f"Ping failed: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, f"Ping timeout after {timeout}s"
    except Exception as e:
        return False, f"Ping error: {str(e)}"

def socket_test(host="8.8.8.8", port=53, timeout=5):
    """Test connectivity using socket connection to DNS port"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            return True, f"Socket connection successful to {host}:{port}"
        else:
            return False, f"Socket connection failed to {host}:{port}"
    except Exception as e:
        return False, f"Socket error: {str(e)}"

def comprehensive_connectivity_test():
    """Run multiple connectivity tests"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] Running connectivity tests...")
    
    # Test 1: Ping Google DNS
    ping_success, ping_msg = ping_test("8.8.8.8")
    print(f"  Ping Test (8.8.8.8): {'✅' if ping_success else '❌'} {ping_msg}")
    
    # Test 2: Ping Cloudflare DNS
    ping2_success, ping2_msg = ping_test("1.1.1.1")
    print(f"  Ping Test (1.1.1.1): {'✅' if ping2_success else '❌'} {ping2_msg}")
    
    # Test 3: Socket connection test
    socket_success, socket_msg = socket_test("8.8.8.8", 53)
    print(f"  Socket Test: {'✅' if socket_success else '❌'} {socket_msg}")
    
    # Overall result
    overall_success = ping_success or ping2_success or socket_success
    status = "✅ CONNECTED" if overall_success else "❌ DISCONNECTED"
    print(f"  Overall Status: {status}")
    
    return overall_success

def continuous_monitoring(interval=5):
    """Continuously monitor connectivity"""
    print("Starting continuous connectivity monitoring...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            comprehensive_connectivity_test()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "continuous":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        continuous_monitoring(interval)
    else:
        # Single test
        comprehensive_connectivity_test()
