#!/usr/bin/env python3
"""
Script to fix syntax errors in barcode_scanner_app.py and ensure offline/online mode works correctly
"""
import os
import re
import shutil
import sys

def fix_syntax_errors(file_path):
    """Fix syntax errors in the given file, focusing on unterminated triple-quoted strings."""
    print(f"Fixing syntax errors in {file_path}...")
    
    # Create a backup if it doesn't exist
    backup_path = file_path + ".bak"
    if not os.path.exists(backup_path):
        shutil.copy2(file_path, backup_path)
        print(f"Created backup at {backup_path}")
    
    # Read the file content
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    # Fix process_barcode_scan function docstring
    if 'def process_barcode_scan(' in content:
        pattern = r'def process_barcode_scan\([^)]*\):\s*"""[^"]*'
        replacement = 'def process_barcode_scan(barcode, device_id=None, quantity=1, additional_data=None):\n    """Process a barcode scan and determine if it\'s a valid product or device ID."""'
        content = re.sub(pattern, replacement, content)
    
    # Fix process_unsent_messages function docstring
    if 'def process_unsent_messages(' in content:
        pattern = r'def process_unsent_messages\([^)]*\):\s*"""[^"]*'
        replacement = 'def process_unsent_messages(auto_retry=False):\n    """Process any unsent messages in the local database and try to send them."""'
        content = re.sub(pattern, replacement, content)
    
    # Write the fixed content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed syntax errors in {file_path}")

def main():
    """Main function to fix the barcode scanner app."""
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        sys.exit(1)
    
    fix_syntax_errors(file_path)
    print("Done!")

if __name__ == "__main__":
    main()
