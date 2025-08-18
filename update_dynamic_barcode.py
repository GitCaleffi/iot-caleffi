#!/usr/bin/env python3
"""
Script to update barcode scanner app to use dynamic test barcodes
"""

import re

def update_dynamic_barcode():
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the hardcoded lambda functions with dynamic ones
    # Pattern 1: Update the lambda function
    pattern1 = r'fn=lambda: register_device_id\("817994ccfe14"\),'
    replacement1 = 'fn=lambda barcode: register_device_id(barcode) if barcode.strip() else "❌ Please enter a barcode first",'
    
    # Pattern 2: Update the inputs
    pattern2 = r'inputs=\[\],'
    replacement2 = 'inputs=[barcode_input],'
    
    # Apply replacements
    updated_content = re.sub(pattern1, replacement1, content)
    updated_content = re.sub(pattern2, replacement2, updated_content)
    
    # Write back to file
    with open(file_path, 'w') as f:
        f.write(updated_content)
    
    print("✅ Successfully updated barcode scanner app to use dynamic test barcodes")
    print("✅ Removed hardcoded '817994ccfe14' restriction")
    print("✅ Now any barcode can be used for testing")

if __name__ == "__main__":
    update_dynamic_barcode()
