#!/usr/bin/env python3
"""
Isolated test to replicate the exact ping logic from ConnectionManager
"""
import subprocess
import time
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_ping_logic():
    """Replicate the exact logic from ConnectionManager.check_internet_connectivity()"""
    
    print("=== Replicating ConnectionManager ping logic ===")
    
    current_time = time.time()
    print(f"Current time: {current_time}")
    
    try:
        print("\nMethod 1: Ping Google DNS (8.8.8.8)")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "8.8.8.8"], 
            capture_output=True, 
            timeout=5
        )
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT length: {len(result.stdout)}")
        print(f"STDERR length: {len(result.stderr)}")
        
        if result.returncode == 0:
            print("✅ Method 1 SUCCESS - Should return True")
            return True
            
        print("❌ Method 1 FAILED - Trying Method 2")
        
        print("\nMethod 2: Ping Cloudflare DNS (1.1.1.1)")
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "3", "1.1.1.1"], 
            capture_output=True, 
            timeout=5
        )
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT length: {len(result.stdout)}")
        print(f"STDERR length: {len(result.stderr)}")
        
        connected = result.returncode == 0
        print(f"✅ Method 2 result: {connected}")
        return connected
        
    except Exception as e:
        print(f"❌ Exception occurred: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_with_threading():
    """Test if threading affects the result"""
    import threading
    
    print("\n=== Testing with threading ===")
    
    results = []
    
    def ping_worker():
        result = test_ping_logic()
        results.append(result)
    
    # Run in thread
    thread = threading.Thread(target=ping_worker)
    thread.start()
    thread.join()
    
    print(f"Thread result: {results[0] if results else 'No result'}")

if __name__ == "__main__":
    # Test direct execution
    direct_result = test_ping_logic()
    print(f"\nDirect execution result: {direct_result}")
    
    # Test with threading
    test_with_threading()
