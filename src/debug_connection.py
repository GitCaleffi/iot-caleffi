#!/usr/bin/env python3
"""
Debug script to understand why connection manager fails
"""
import subprocess
import time

def test_ping_directly():
    print("=== Testing ping commands directly ===")
    
    try:
        print("Testing ping to 8.8.8.8...")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
            capture_output=True, 
            timeout=5
        )
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout.decode()}")
        print(f"STDERR: {result.stderr.decode()}")
        
        if result.returncode == 0:
            print("✅ 8.8.8.8 ping successful")
        else:
            print("❌ 8.8.8.8 ping failed")
            
    except Exception as e:
        print(f"❌ Exception during 8.8.8.8 ping: {e}")
    
    print("\n" + "="*50 + "\n")
    
    try:
        print("Testing ping to 1.1.1.1...")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "1.1.1.1"], 
            capture_output=True, 
            timeout=5
        )
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout.decode()}")
        print(f"STDERR: {result.stderr.decode()}")
        
        if result.returncode == 0:
            print("✅ 1.1.1.1 ping successful")
        else:
            print("❌ 1.1.1.1 ping failed")
            
    except Exception as e:
        print(f"❌ Exception during 1.1.1.1 ping: {e}")

def test_connection_manager_method():
    print("\n=== Testing ConnectionManager method ===")
    
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from utils.connection_manager import ConnectionManager
    
    # Create a fresh instance
    cm = ConnectionManager()
    
    # Clear cache
    cm.last_connection_check = 0
    cm.is_connected_to_internet = False
    
    print("Calling check_internet_connectivity()...")
    
    try:
        current_time = time.time()
        print(f"Current time: {current_time}")
        print(f"Last check: {cm.last_connection_check}")
        print(f"Check interval: {cm.connection_check_interval}")
        
        # Manually run the same logic as the method
        print("\nTesting Method 1: Ping Google DNS")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
            capture_output=True, 
            timeout=5
        )
        
        print(f"Method 1 return code: {result.returncode}")
        if result.returncode == 0:
            print("✅ Method 1 should succeed")
        else:
            print("❌ Method 1 failed, trying Method 2")
            
            print("\nTesting Method 2: Ping Cloudflare DNS")
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "3", "1.1.1.1"], 
                capture_output=True, 
                timeout=5
            )
            print(f"Method 2 return code: {result.returncode}")
            if result.returncode == 0:
                print("✅ Method 2 should succeed")
            else:
                print("❌ Both methods failed")
        
        # Now call the actual method
        print(f"\nCalling actual ConnectionManager.check_internet_connectivity()...")
        result = cm.check_internet_connectivity()
        print(f"Result: {result}")
        print(f"Updated is_connected_to_internet: {cm.is_connected_to_internet}")
        
    except Exception as e:
        print(f"❌ Exception in connection manager test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_ping_directly()
    test_connection_manager_method()
