"""
Phone number formatting module for the Phone Extraction project.
"""
import re
from src.phone.extractor import is_valid_phone_number

def format_phone_number(number: str, format: str = 'international') -> str:
    """
    Format a phone number according to the specified format.
    
    Args:
        number: Phone number string (digits only)
        format: Desired output format ('international', 'local', or 'german')
        
    Returns:
        Formatted phone number string
    """
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', number)
    
    # If not a valid phone number, return as is
    if not is_valid_phone_number(digits):
        return number
    
    if format == 'german':
        if digits.startswith('49'):
            digits = digits[2:]  # Remove country code
        if digits.startswith('0'):
            digits = digits[1:]  # Remove leading zero
        return f"+49 {digits[:3]} {digits[3:]}"
    
    elif format == 'international':
        if len(digits) >= 10:
            if digits.startswith('00'):
                digits = digits[2:]  # Remove 00 prefix
            if not digits.startswith('+'):
                digits = '+' + digits
                
            # Handle country code correctly - most country codes are 1-3 digits
            if digits.startswith('+1'):  # North American country code is just 1 digit
                return f"+1 {digits[2:5]} {digits[5:8]} {digits[8:]}"
            elif digits.startswith('+'):  # Other country codes
                # Extract country code (assuming 1-3 digits after +)
                country_code_match = re.match(r'\+(\d{1,3})', digits)
                if country_code_match:
                    country_code = country_code_match.group(1)
                    remaining = digits[1+len(country_code):]  # Skip + and country code
                    # Format the remaining digits in groups of 3
                    return f"+{country_code} {remaining[:3]} {remaining[3:6]} {remaining[6:]}"
            
            # Fallback to original formatting if no specific rule matches
            return f"{digits[:3]} {digits[3:6]} {digits[6:9]} {digits[9:]}"
    
    elif format == 'local':
        if len(digits) >= 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}"
    
    return number  # Return original if no format matches

def format_extracted_numbers(extracted_numbers):
    """
    Format a list of extracted phone numbers.
    
    Args:
        extracted_numbers: List of dictionaries containing extracted phone numbers
        
    Returns:
        List of dictionaries with formatted phone numbers added
    """
    formatted_numbers = []
    
    for number in extracted_numbers:
        formatted = number.copy()
        formatted['formatted'] = format_phone_number(number['cleaned'], number['format'])
        formatted_numbers.append(formatted)
    
    return formatted_numbers