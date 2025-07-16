"""
Barcode validation module for EAN barcodes and other barcode formats.
"""

import re
import logging

logger = logging.getLogger(__name__)

class BarcodeValidationError(Exception):
    """Exception raised when barcode validation fails"""
    pass

def validate_ean(barcode):
    """
    Validate and normalize an EAN barcode.
    
    Args:
        barcode (str): The barcode to validate
        
    Returns:
        str: The validated and normalized barcode
        
    Raises:
        BarcodeValidationError: If the barcode is invalid
    """
    if not barcode:
        raise BarcodeValidationError("Barcode cannot be empty")
    
    # Convert to string and strip whitespace
    barcode = str(barcode).strip()
    
    # Remove any non-digit characters for validation
    digits_only = re.sub(r'\D', '', barcode)
    
    if not digits_only:
        raise BarcodeValidationError("Barcode must contain at least one digit")
    
    # Check for common barcode lengths
    valid_lengths = [8, 10, 12, 13, 14]  # EAN-8, UPC-A, EAN-13, etc.
    
    if len(digits_only) not in valid_lengths:
        # For this application, we'll be more lenient and accept any numeric barcode
        # but log a warning for unusual lengths
        if len(digits_only) < 6:
            raise BarcodeValidationError(f"Barcode too short: {len(digits_only)} digits. Minimum 6 digits required.")
        elif len(digits_only) > 20:
            raise BarcodeValidationError(f"Barcode too long: {len(digits_only)} digits. Maximum 20 digits allowed.")
        else:
            logger.warning(f"Unusual barcode length: {len(digits_only)} digits")
    
    # For EAN-13 and EAN-8, we could validate the check digit
    # but for this application, we'll accept any valid numeric barcode
    
    # Return the normalized barcode (digits only)
    return digits_only

def validate_ean13(barcode):
    """
    Validate an EAN-13 barcode with check digit verification.
    
    Args:
        barcode (str): The 13-digit EAN barcode
        
    Returns:
        str: The validated barcode
        
    Raises:
        BarcodeValidationError: If the barcode is invalid
    """
    if not barcode:
        raise BarcodeValidationError("EAN-13 barcode cannot be empty")
    
    # Convert to string and strip whitespace
    barcode = str(barcode).strip()
    
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', barcode)
    
    if len(digits_only) != 13:
        raise BarcodeValidationError(f"EAN-13 barcode must be exactly 13 digits, got {len(digits_only)}")
    
    # Validate check digit
    if not _validate_ean13_check_digit(digits_only):
        raise BarcodeValidationError("Invalid EAN-13 check digit")
    
    return digits_only

def validate_ean8(barcode):
    """
    Validate an EAN-8 barcode with check digit verification.
    
    Args:
        barcode (str): The 8-digit EAN barcode
        
    Returns:
        str: The validated barcode
        
    Raises:
        BarcodeValidationError: If the barcode is invalid
    """
    if not barcode:
        raise BarcodeValidationError("EAN-8 barcode cannot be empty")
    
    # Convert to string and strip whitespace
    barcode = str(barcode).strip()
    
    # Remove any non-digit characters
    digits_only = re.sub(r'\D', '', barcode)
    
    if len(digits_only) != 8:
        raise BarcodeValidationError(f"EAN-8 barcode must be exactly 8 digits, got {len(digits_only)}")
    
    # Validate check digit
    if not _validate_ean8_check_digit(digits_only):
        raise BarcodeValidationError("Invalid EAN-8 check digit")
    
    return digits_only

def _validate_ean13_check_digit(barcode):
    """
    Validate the check digit for an EAN-13 barcode.
    
    Args:
        barcode (str): 13-digit barcode string
        
    Returns:
        bool: True if check digit is valid
    """
    if len(barcode) != 13:
        return False
    
    # Calculate check digit
    odd_sum = sum(int(barcode[i]) for i in range(0, 12, 2))
    even_sum = sum(int(barcode[i]) for i in range(1, 12, 2))
    
    total = odd_sum + (even_sum * 3)
    check_digit = (10 - (total % 10)) % 10
    
    return check_digit == int(barcode[12])

def _validate_ean8_check_digit(barcode):
    """
    Validate the check digit for an EAN-8 barcode.
    
    Args:
        barcode (str): 8-digit barcode string
        
    Returns:
        bool: True if check digit is valid
    """
    if len(barcode) != 8:
        return False
    
    # Calculate check digit
    odd_sum = sum(int(barcode[i]) for i in range(0, 7, 2))
    even_sum = sum(int(barcode[i]) for i in range(1, 7, 2))
    
    total = (odd_sum * 3) + even_sum
    check_digit = (10 - (total % 10)) % 10
    
    return check_digit == int(barcode[7])

def is_valid_barcode_format(barcode):
    """
    Check if a barcode has a valid format without raising exceptions.
    
    Args:
        barcode (str): The barcode to check
        
    Returns:
        bool: True if the barcode format is valid
    """
    try:
        validate_ean(barcode)
        return True
    except BarcodeValidationError:
        return False

def normalize_barcode(barcode):
    """
    Normalize a barcode by removing non-digit characters and validating format.
    
    Args:
        barcode (str): The barcode to normalize
        
    Returns:
        str: The normalized barcode (digits only)
        
    Raises:
        BarcodeValidationError: If the barcode is invalid
    """
    return validate_ean(barcode)