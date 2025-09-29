#!/usr/bin/env python3
"""
Fix Device ID Issue - Prevent test barcodes from being used as device IDs
"""

import sys
import re
from pathlib import Path

def fix_device_id_validation():
    """Fix the device ID validation to prevent test barcodes from being used as device IDs"""
    print("🔧 Fixing Device ID Validation Issue")
    print("=" * 50)
    
    # The problem: test barcode 817994ccfe14 is being corrupted to 17994ccfe14 
    # and then used as device ID 17994ccfe143
    
    # Test barcodes that should NEVER be used as device IDs
    test_barcodes = [
        "817994ccfe14",    # Main test barcode
        "17994ccfe14",     # Corrupted version (missing first char)
        "7994ccfe14",      # Corrupted version (missing first two chars)
        "17994ccfe141",    # Corrupted version with extra char
        "17994ccfe143",    # The problematic device ID being created
        "36928f67f397"     # Device barcode
    ]
    
    print("🚫 Test barcodes that should NOT be device IDs:")
    for barcode in test_barcodes:
        print(f"  - {barcode}")
    
    # Create validation function
    validation_code = '''
def is_valid_device_id(device_id):
    """Validate that a device ID is not a test barcode or corrupted version"""
    if not device_id or not isinstance(device_id, str):
        return False
    
    device_id = device_id.strip()
    
    # Test barcodes that should NEVER be device IDs
    invalid_device_ids = [
        "817994ccfe14",    # Main test barcode
        "17994ccfe14",     # Corrupted version (missing first char)
        "7994ccfe14",      # Corrupted version (missing first two chars)
        "17994ccfe141",    # Corrupted version with extra char
        "17994ccfe143",    # The problematic device ID
        "36928f67f397"     # Device barcode
    ]
    
    # Check exact matches
    if device_id in invalid_device_ids:
        return False
    
    # Check if it's a variation of test barcode
    if "817994ccfe14" in device_id or device_id in "817994ccfe14":
        return False
    
    # Check if it's too similar to test barcode (edit distance)
    test_barcode = "817994ccfe14"
    if len(device_id) == len(test_barcode):
        differences = sum(1 for a, b in zip(device_id, test_barcode) if a != b)
        if differences <= 2:  # Too similar
            return False
    
    # Valid device ID should be:
    # - At least 8 characters
    # - Not a test barcode
    # - Alphanumeric
    if len(device_id) < 8:
        return False
    
    return True

def generate_proper_device_id():
    """Generate a proper device ID that's not based on test barcodes"""
    import uuid
    import hashlib
    import time
    
    # Generate based on system info + timestamp
    timestamp = str(int(time.time()))
    unique_id = str(uuid.uuid4())[:8]
    
    # Create a proper device ID
    device_id = f"device-{unique_id}"
    
    # Ensure it's not similar to test barcodes
    if not is_valid_device_id(device_id):
        # Fallback: use pure UUID
        device_id = str(uuid.uuid4()).replace('-', '')[:12]
    
    return device_id
'''
    
    # Write validation functions to a file
    validation_file = Path(__file__).parent / "device_id_validator.py"
    with open(validation_file, 'w') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\nDevice ID Validation Functions\n"""\n\n')
        f.write(validation_code)
    
    print(f"✅ Created validation file: {validation_file}")
    
    # Test the validation
    print("\n🧪 Testing validation function...")
    
    # Import the validation function
    sys.path.insert(0, str(Path(__file__).parent))
    from device_id_validator import is_valid_device_id, generate_proper_device_id
    
    test_cases = [
        ("17994ccfe143", False, "Problematic device ID"),
        ("17994ccfe14", False, "Corrupted test barcode"),
        ("817994ccfe14", False, "Main test barcode"),
        ("36928f67f397", False, "Device barcode"),
        ("device-abc12345", True, "Valid device ID"),
        ("scanner-xyz789", True, "Valid scanner ID"),
        ("12345", False, "Too short"),
        ("", False, "Empty"),
        (None, False, "None value")
    ]
    
    all_passed = True
    for device_id, expected, description in test_cases:
        result = is_valid_device_id(device_id)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"  {status} {device_id}: {description}")
        if result != expected:
            all_passed = False
    
    if all_passed:
        print("\n✅ All validation tests passed!")
    else:
        print("\n❌ Some validation tests failed!")
    
    # Generate proper device IDs
    print("\n🔧 Generating proper device IDs...")
    for i in range(3):
        proper_id = generate_proper_device_id()
        is_valid = is_valid_device_id(proper_id)
        status = "✅" if is_valid else "❌"
        print(f"  {status} Generated: {proper_id}")
    
    return validation_file

def create_fix_script():
    """Create a script to fix the current device ID issue"""
    fix_script = '''#!/usr/bin/env python3
"""
Emergency Fix for Device ID Issue
Run this to fix the problematic device ID 17994ccfe143
"""

import sys
import json
from pathlib import Path

def fix_problematic_device():
    """Fix the problematic device ID 17994ccfe143"""
    print("🚨 Emergency Fix for Device ID Issue")
    print("=" * 40)
    
    problematic_id = "17994ccfe143"
    print(f"🎯 Target problematic device ID: {problematic_id}")
    
    # Check device_config.json
    config_file = Path("device_config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            devices = config.get('devices', {})
            if problematic_id in devices:
                print(f"❌ Found problematic device in config: {problematic_id}")
                
                # Remove the problematic device
                del devices[problematic_id]
                
                # Save updated config
                with open(config_file, 'w') as f:
                    json.dump(config, f, indent=2)
                
                print(f"✅ Removed problematic device from config")
            else:
                print(f"✅ Problematic device not found in config")
                
        except Exception as e:
            print(f"❌ Error checking config: {e}")
    
    # Check local database
    try:
        sys.path.insert(0, str(Path(__file__).parent / 'deployment_package' / 'src'))
        from database.local_storage import LocalStorage
        
        local_db = LocalStorage()
        
        # Check if problematic device exists in database
        device_id = local_db.get_device_id()
        if device_id == problematic_id:
            print(f"❌ Found problematic device in database: {device_id}")
            
            # Clear the device ID (this will force re-registration with proper ID)
            # Note: This would require adding a method to LocalStorage
            print(f"⚠️ Manual intervention needed to clear device from database")
        else:
            print(f"✅ Database device ID is OK: {device_id}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    print(f"\\n📋 Next steps:")
    print(f"1. Restart the barcode scanner service")
    print(f"2. Use proper device registration with valid device ID")
    print(f"3. Avoid using test barcodes as device IDs")

if __name__ == "__main__":
    fix_problematic_device()
'''
    
    fix_file = Path(__file__).parent / "emergency_fix_device_id.py"
    with open(fix_file, 'w') as f:
        f.write(fix_script)
    
    print(f"✅ Created emergency fix script: {fix_file}")
    return fix_file

def main():
    """Main function"""
    print("🔧 Device ID Issue Diagnosis and Fix")
    print("=" * 50)
    
    print("📋 Issue Summary:")
    print("  - Test barcode 817994ccfe14 is being corrupted to 17994ccfe14")
    print("  - System is using 17994ccfe143 as device ID")
    print("  - API rejects this as invalid device ID")
    print("  - Need to prevent test barcodes from being device IDs")
    
    # Create validation functions
    validation_file = fix_device_id_validation()
    
    # Create emergency fix script
    fix_file = create_fix_script()
    
    print(f"\n🎯 Solution:")
    print(f"1. Use validation functions from: {validation_file}")
    print(f"2. Run emergency fix: python3 {fix_file}")
    print(f"3. Update device registration to use proper device IDs")
    print(f"4. Never use test barcodes as device IDs")
    
    print(f"\n✅ Fix complete! Use the generated files to resolve the issue.")

if __name__ == "__main__":
    main()
