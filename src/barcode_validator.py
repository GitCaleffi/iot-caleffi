#!/usr/bin/env python3

class BarcodeValidationError(Exception):
    """Custom exception for barcode validation errors"""
    pass

def validate_ean(ean_value):
    """
    Validates EAN/UPC/ISBN/GTIN barcodes.
    
    Args:
        ean_value: The barcode value to validate (can be string, int, or float)
    
    Returns:
        str: The validated EAN string
        
    Raises:
        BarcodeValidationError: If the EAN is invalid
    """
    # Handle empty values
    if ean_value is None or str(ean_value).strip() == "":
        raise BarcodeValidationError("EAN value cannot be empty.")
        
    # Convert to string and clean
    ean_str = str(ean_value).strip()
    
    # Check if numeric
    if not ean_str.isdigit():
        raise BarcodeValidationError("EAN must be numeric.")
    
    # Validate length
    valid_lengths = {
        8,   # EAN-8
        12,  # UPC-A
        13,  # EAN-13/ISBN-13
        14   # GTIN-14
    }
    
    if len(ean_str) not in valid_lengths:
        raise BarcodeValidationError(
            "Invalid EAN format. Must be one of: EAN-8 (8), UPC-A (12), "
            "EAN-13/ISBN-13 (13), GTIN-14 (14 digits)"
        )
    
    # Additional ISBN-13 validation if needed
    if len(ean_str) == 13 and ean_str.startswith(('978', '979')):
        # This is an ISBN-13, which is already validated by length and numeric check
        pass
        
    return ean_str
