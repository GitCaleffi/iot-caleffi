#!/usr/bin/env python3
import json
import subprocess
import logging

def fix_pi_detection():
    """Force Pi detection by updating config with known Pi IP"""
    config_path = "config.json"
    
    # Load current config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Force Pi detection with known IP
    pi_ip = "192.168.1.18"
    
    # Test connectivity first
    try:
        result = subprocess.run(["ping", "-c", "1", pi_ip], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            # Update config to force Pi recognition
            config["raspberry_pi"]["auto_detected_ip"] = pi_ip
            config["raspberry_pi"]["status"] = "connected"
            config["raspberry_pi"]["force_detection"] = True
            
            # Save updated config
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"✅ Pi detection fixed - forced IP: {pi_ip}")
            return True
        else:
            print(f"❌ Pi not reachable at {pi_ip}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    fix_pi_detection()
