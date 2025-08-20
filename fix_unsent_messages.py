#!/usr/bin/env python3
"""
Script to fix the process_unsent_messages function to use dynamic registration service
instead of default connection string which causes "DeviceId not found" error
"""

import re

def fix_process_unsent_messages():
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern to find the problematic section in process_unsent_messages
    pattern = r'(        # Get default connection string\n        default_connection_string = config\.get\("iot_hub", \{\}\)\.get\("connection_string", None\)\n        if not default_connection_string:\n            return "Error: No default connection string provided\."\n            \n        # Create IoT Hub client\n        hub_client = HubClient\(default_connection_string\))'
    
    replacement = '''        # Get dynamic registration service for generating device connection strings
        registration_service = get_dynamic_registration_service()
        if not registration_service:
            return "Error: Failed to initialize dynamic registration service"'''
    
    # Replace the problematic section
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        # Write the fixed content back
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed process_unsent_messages function to use dynamic registration service")
        return True
    else:
        print("⚠️ Pattern not found, trying alternative approach...")
        
        # Alternative approach - find and replace line by line
        lines = content.split('\n')
        fixed_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Look for the specific problematic lines
            if "# Get default connection string" in line and i < len(lines) - 6:
                # Check if this is the process_unsent_messages function context
                if ("default_connection_string = config.get" in lines[i+1] and 
                    "if not default_connection_string:" in lines[i+2] and
                    "hub_client = HubClient(default_connection_string)" in lines[i+5]):
                    
                    # Replace the entire problematic block
                    fixed_lines.append("        # Get dynamic registration service for generating device connection strings")
                    fixed_lines.append("        registration_service = get_dynamic_registration_service()")
                    fixed_lines.append("        if not registration_service:")
                    fixed_lines.append('            return "Error: Failed to initialize dynamic registration service"')
                    
                    # Skip the original problematic lines
                    i += 6
                    continue
            
            fixed_lines.append(line)
            i += 1
        
        new_content = '\n'.join(fixed_lines)
        
        if new_content != content:
            with open(file_path, 'w') as f:
                f.write(new_content)
            print("✅ Fixed process_unsent_messages function using alternative approach")
            return True
        else:
            print("❌ Could not find the problematic section to fix")
            return False

if __name__ == "__main__":
    fix_process_unsent_messages()
