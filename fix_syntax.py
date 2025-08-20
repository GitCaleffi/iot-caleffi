#!/usr/bin/env python3

def fix_syntax_errors(file_path):
    """Fix syntax errors in the given file, focusing on unterminated triple-quoted strings."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the process_unsent_messages function definition and docstring
    if 'def process_unsent_messages(auto_retry=False):' in content:
        # Replace the function definition and docstring with a fixed version
        content = content.replace(
            'def process_unsent_messages(auto_retry=False):\n    """Process any unsent messages in the local database and try to send them"""',
            'def process_unsent_messages(auto_retry=False):\n    """Process any unsent messages in the local database and try to send them."""'
        )
    
    # Write the fixed content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed syntax errors in {file_path}")

if __name__ == "__main__":
    file_path = "/var/www/html/abhimanyu/barcode_scanner_clean/src/barcode_scanner_app.py"
    fix_syntax_errors(file_path)
