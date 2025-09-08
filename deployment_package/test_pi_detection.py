#!/usr/bin/env python3
"""
Test script to manually verify Raspberry Pi hardware detection
"""

import os
import subprocess

def test_pi_detection():
    """Test all Pi detection methods manually"""
    print("🔍 Testing Raspberry Pi Hardware Detection Methods")
    print("=" * 60)
    
    # Method 1: Check CPU info
    print("\n📋 Method 1: Checking /proc/cpuinfo...")
    try:
        if os.path.exists("/proc/cpuinfo"):
            with open("/proc/cpuinfo", 'r') as f:
                content = f.read().lower()
                print(f"CPU info preview: {content[:200]}...")
                
                pi_indicators = ["raspberry", "pi", "arm", "bcm"]
                found_indicators = [indicator for indicator in pi_indicators if indicator in content]
                
                if found_indicators:
                    print(f"✅ SUCCESS: Found Pi indicators: {found_indicators}")
                    return True
                else:
                    print("❌ No Pi indicators found in CPU info")
        else:
            print("❌ /proc/cpuinfo not found")
    except Exception as e:
        print(f"❌ Error reading CPU info: {e}")
    
    # Method 2: Check device tree model
    print("\n🌳 Method 2: Checking device tree model...")
    try:
        model_path = "/sys/firmware/devicetree/base/model"
        if os.path.exists(model_path):
            with open(model_path, 'r') as f:
                content = f.read().lower()
                print(f"Device model: {content}")
                
                if "raspberry" in content or "pi" in content:
                    print("✅ SUCCESS: Raspberry Pi detected in device model")
                    return True
                else:
                    print("❌ No Pi indicators in device model")
        else:
            print("❌ Device tree model file not found")
    except Exception as e:
        print(f"❌ Error reading device model: {e}")
    
    # Method 3: Check Pi-specific paths
    print("\n📁 Method 3: Checking Pi-specific system paths...")
    pi_paths = [
        "/boot/config.txt",
        "/opt/vc/bin/vcgencmd", 
        "/sys/firmware/devicetree/base/model",
        "/boot/cmdline.txt",
        "/proc/device-tree/model"
    ]
    
    found_paths = []
    for path in pi_paths:
        if os.path.exists(path):
            found_paths.append(path)
            print(f"✅ Found: {path}")
        else:
            print(f"❌ Missing: {path}")
    
    if found_paths:
        print(f"✅ SUCCESS: Found {len(found_paths)} Pi-specific paths")
        return True
    
    # Method 4: Check current working directory
    print("\n📂 Method 4: Checking working directory...")
    current_path = os.getcwd()
    print(f"Current path: {current_path}")
    
    if "/home/pi/" in current_path or "raspberry" in current_path.lower():
        print("✅ SUCCESS: Running in Pi user directory")
        return True
    else:
        print("❌ Not in Pi user directory")
    
    # Method 5: Check username
    print("\n👤 Method 5: Checking current user...")
    try:
        import getpass
        username = getpass.getuser()
        print(f"Current user: {username}")
        
        if username == "pi":
            print("✅ SUCCESS: Running as 'pi' user")
            return True
        else:
            print("❌ Not running as 'pi' user")
    except Exception as e:
        print(f"❌ Error getting username: {e}")
    
    # Method 6: Check architecture
    print("\n🏗️ Method 6: Checking system architecture...")
    try:
        result = subprocess.run(["uname", "-m"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0:
            arch = result.stdout.strip()
            print(f"Architecture: {arch}")
            
            if "arm" in arch.lower():
                print("✅ SUCCESS: ARM architecture detected (likely Pi)")
                return True
            else:
                print("❌ Not ARM architecture")
        else:
            print("❌ Failed to get architecture")
    except Exception as e:
        print(f"❌ Error checking architecture: {e}")
    
    print("\n❌ ALL METHODS FAILED: No Pi hardware detected")
    return False

if __name__ == "__main__":
    result = test_pi_detection()
    print(f"\n🎯 FINAL RESULT: Pi detection = {result}")
