#!/usr/bin/env python3
"""
Script to fix all calls to get_dynamic_registration_service() to pass the required
IoT Hub connection string parameter
"""

import re

def fix_dynamic_registration_calls():
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Pattern 1: Fix calls in process_unsent_messages functions
    # Look for: registration_service = get_dynamic_registration_service()
    # Replace with: registration_service = get_dynamic_registration_service(config.get("iot_hub", {}).get("connection_string"))
    
    pattern1 = r'(\s+)registration_service = get_dynamic_registration_service\(\)\n(\s+)if not registration_service:\n(\s+)return "Error: Failed to initialize dynamic registration service"'
    
    replacement1 = r'''\1# Get IoT Hub connection string for dynamic registration
\1iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
\1if not iot_hub_connection_string:
\1    return "Error: No IoT Hub connection string found in configuration"
\1
\1registration_service = get_dynamic_registration_service(iot_hub_connection_string)
\1if not registration_service:
\1    return "Error: Failed to initialize dynamic registration service"'''
    
    content = re.sub(pattern1, replacement1, content)
    
    # Pattern 2: Fix calls in device registration sections
    # Look for similar patterns in device registration areas
    pattern2 = r'(\s+)registration_service = get_dynamic_registration_service\(\)\n(\s+)if not registration_service:\n(\s+)return f"❌ Error: Failed to initialize dynamic registration service"'
    
    replacement2 = r'''\1# Get IoT Hub connection string for dynamic registration
\1iot_hub_connection_string = config.get("iot_hub", {}).get("connection_string")
\1if not iot_hub_connection_string:
\1    return f"❌ Error: No IoT Hub connection string found in configuration"
\1
\1registration_service = get_dynamic_registration_service(iot_hub_connection_string)
\1if not registration_service:
\1    return f"❌ Error: Failed to initialize dynamic registration service"'''
    
    content = re.sub(pattern2, replacement2, content)
    
    # Check if any changes were made
    if content != original_content:
        # Write the fixed content back
        with open(file_path, 'w') as f:
            f.write(content)
        print("✅ Fixed all get_dynamic_registration_service() calls to include connection string parameter")
        return True
    else:
        print("⚠️ No patterns found to fix. Let me try a more targeted approach...")
        
        # Alternative approach - find and fix specific lines
        lines = content.split('\n')
        fixed_lines = []
        i = 0
        changes_made = False
        
        while i < len(lines):
            line = lines[i]
            
            # Look for get_dynamic_registration_service() calls without parameters
            if "registration_service = get_dynamic_registration_service()" in line:
                # Replace with proper call that includes connection string
                indent = line[:len(line) - len(line.lstrip())]
                fixed_lines.append(f"{indent}# Get IoT Hub connection string for dynamic registration")
                fixed_lines.append(f"{indent}iot_hub_connection_string = config.get(\"iot_hub\", {{}}).get(\"connection_string\")")
                fixed_lines.append(f"{indent}if not iot_hub_connection_string:")
                fixed_lines.append(f"{indent}    return \"Error: No IoT Hub connection string found in configuration\"")
                fixed_lines.append("")
                fixed_lines.append(f"{indent}registration_service = get_dynamic_registration_service(iot_hub_connection_string)")
                changes_made = True
                i += 1
                continue
            
            fixed_lines.append(line)
            i += 1
        
        if changes_made:
            new_content = '\n'.join(fixed_lines)
            with open(file_path, 'w') as f:
                f.write(new_content)
            print("✅ Fixed get_dynamic_registration_service() calls using targeted approach")
            return True
        else:
            print("❌ Could not find get_dynamic_registration_service() calls to fix")
            return False

if __name__ == "__main__":
    fix_dynamic_registration_calls()
