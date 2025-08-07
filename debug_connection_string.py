#!/usr/bin/env python3
"""
Debug script to validate Azure IoT Hub connection string format and base64 encoding
"""

import base64
import re
import sys
import os
from pathlib import Path

# Add src to path to import config
current_dir = Path(__file__).resolve().parent
src_dir = current_dir / 'src'
sys.path.append(str(src_dir))

from utils.config import load_config

def validate_base64_key(key):
    """Validate if a string is properly base64 encoded"""
    try:
        # Remove any whitespace
        key = key.strip()
        
        # Check if the key length is a multiple of 4 (required for base64)
        if len(key) % 4 != 0:
            print(f"❌ Key length ({len(key)}) is not a multiple of 4")
            return False
        
        # Try to decode the base64 string
        decoded = base64.b64decode(key, validate=True)
        print(f"✅ Base64 key is valid (decoded to {len(decoded)} bytes)")
        return True
        
    except Exception as e:
        print(f"❌ Base64 validation failed: {e}")
        return False

def fix_base64_padding(key):
    """Fix base64 padding if missing"""
    key = key.strip()
    # Add padding if needed
    missing_padding = len(key) % 4
    if missing_padding:
        key += '=' * (4 - missing_padding)
    return key

def analyze_connection_string(connection_string):
    """Analyze the connection string components"""
    print("🔍 Analyzing connection string components...")
    
    if not connection_string:
        print("❌ Connection string is empty or None")
        return False
    
    try:
        # Parse the connection string
        parts = dict(part.split('=', 1) for part in connection_string.split(';') if '=' in part)
        
        print(f"📋 Found {len(parts)} components:")
        for key in parts.keys():
            if key == 'SharedAccessKey':
                # Don't print the actual key, just its characteristics
                key_value = parts[key]
                print(f"  - {key}: [REDACTED] (length: {len(key_value)})")
                
                # Validate the SharedAccessKey
                print(f"🔑 Validating SharedAccessKey...")
                if validate_base64_key(key_value):
                    print("✅ SharedAccessKey is valid")
                else:
                    print("❌ SharedAccessKey is invalid")
                    
                    # Try to fix padding
                    print("🔧 Attempting to fix base64 padding...")
                    fixed_key = fix_base64_padding(key_value)
                    if fixed_key != key_value:
                        print(f"🔧 Fixed key length: {len(key_value)} -> {len(fixed_key)}")
                        if validate_base64_key(fixed_key):
                            print("✅ Fixed key is now valid!")
                            print(f"💡 Suggestion: Update your SharedAccessKey to: {fixed_key}")
                        else:
                            print("❌ Even after fixing padding, key is still invalid")
                    else:
                        print("❌ Key padding is correct, but key is still invalid")
                        print("💡 You may need to regenerate the SharedAccessKey from Azure Portal")
            else:
                print(f"  - {key}: {parts[key]}")
        
        # Check required components
        required_parts = ['HostName', 'DeviceId', 'SharedAccessKey']
        missing_parts = [part for part in required_parts if part not in parts]
        
        if missing_parts:
            print(f"❌ Missing required components: {missing_parts}")
            return False
        else:
            print("✅ All required components are present")
            
        return True
        
    except Exception as e:
        print(f"❌ Error parsing connection string: {e}")
        return False

def main():
    print("🔧 Azure IoT Hub Connection String Debugger")
    print("=" * 50)
    
    # Load configuration
    print("📁 Loading configuration...")
    config = load_config()
    
    if not config:
        print("❌ Failed to load configuration")
        print("💡 Make sure config.json exists or IOTHUB_CONNECTION_STRING environment variable is set")
        return
    
    connection_string = config.get('iot_hub', {}).get('connection_string')
    
    if not connection_string:
        print("❌ No connection string found in configuration")
        return
    
    print("✅ Configuration loaded successfully")
    print()
    
    # Analyze the connection string
    if analyze_connection_string(connection_string):
        print()
        print("🎉 Connection string analysis completed successfully!")
        print("💡 If the SharedAccessKey was invalid, update your config.json or environment variable")
    else:
        print()
        print("❌ Connection string has issues that need to be resolved")
        print()
        print("🔧 Troubleshooting steps:")
        print("1. Check if your Azure IoT Hub device exists")
        print("2. Regenerate the SharedAccessKey from Azure Portal")
        print("3. Ensure the connection string format is correct:")
        print("   HostName=<hub-name>.azure-devices.net;DeviceId=<device-id>;SharedAccessKey=<key>")

if __name__ == "__main__":
    main()
