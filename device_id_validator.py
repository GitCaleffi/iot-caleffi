#!/usr/bin/env python3
"""
Device ID Validation Functions
"""


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
