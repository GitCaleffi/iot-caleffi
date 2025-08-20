#!/usr/bin/env python3
"""
Script to fix all remaining instances where IoT Hub owner connection string
is being used instead of device-specific connection strings
"""

import re

def fix_all_connection_string_issues():
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix 1: Around line 2220-2228 - Replace fallback to owner connection string
    pattern1 = r'(\s+)connection_string = config\.get\("iot_hub", \{\}\)\.get\("connection_string", None\)\n(\s+)else:\n(\s+)connection_string = config\.get\("iot_hub", \{\}\)\.get\("connection_string", None\)\n(\s+)\n(\s+)if not connection_string:\n(\s+)return f"❌ Error: Device ID \'\{device_id\}\' not found in configuration and no default connection string provided\."\n(\s+)\n(\s+)# Create IoT Hub client\n(\s+)hub_client = HubClient\(connection_string\)'
    
    replacement1 = r'''\1# Use dynamic registration service to get device-specific connection string
\1registration_service = get_dynamic_registration_service()
\1if not registration_service:
\1    return f"❌ Error: Failed to initialize dynamic registration service"
\1
\1try:
\1    device_connection_string = registration_service.register_device_with_azure(device_id)
\1    if not device_connection_string:
\1        return f"❌ Error: Failed to get connection string for device {device_id}"
\1except Exception as reg_error:
\1    return f"❌ Error: Registration failed for device {device_id}: {reg_error}"
\1
\1# Create IoT Hub client with device-specific connection string
\1hub_client = HubClient(device_connection_string)'''
    
    content = re.sub(pattern1, replacement1, content)
    
    # Fix 2: Around line 2326-2329 - Replace fallback in second process_unsent_messages function
    pattern2 = r'(\s+)else:\n(\s+)connection_string = default_connection_string\n(\s+)\n(\s+)# Create a new client for each message\n(\s+)message_client = HubClient\(connection_string\)'
    
    replacement2 = r'''\1else:
\1    # Use dynamic registration service to get device-specific connection string
\1    try:
\1        device_connection_string = registration_service.register_device_with_azure(device_id)
\1        if not device_connection_string:
\1            logger.error(f"Failed to get connection string for device {device_id}")
\1            fail_count += 1
\1            continue
\1    except Exception as reg_error:
\1        logger.error(f"Registration error for device {device_id}: {reg_error}")
\1        fail_count += 1
\1        continue
\1
\1# Create a new client for each message with device-specific connection string
\1message_client = HubClient(device_connection_string)'''
    
    content = re.sub(pattern2, replacement2, content)
    
    # Fix 3: Check if there's still a second process_unsent_messages function that needs fixing
    # Look for the pattern where default_connection_string is used in the second function
    pattern3 = r'(\s+)# Get default connection string\n(\s+)default_connection_string = config\.get\("iot_hub", \{\}\)\.get\("connection_string", None\)\n(\s+)if not default_connection_string:\n(\s+)return "Error: No default connection string provided\."\n(\s+)\n(\s+)# Create IoT Hub client\n(\s+)hub_client = HubClient\(default_connection_string\)'
    
    replacement3 = r'''\1# Get dynamic registration service for generating device connection strings
\1registration_service = get_dynamic_registration_service()
\1if not registration_service:
\1    return "Error: Failed to initialize dynamic registration service"'''
    
    content = re.sub(pattern3, replacement3, content)
    
    # Check if any changes were made
    if content != original_content:
        # Write the fixed content back
        with open(file_path, 'w') as f:
            f.write(content)
        print("✅ Fixed all remaining connection string issues")
        return True
    else:
        print("⚠️ No patterns found to fix. Let me try a more targeted approach...")
        
        # Alternative approach - find and fix specific problematic lines
        lines = content.split('\n')
        fixed_lines = []
        i = 0
        changes_made = False
        
        while i < len(lines):
            line = lines[i]
            
            # Look for the specific problematic pattern around line 2220
            if ("connection_string = config.get" in line and 
                i < len(lines) - 10 and
                "hub_client = HubClient(connection_string)" in lines[i+8]):
                
                # Replace the entire problematic block
                fixed_lines.append("                    # Use dynamic registration service to get device-specific connection string")
                fixed_lines.append("                    registration_service = get_dynamic_registration_service()")
                fixed_lines.append("                    if not registration_service:")
                fixed_lines.append('                        return f"❌ Error: Failed to initialize dynamic registration service"')
                fixed_lines.append("")
                fixed_lines.append("                    try:")
                fixed_lines.append("                        device_connection_string = registration_service.register_device_with_azure(device_id)")
                fixed_lines.append("                        if not device_connection_string:")
                fixed_lines.append('                            return f"❌ Error: Failed to get connection string for device {device_id}"')
                fixed_lines.append("                    except Exception as reg_error:")
                fixed_lines.append('                        return f"❌ Error: Registration failed for device {device_id}: {reg_error}"')
                fixed_lines.append("")
                fixed_lines.append("                    # Create IoT Hub client with device-specific connection string")
                fixed_lines.append("                    hub_client = HubClient(device_connection_string)")
                
                # Skip the original problematic lines
                i += 9
                changes_made = True
                continue
            
            # Look for the second problematic pattern around line 2326
            if ("connection_string = default_connection_string" in line and 
                i < len(lines) - 5 and
                "message_client = HubClient(connection_string)" in lines[i+4]):
                
                # Replace the problematic block
                fixed_lines.append("                # Use dynamic registration service to get device-specific connection string")
                fixed_lines.append("                try:")
                fixed_lines.append("                    device_connection_string = registration_service.register_device_with_azure(device_id)")
                fixed_lines.append("                    if not device_connection_string:")
                fixed_lines.append('                        logger.error(f"Failed to get connection string for device {device_id}")')
                fixed_lines.append("                        fail_count += 1")
                fixed_lines.append("                        continue")
                fixed_lines.append("                except Exception as reg_error:")
                fixed_lines.append('                    logger.error(f"Registration error for device {device_id}: {reg_error}")')
                fixed_lines.append("                    fail_count += 1")
                fixed_lines.append("                    continue")
                fixed_lines.append("                ")
                fixed_lines.append("            # Create a new client for each message with device-specific connection string")
                fixed_lines.append("            message_client = HubClient(device_connection_string)")
                
                # Skip the original problematic lines
                i += 5
                changes_made = True
                continue
            
            fixed_lines.append(line)
            i += 1
        
        if changes_made:
            new_content = '\n'.join(fixed_lines)
            with open(file_path, 'w') as f:
                f.write(new_content)
            print("✅ Fixed connection string issues using targeted approach")
            return True
        else:
            print("❌ Could not find the problematic sections to fix")
            return False

if __name__ == "__main__":
    fix_all_connection_string_issues()
