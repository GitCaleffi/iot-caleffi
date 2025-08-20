#!/usr/bin/env python3
"""
Script to disable aggressive reconnection loops in IoT Hub clients
that are causing auto-disconnections and bad gateway timeout errors
"""

import re

def disable_reconnection_loops():
    """Disable problematic reconnection logic in IoT Hub clients"""
    
    files_to_fix = [
        "/var/www/html/abhimanyu/barcode_scanner_clean/src/iot/hub_client.py",
        "/var/www/html/abhimanyu/barcode_scanner_clean/src/iot/barcode_hub_client.py"
    ]
    
    for file_path in files_to_fix:
        try:
            # Read the file
            with open(file_path, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Disable _schedule_reconnect method by making it a no-op
            pattern1 = r'(def _schedule_reconnect\(self\):\n\s+""".*?"""\n)(.*?)(?=\n\s+def|\nclass|\n$)'
            replacement1 = r'\1        # Reconnection disabled to prevent connection loops and timeout errors\n        logger.info("Reconnection disabled to prevent connection conflicts")\n        return\n'
            
            content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)
            
            # Disable _reconnect method by making it a no-op
            pattern2 = r'(def _reconnect\(self\):\n\s+""".*?"""\n)(.*?)(?=\n\s+def|\nclass|\n$)'
            replacement2 = r'\1        # Reconnection disabled to prevent connection loops and timeout errors\n        logger.info("Reconnection disabled to prevent connection conflicts")\n        return\n'
            
            content = re.sub(pattern2, replacement2, content, flags=re.DOTALL)
            
            # Remove calls to _schedule_reconnect
            content = re.sub(r'\s+self\._schedule_reconnect\(\)', '', content)
            
            # Remove reconnection timer initialization
            content = re.sub(r'\s+self\.reconnect_timer = None', '', content)
            content = re.sub(r'\s+self\.reconnect_interval = \d+.*', '', content)
            content = re.sub(r'\s+self\.max_reconnect_interval = \d+.*', '', content)
            
            if content != original_content:
                # Write the fixed content back
                with open(file_path, 'w') as f:
                    f.write(content)
                print(f"✅ Disabled reconnection loops in {file_path}")
            else:
                print(f"⚠️ No changes needed in {file_path}")
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
    
    print("✅ Connection loop fixes completed")
    print("✅ This should resolve auto-disconnection and bad gateway timeout errors")

if __name__ == "__main__":
    disable_reconnection_loops()
